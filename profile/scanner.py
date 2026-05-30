"""
Модуль сканирования документов через GigaChat Vision.

Бэкенд передаёт фото документа в base64 → модуль возвращает
словарь с полями в формате collected_fields из step2_europrotocol.

Поддерживаемые документы:
  "osago"          → vehicle_a_insurer, vehicle_a_policy_number, vehicle_a_policy_expiry
  "driver_license" → vehicle_a_owner_name, vehicle_a_driver_name, vehicle_a_driver_license
  "sts"            → vehicle_a_make_model, vehicle_a_reg_number, vehicle_a_owner_name

Пример использования (бэкенд):
    from gigachat import GigaChat
    from profile.scanner import scan_document
    from config import GIGA_AUTH, GIGACHAT_VISION_MODEL

    with GigaChat(credentials=GIGA_AUTH, verify_ssl_certs=False,
                  scope="GIGACHAT_API_B2B") as giga:
        fields = scan_document(
            giga=giga,
            image_b64="<base64-строка>",
            media_type="image/jpeg",
            document_type="osago",
        )
    # fields → {"vehicle_a_insurer": "Росгосстрах", "vehicle_a_policy_number": "ХХХ 1234567890", ...}
"""

from __future__ import annotations

import base64
import io
import json
import re

from gigachat import GigaChat

from config import GIGACHAT_VISION_MODEL

# ---------------------------------------------------------------------------
# Типы документов
# ---------------------------------------------------------------------------

DOCUMENT_TYPES: frozenset[str] = frozenset({
    "osago",
    "driver_license",
    "sts",
})

# ---------------------------------------------------------------------------
# Имена файлов для загрузки (GigaChat определяет тип по расширению)
# ---------------------------------------------------------------------------

_MEDIA_TYPE_TO_FILENAME: dict[str, str] = {
    "image/jpeg": "document.jpg",
    "image/jpg":  "document.jpg",
    "image/png":  "document.png",
    "image/webp": "document.webp",
}

_DEFAULT_FILENAME = "document.jpg"

# ---------------------------------------------------------------------------
# Промпты для каждого типа документа
# ---------------------------------------------------------------------------

_PROMPTS: dict[str, str] = {

    "osago": """\
На фото — полис ОСАГО (страховка автомобиля).
Внимательно прочитай все данные на документе и извлеки:

- Название страховой компании (поле «Страховщик» или шапка документа)
- Серию и номер полиса (формат: три буквы + 10 цифр, например ХХХ 1234567890 или ЕЕЕ 0987654321)
- Срок действия полиса — только дату ОКОНЧАНИЯ (например: 31.12.2025)

Верни ТОЛЬКО валидный JSON без пояснений, комментариев и markdown:
{"vehicle_a_insurer": "...", "vehicle_a_policy_number": "...", "vehicle_a_policy_expiry": "..."}

Если какое-то поле невозможно прочитать на фото — не включай его в JSON.
""",

    "driver_license": """\
На фото — водительское удостоверение (права).
Внимательно прочитай все данные и извлеки:

- Фамилию, имя и отчество владельца (поля 1, 2 на российских правах)
- Номер водительского удостоверения (поле 5, формат: 2 цифры пробел 2 цифры/буквы пробел 6 цифр,
  например: 77 77 123456 или 77 АА 123456)

Владелец и водитель — одно и то же лицо, поэтому owner_name и driver_name будут одинаковыми.

Верни ТОЛЬКО валидный JSON без пояснений, комментариев и markdown:
{"vehicle_a_owner_name": "...", "vehicle_a_driver_name": "...", "vehicle_a_driver_license": "..."}

Если какое-то поле невозможно прочитать на фото — не включай его в JSON.
""",

    "sts": """\
На фото — свидетельство о регистрации транспортного средства (СТС) или ПТС.
Внимательно прочитай все данные и извлеки:

- Марку и модель автомобиля (например: Toyota Camry, Kia Rio, ВАЗ 2114)
- Государственный регистрационный знак (госномер, например: А123БВ777)
- ФИО владельца (фамилия, имя, отчество — поле «Владелец»)

Верни ТОЛЬКО валидный JSON без пояснений, комментариев и markdown:
{"vehicle_a_make_model": "...", "vehicle_a_reg_number": "...", "vehicle_a_owner_name": "..."}

Если какое-то поле невозможно прочитать на фото — не включай его в JSON.
""",
}

# ---------------------------------------------------------------------------
# Публичная функция
# ---------------------------------------------------------------------------

