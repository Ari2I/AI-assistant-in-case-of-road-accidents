import base64
from typing import Tuple, Optional
from pathlib import Path

from gigachat import GigaChat

_DEFAULT_SCORE = 3

_PROMPT_TEMPLATE = """\
Оцени качество фотографии по шкале от 1 до 5.

Критерии оценки:
5 — отличное фото: высокая чёткость, хорошее освещение, правильная композиция, нет шумов и размытия
4 — хорошее фото: небольшие недостатки в освещении или композиции, но общее качество высокое
3 — среднее фото: заметные проблемы с освещением, фокусом или композицией, но объект различим
2 — плохое фото: сильное размытие, плохое освещение, шумы, объект плохо различим
1 — очень плохое фото: фото невозможно использовать — сильное размытие, темнота, артефакты

Верни ответ строго в формате:
ОЦЕНКА: <число от 1 до 5>
КОММЕНТАРИЙ: <краткое обоснование с указанием конкретных проблем или достоинств>
"""


def _encode_image_to_base64(image_path: str) -> str:
    """
    Кодирует изображение в base64 для отправки в GigaChat.

    Args:
        image_path: путь к файлу изображения

    Returns:
        Base64 строка с изображением
    """
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def _get_image_mime_type(image_path: str) -> str:
    """
    Определяет MIME тип изображения по расширению файла.

    Args:
        image_path: путь к файлу изображения

    Returns:
        MIME тип изображения
    """
    suffix = Path(image_path).suffix.lower()
    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    return mime_types.get(suffix, "image/jpeg")


def rate_photo(
    giga: GigaChat,
    image_path: str,
    custom_prompt: Optional[str] = None,
) -> Tuple[int, str]:
    """
    Оценивает качество фотографии с помощью GigaChat.

    Args:
        giga: клиент GigaChat
        image_path: путь к файлу изображения
        custom_prompt: пользовательский промпт для оценки (опционально).
            Если не указан, используется стандартный шаблон оценки качества фото.

    Returns:
        Кортеж (score, comment). score от 1 до 5.
        При ошибке возвращает (_DEFAULT_SCORE, "").

    Raises:
        FileNotFoundError: если файл изображения не найден
        ValueError: если файл не является поддерживаемым изображением
    """
    # Проверка существования файла
    if not Path(image_path).exists():
        raise FileNotFoundError(f"Файл изображения не найден: {image_path}")

    # Проверка расширения
    valid_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
    file_suffix = Path(image_path).suffix.lower()
    if file_suffix not in valid_extensions:
        raise ValueError(
            f"Неподдерживаемый формат файла: {file_suffix}. "
            f"Допустимые форматы: {', '.join(valid_extensions)}"
        )

    # Кодирование изображения
    try:
        image_base64 = _encode_image_to_base64(image_path)
        mime_type = _get_image_mime_type(image_path)
    except IOError as e:
        return _DEFAULT_SCORE, f"Ошибка чтения файла: {e}"

    # Формирование промпта
    prompt = custom_prompt if custom_prompt else _PROMPT_TEMPLATE

    try:
        # Отправка запроса с изображением в GigaChat
        response = giga.chat(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_base64}"
                            },
                        },
                    ],
                }
            ]
        )

        text = response.choices[0].message.content

        # Парсинг ответа
        import re

        score_match = re.search(r"ОЦЕНКА:\s*([1-5])", text)
        comment_match = re.search(r"КОММЕНТАРИЙ:\s*(.+)", text, re.DOTALL)

        score = int(score_match.group(1)) if score_match else _DEFAULT_SCORE
        comment = comment_match.group(1).strip() if comment_match else text.strip()

        return score, comment

    except (AttributeError, IndexError, ValueError) as e:
        return _DEFAULT_SCORE, f"Ошибка обработки ответа: {e}"


