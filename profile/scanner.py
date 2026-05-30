"""
Модуль сканирования документов через GigaChat Vision.

Читает фото автомобильного документа, извлекает данные и возвращает
их в формате профиля пользователя. Бэкенд сохраняет профиль в БД
и при старте сессии ДТП подтягивает нужные поля в collected_fields.

─────────────────────────────────────────────────────────
ПУБЛИЧНЫЙ API (единственная функция для бэкенда)
─────────────────────────────────────────────────────────

    scan_to_profile(image_path: str) -> dict

Принимает путь к файлу фото на диске.
Конвертация в base64, загрузка в GigaChat и удаление файла
из хранилища после сканирования — выполняются внутри автоматически.

Исходный файл на диске НЕ удаляется — это зона ответственности бэкенда.

─────────────────────────────────────────────────────────
Поддерживаемые документы и возвращаемые поля профиля
─────────────────────────────────────────────────────────

  ОСАГО          → insurer, policy_number, policy_expiry
  Водительское   → driver_name, license_number
  удостоверение
  СТС / ПТС      → car_brand, car_number, owner_name

─────────────────────────────────────────────────────────
Пример использования (бэкенд):
─────────────────────────────────────────────────────────

    from profile.scanner import scan_to_profile

    # Бэкенд сохранил загруженное пользователем фото во временный файл
    profile_fields = scan_to_profile("/tmp/uploads/user_42_osago.jpg")

    # profile_fields → {
    #     "document_type": "osago",
    #     "insurer":        "Росгосстрах",
    #     "policy_number":  "ХХХ 1234567890",
    #     "policy_expiry":  "31.12.2025",
    # }

    # Бэкенд мёржит в профиль пользователя и УДАЛЯЕТ временный файл
    user_profile.update(profile_fields)
    user_profile.save()
    os.remove("/tmp/uploads/user_42_osago.jpg")

─────────────────────────────────────────────────────────
Конфиденциальность и удаление данных
─────────────────────────────────────────────────────────

  Фото передаётся в GigaChat только для распознавания текста.
  После завершения сканирования файл ГАРАНТИРОВАННО удаляется
  из хранилища GigaChat через finally-блок — даже при ошибке.

  Исходный файл на диске бэкенд обязан удалить самостоятельно
  сразу после получения результата scan_to_profile().
"""

from __future__ import annotations

import base64
import io
import json
import re

from gigachat import GigaChat

from config import GIGA_AUTH, GIGACHAT_VISION_MODEL
from profile.utils import image_to_base64

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
# Маппинг внутренних ключей → поля профиля
# ---------------------------------------------------------------------------

_PROFILE_KEY_MAP: dict[str, str] = {
    # ОСАГО
    "vehicle_a_insurer":        "insurer",
    "vehicle_a_policy_number":  "policy_number",
    "vehicle_a_policy_expiry":  "policy_expiry",
    # Права
    "vehicle_a_driver_name":    "driver_name",
    "vehicle_a_driver_license": "license_number",
    # СТС
    "vehicle_a_make_model":     "car_brand",
    "vehicle_a_reg_number":     "car_number",
    "vehicle_a_owner_name":     "owner_name",
}

# ---------------------------------------------------------------------------
# Промпт автоопределения типа документа
# ---------------------------------------------------------------------------

_DETECT_TYPE_PROMPT = """\
На фото — один из следующих документов, связанных с автомобилем в России.
Определи, что именно изображено.

Возможные варианты:
  osago          — полис ОСАГО (страховой полис автогражданской ответственности).
                   Признаки: слова «ОСАГО», «страховой полис», название страховой компании,
                   серия и номер полиса (три буквы + 10 цифр), даты начала и окончания.

  driver_license — водительское удостоверение (права).
                   Признаки: фото владельца, категории транспортных средств (A, B, C, D...),
                   слова «водительское удостоверение» или «driving licence».

  sts            — свидетельство о регистрации ТС (СТС) или паспорт ТС (ПТС).
                   Признаки: VIN-номер, марка и модель автомобиля, государственный номер,
                   слова «свидетельство о регистрации» или «паспорт транспортного средства».

  unknown        — документ не относится ни к одному из перечисленных типов,
                   или изображение слишком плохого качества для распознавания.

Верни ТОЛЬКО валидный JSON без пояснений и markdown:
{"document_type": "osago" | "driver_license" | "sts" | "unknown"}
"""

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

- Фамилию, имя и отчество водителя (поля 1, 2 на российских правах)
- Номер водительского удостоверения (поле 5, формат: 2 цифры пробел 2 цифры/буквы пробел 6 цифр,
  например: 77 77 123456 или 77 АА 123456)

Верни ТОЛЬКО валидный JSON без пояснений, комментариев и markdown:
{"vehicle_a_driver_name": "...", "vehicle_a_driver_license": "..."}

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
# Ожидаемые внутренние ключи для каждого типа документа
# ---------------------------------------------------------------------------

_EXPECTED_KEYS: dict[str, set[str]] = {
    "osago": {
        "vehicle_a_insurer",
        "vehicle_a_policy_number",
        "vehicle_a_policy_expiry",
    },
    "driver_license": {
        "vehicle_a_driver_name",
        "vehicle_a_driver_license",
    },
    "sts": {
        "vehicle_a_make_model",
        "vehicle_a_reg_number",
        "vehicle_a_owner_name",
    },
}

# ---------------------------------------------------------------------------
# Публичный API
# ---------------------------------------------------------------------------