def scan_document(
    giga: GigaChat,
    image_b64: str,
    media_type: str,
    document_type: str,
) -> dict:
    """
    Сканирует документ по фото и возвращает извлечённые поля.

    Args:
        giga:          активный клиент GigaChat (создаётся и закрывается бэкендом)
        image_b64:     фото документа в формате base64
        media_type:    MIME-тип изображения ("image/jpeg" | "image/png" | "image/webp")
        document_type: тип документа ("osago" | "driver_license" | "sts")

    Returns:
        Словарь с извлечёнными полями в формате collected_fields.
        Пустой словарь — если документ нераспознан или произошла ошибка.

    Raises:
        ValueError: если передан неизвестный document_type.
    """
    if document_type not in DOCUMENT_TYPES:
        raise ValueError(
            f"Неизвестный тип документа: {document_type!r}. "
            f"Допустимые значения: {sorted(DOCUMENT_TYPES)}"
        )

    image_bytes = _decode_base64(image_b64)
    if not image_bytes:
        print(f"[scanner] Ошибка декодирования base64 для документа {document_type!r}")
        return {}

    file_id: str | None = None
    try:
        file_id = _upload_image(giga, image_bytes, media_type)
        if not file_id:
            return {}

        raw_response = _query_vision(giga, file_id, document_type)
        result = _parse_response(raw_response, document_type)

        print(f"[scanner] {document_type}: извлечено полей {len(result)} → {list(result.keys())}")
        return result

    except Exception as e:
        print(f"[scanner] Ошибка при сканировании {document_type!r}: {e}")
        return {}

    finally:
        if file_id:
            _delete_file_safe(giga, file_id)


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _decode_base64(image_b64: str) -> bytes | None:
    """Декодирует base64-строку в байты. Обрабатывает data URI формат."""
    try:
        # Обрезаем data URI префикс если есть: "data:image/jpeg;base64,..."
        if "," in image_b64:
            image_b64 = image_b64.split(",", 1)[1]
        return base64.b64decode(image_b64)
    except Exception as e:
        print(f"[scanner] base64 decode error: {e}")
        return None


def _upload_image(giga: GigaChat, image_bytes: bytes, media_type: str) -> str | None:
    """
    Загружает изображение в хранилище GigaChat.
    Возвращает file_id или None при ошибке.
    """
    filename = _MEDIA_TYPE_TO_FILENAME.get(media_type, _DEFAULT_FILENAME)

    # BytesIO нужен атрибут name — по нему GigaChat определяет content-type
    file_obj = io.BytesIO(image_bytes)
    file_obj.name = filename

    try:
        uploaded = giga.upload_file(file_obj, purpose="general")
        file_id = uploaded.id_
        print(f"[scanner] Файл загружен: {file_id} ({filename}, {len(image_bytes)} байт)")
        return file_id
    except Exception as e:
        print(f"[scanner] Ошибка загрузки файла: {e}")
        return None


def _query_vision(giga: GigaChat, file_id: str, document_type: str) -> str:
    """
    Отправляет изображение в GigaChat Vision и возвращает текст ответа.
    Использует модель GIGACHAT_VISION_MODEL из config.py.
    """
    prompt = _PROMPTS[document_type]

    result = giga.chat(
        {
            "model": GIGACHAT_VISION_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "attachments": [file_id],
                }
            ],
            "temperature": 0.0,
        }
    )
    return result.choices[0].message.content


def _parse_response(text: str, document_type: str) -> dict:
    """
    Парсит JSON из ответа модели.
    Возвращает только валидные поля для данного типа документа.
    """
    # Убираем markdown-обёртку если модель всё же её добавила
    if "```" in text:
        for part in text.split("```"):
            stripped = part.strip()
            if stripped.startswith("{"):
                text = stripped
                break

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        print(f"[scanner] JSON не найден в ответе: {text[:120]!r}")
        return {}

    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        print(f"[scanner] JSON parse error: {e} | text: {text[:120]!r}")
        return {}

    # Оставляем только ожидаемые поля и непустые значения
    expected_keys = _EXPECTED_KEYS.get(document_type, set())
    return {
        k: v.strip()
        for k, v in data.items()
        if k in expected_keys and isinstance(v, str) and v.strip()
    }


def _delete_file_safe(giga: GigaChat, file_id: str) -> None:
    """Удаляет файл из хранилища. Не бросает исключений."""
    try:
        giga.delete_file(file_id)
        print(f"[scanner] Файл удалён: {file_id}")
    except Exception as e:
        print(f"[scanner] Не удалось удалить файл {file_id}: {e}")


# ---------------------------------------------------------------------------
# Ожидаемые ключи для каждого типа документа
# ---------------------------------------------------------------------------

_EXPECTED_KEYS: dict[str, set[str]] = {
    "osago": {
        "vehicle_a_insurer",
        "vehicle_a_policy_number",
        "vehicle_a_policy_expiry",
    },
    "driver_license": {
        "vehicle_a_owner_name",
        "vehicle_a_driver_name",
        "vehicle_a_driver_license",
    },
    "sts": {
        "vehicle_a_make_model",
        "vehicle_a_reg_number",
        "vehicle_a_owner_name",
    },
}