def rate_photo_for_dtp(
    giga: GigaChat,
    image_path: str,
    description: Optional[str] = None,
) -> Tuple[int, str, list]:
    """
    Оценивает фотографию ДТП и выявляет ключевые детали.

    Специализированная функция для анализа фотографий дорожно-транспортных
    происшествий. Оценивает пригодность фото для страховой выплаты и
    определяет видимые повреждения.

    Args:
        giga: клиент GigaChat
        image_path: путь к файлу изображения
        description: описание ситуации от пользователя (опционально)

    Returns:
        Кортеж (score, comment, details), где:
            - score: оценка от 1 до 5
            - comment: комментарий о качестве фото
            - details: список видимых деталей (повреждения, номера, знаки и т.д.)
        При ошибке возвращает (_DEFAULT_SCORE, "", []).
    """
    dtp_prompt = """\
Ты эксперт по оценке фотографий ДТП. Проанализируй фотографию и оцени её качество \
для использования в страховых целях.

Критерии оценки:
5 — отличное фото: видны все детали повреждений, номера автомобилей, дорожные знаки, \
    хорошее освещение, чёткое изображение
4 — хорошее фото: видны основные повреждения, но некоторые детали могут быть неразборчивы
3 — среднее фото: повреждения видны, но есть проблемы с качеством (освещение, ракурс, фокус)
2 — плохое фото: повреждения трудно разглядеть, важные детали отсутствуют
1 — очень плохое фото: невозможно идентифицировать повреждения или автомобили

Найди и перечисли:
1. Видимые повреждения автомобилей
2. Номера автомобилей (если видны)
3. Дорожные знаки и разметку
4. Обстоятельства места (перекрёсток, парковка, обочина и т.д.)
5. Другие важные детали

Верни ответ строго в формате:
ОЦЕНКА: <число от 1 до 5>
КОММЕНТАРИЙ: <общая оценка пригодности для страховой выплаты>
ДЕТАЛИ: <список найденных деталей, каждая с новой строки через дефис>
"""

    if description:
        dtp_prompt = f"{description}\n\n{dtp_prompt}"

    # Проверка существования файла
    if not Path(image_path).exists():
        raise FileNotFoundError(f"Файл изображения не найден: {image_path}")

    # Проверка расширения
    valid_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
    file_suffix = Path(image_path).suffix.lower()
    if file_suffix not in valid_extensions:
        raise ValueError(
            f"Неподдерживаемый формат файла: {file_suffix}. "
            f"Допустимые форматы: {', '.join(valid_extensions)}"
        )

    # Кодирование изображения
    try:
        image_base64 = _encode_image_to_base64(image_path)
        mime_type = _get_image_mime_type(image_path)
    except IOError as e:
        return _DEFAULT_SCORE, f"Ошибка чтения файла: {e}", []

    try:
        response = giga.chat(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": dtp_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_base64}"
                            },
                        },
                    ],
                }
            ]
        )

        text = response.choices[0].message.content

        import re

        score_match = re.search(r"ОЦЕНКА:\s*([1-5])", text)
        comment_match = re.search(r"КОММЕНТАРИЙ:\s*(.+?)(?=ДЕТАЛИ:|$)", text, re.DOTALL)
        details_match = re.search(r"ДЕТАЛИ:\s*(.+)", text, re.DOTALL)

        score = int(score_match.group(1)) if score_match else _DEFAULT_SCORE
        comment = comment_match.group(1).strip() if comment_match else text.strip()

        details = []
        if details_match:
            details_text = details_match.group(1).strip()
            # Парсинг списка деталей (каждая с новой строки или через дефис)
            for line in details_text.split("\n"):
                line = line.strip()
                if line.startswith("-"):
                    line = line[1:].strip()
                if line:
                    details.append(line)

        return score, comment, details

    except (AttributeError, IndexError, ValueError) as e:
        return _DEFAULT_SCORE, f"Ошибка обработки ответа: {e}", []