def scan_to_profile(image_path: str) -> dict:
    """
    Сканирует документ по фото и возвращает поля профиля пользователя.

    Единственная публичная функция модуля для вызова бэкендом.
    Конвертация фото в base64, загрузка в GigaChat Vision,
    удаление из хранилища после сканирования — всё выполняется внутри.

    Args:
        image_path: абсолютный путь к файлу фото на диске.
                    Поддерживаемые форматы: JPEG, PNG, WEBP.
                    Файл на диске НЕ удаляется — бэкенд удаляет его сам
                    после получения результата.

    Returns:
        Словарь с полями профиля и типом документа:
        {
            "document_type": "osago" | "driver_license" | "sts" | None,

            # ОСАГО:
            "insurer":       str,   # название страховой компании
            "policy_number": str,   # серия и номер полиса
            "policy_expiry": str,   # дата окончания действия

            # Водительское удостоверение:
            "driver_name":    str,  # ФИО водителя
            "license_number": str,  # номер удостоверения

            # СТС / ПТС:
            "car_brand":  str,      # марка и модель
            "car_number": str,      # госномер
            "owner_name": str,      # ФИО владельца
        }

        Поля присутствуют только если были успешно извлечены из документа.
        При ошибке или нераспознанном документе → {"document_type": None}

    Raises:
        FileNotFoundError: если файл по указанному пути не найден.
        ValueError: если формат файла не поддерживается.
    """
    # Конвертация в base64 через utils.py (наша реализация)
    image_b64, media_type = image_to_base64(image_path)

    image_bytes = _decode_base64(image_b64)
    if not image_bytes:
        print("[scanner] Ошибка декодирования base64")
        return {"document_type": None}

    with GigaChat(
        credentials=GIGA_AUTH,
        verify_ssl_certs=False,
        scope="GIGACHAT_API_B2B",
    ) as giga:
        file_id: str | None = None
        try:
            file_id = _upload_image(giga, image_bytes, media_type)
            if not file_id:
                return {"document_type": None}

            # Автоопределение типа документа
            document_type = _detect_document_type(giga, file_id)
            print(f"[scanner] Тип документа: {document_type!r}")

            if document_type is None or document_type not in DOCUMENT_TYPES:
                print(f"[scanner] Документ не распознан")
                return {"document_type": None}

            # Извлечение полей
            raw_response = _query_vision(giga, file_id, document_type)
            raw_fields = _parse_response(raw_response, document_type)

            # Маппинг во внешние имена профиля
            profile_fields = _to_profile_fields(raw_fields)
            profile_fields["document_type"] = document_type

            print(
                f"[scanner] {document_type}: извлечено полей {len(profile_fields) - 1} "
                f"→ {[k for k in profile_fields if k != 'document_type']}"
            )
            return profile_fields

        except Exception as e:
            print(f"[scanner] Ошибка при сканировании: {e}")
            return {"document_type": None}

        finally:
            # Файл ГАРАНТИРОВАННО удаляется из хранилища GigaChat
            # даже если в процессе сканирования произошла ошибка
            if file_id:
                _delete_file_safe(giga, file_id)


# ---------------------------------------------------------------------------
# Внутренние вспомогательные функции
# ---------------------------------------------------------------------------

def _to_profile_fields(raw_fields: dict) -> dict:
    """Конвертирует внутренние ключи vehicle_a_* в читаемые имена профиля."""
    return {
        _PROFILE_KEY_MAP[k]: v
        for k, v in raw_fields.items()
        if k in _PROFILE_KEY_MAP
    }


def _detect_document_type(giga: GigaChat, file_id: str) -> str | None:
    """
    Определяет тип документа через Vision-модель.
    Возвращает "osago", "driver_license", "sts" или None.
    """
    try:
        result = giga.chat(
            {
                "model": GIGACHAT_VISION_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": _DETECT_TYPE_PROMPT,
                        "attachments": [file_id],
                    }
                ],
                "temperature": 0.0,
            }
        )
        content = result.choices[0].message.content.strip()

        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            print(f"[scanner] detect_type: JSON не найден: {content[:80]!r}")
            return None

        data = json.loads(match.group(0))
        detected = data.get("document_type", "unknown")
        return detected if detected in DOCUMENT_TYPES else None

    except Exception as e:
        print(f"[scanner] detect_type error: {e}")
        return None


def _decode_base64(image_b64: str) -> bytes | None:
    """Декодирует base64-строку в байты. Обрабатывает data URI формат."""
    try:
        if "," in image_b64:
            image_b64 = image_b64.split(",", 1)[1]
        return base64.b64decode(image_b64)
    except Exception as e:
        print(f"[scanner] base64 decode error: {e}")
        return None


def _upload_image(giga: GigaChat, image_bytes: bytes, media_type: str) -> str | None:
    """Загружает изображение в хранилище GigaChat. Возвращает file_id или None."""
    filename = _MEDIA_TYPE_TO_FILENAME.get(media_type, _DEFAULT_FILENAME)
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
    """Отправляет изображение в GigaChat Vision и возвращает текст ответа."""
    result = giga.chat(
        {
            "model": GIGACHAT_VISION_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": _PROMPTS[document_type],
                    "attachments": [file_id],
                }
            ],
            "temperature": 0.0,
        }
    )
    return result.choices[0].message.content


def _parse_response(text: str, document_type: str) -> dict:
    """Парсит JSON из ответа модели. Возвращает только валидные поля."""
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

    expected_keys = _EXPECTED_KEYS.get(document_type, set())
    return {
        k: v.strip()
        for k, v in data.items()
        if k in expected_keys and isinstance(v, str) and v.strip()
    }


def _delete_file_safe(giga: GigaChat, file_id: str) -> None:
    """Удаляет файл из хранилища GigaChat. Не бросает исключений."""
    try:
        giga.delete_file(file_id)
        print(f"[scanner] Файл удалён из хранилища GigaChat: {file_id}")
    except Exception as e:
        print(f"[scanner] Не удалось удалить файл {file_id}: {e}")