import base64
from typing import Tuple, Optional, Dict, Any
from pathlib import Path

from gigachat import GigaChat

_DEFAULT_ESTIMATE = 0

_DAMAGE_ANALYSIS_PROMPT = """\
Ты профессиональный эксперт-оценщик ущерба автомобилей после ДТП.
Проанализируй фотографию повреждения и предоставь детальную оценку.

ЗАДАЧА:
1. Определи тип повреждения (вмятина, царапина, разрыв, трещина, скол и т.д.)
2. Определи повреждённую деталь автомобиля (капот, бампер, дверь, крыло, фара и т.д.)
3. Оцени размер повреждения (малое: до 10 см, среднее: 10-30 см, большое: более 30 см)
4. Определи степень повреждения (поверхностное, среднее, критическое)
5. Предположи марку и модель автомобиля если возможно
6. Оцени примерную стоимость ремонта в рублях

КРИТЕРИИ ОЦЕНКИ СТОИМОСТИ:
- Царапина поверхностная: 5 000 - 15 000 руб
- Царапина глубокая с покраской: 15 000 - 40 000 руб
- Вмятина без покраски (PDR): 10 000 - 30 000 руб
- Вмятина с покраской: 25 000 - 60 000 руб
- Разрыв пластика (бампер): 30 000 - 80 000 руб
- Замена фары: 40 000 - 150 000 руб
- Замена детали кузова: 50 000 - 200 000 руб
- Повреждение нескольких деталей: суммируется

Укажи диапазон стоимости: минимальная и максимальная сумма, а также среднее значение.

Верни ответ СТРОГО в следующем формате:
ТИП_ПОВРЕЖДЕНИЯ: <тип>
ДЕТАЛЬ: <название детали>
РАЗМЕР: <малое/среднее/большое> с указанием примерных размеров в см
СТЕПЕНЬ: <поверхностное/среднее/критическое>
АВТОМОБИЛЬ: <марка и модель или "не определено">
ОПИСАНИЕ: <детальное описание видимых повреждений>
МИН_СТОИМОСТЬ: <число в рублях>
МАКС_СТОИМОСТЬ: <число в рублях>
СРЕДНЯЯ_СТОИМОСТЬ: <число в рублях>
КОММЕНТАРИЙ: <дополнительные рекомендации по ремонту>
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


def analyze_damage(
    giga: GigaChat,
    image_path: str,
    vehicle_info: Optional[str] = None,
    custom_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Анализирует повреждения на фото и оценивает примерную сумму ущерба.

    Функция использует GigaChat для анализа фотографии повреждения автомобиля,
    определения типа и степени повреждения, а также расчёта ориентировочной
    стоимости восстановительного ремонта.

    Args:
        giga: клиент GigaChat
        image_path: путь к файлу изображения с повреждением
        vehicle_info: информация об автомобиле (марка, модель, год) для уточнения оценки
        custom_prompt: пользовательский промпт (опционально). Если не указан,
            используется стандартный шаблон анализа повреждений.

    Returns:
        Словарь с результатами анализа:
        {
            "damage_type": str,          # тип повреждения
            "damaged_part": str,         # повреждённая деталь
            "size": str,                 # размер повреждения
            "severity": str,             # степень повреждения
            "vehicle": str,              # марка и модель авто
            "description": str,          # описание повреждений
            "min_cost": float,           # минимальная стоимость ремонта
            "max_cost": float,           # максимальная стоимость ремонта
            "avg_cost": float,           # средняя стоимость ремонта
            "comment": str,              # рекомендации
            "currency": str = "RUB"      # валюта оценки
        }

        При ошибке возвращает словарь с нулевыми значениями и сообщением об ошибке.

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
        return {
            "damage_type": "не определено",
            "damaged_part": "не определено",
            "size": "не определено",
            "severity": "не определено",
            "vehicle": "не определено",
            "description": f"Ошибка чтения файла: {e}",
            "min_cost": 0,
            "max_cost": 0,
            "avg_cost": 0,
            "comment": "",
            "currency": "RUB",
        }

    # Формирование промпта
    prompt = custom_prompt if custom_prompt else _DAMAGE_ANALYSIS_PROMPT

    if vehicle_info:
        prompt = f"Информация об автомобиле: {vehicle_info}\n\n{prompt}"

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

        def extract_field(pattern: str, default: str = "") -> str:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL | re.MULTILINE)
            return match.group(1).strip() if match else default

        def extract_number(field_name: str) -> float:
            pattern = rf"{field_name}:\s*([\d\s]+)"
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                num_str = match.group(1).replace(" ", "").replace("\u00A0", "")
                try:
                    return float(num_str)
                except ValueError:
                    pass
            return 0.0

        result = {
            "damage_type": extract_field(r"ТИП_ПОВРЕЖДЕНИЯ:\s*(.+?)(?=ДЕТАЛЬ:|$)", "не определено"),
            "damaged_part": extract_field(r"ДЕТАЛЬ:\s*(.+?)(?=РАЗМЕР:|$)", "не определено"),
            "size": extract_field(r"РАЗМЕР:\s*(.+?)(?=СТЕПЕНЬ:|$)", "не определено"),
            "severity": extract_field(r"СТЕПЕНЬ:\s*(.+?)(?=АВТОМОБИЛЬ:|$)", "не определено"),
            "vehicle": extract_field(r"АВТОМОБИЛЬ:\s*(.+?)(?=ОПИСАНИЕ:|$)", "не определено"),
            "description": extract_field(r"ОПИСАНИЕ:\s*(.+?)(?=МИН_СТОИМОСТЬ:|$)", ""),
            "min_cost": extract_number("МИН_СТОИМОСТЬ"),
            "max_cost": extract_number("МАКС_СТОИМОСТЬ"),
            "avg_cost": extract_number("СРЕДНЯЯ_СТОИМОСТЬ"),
            "comment": extract_field(r"КОММЕНТАРИЙ:\s*(.+)", ""),
            "currency": "RUB",
        }

        # Если средняя стоимость не указана, вычисляем её
        if result["avg_cost"] == 0 and result["min_cost"] > 0 and result["max_cost"] > 0:
            result["avg_cost"] = (result["min_cost"] + result["max_cost"]) / 2

        return result

    except (AttributeError, IndexError, ValueError) as e:
        return {
            "damage_type": "не определено",
            "damaged_part": "не определено",
            "size": "не определено",
            "severity": "не определено",
            "vehicle": "не определено",
            "description": "",
            "min_cost": 0,
            "max_cost": 0,
            "avg_cost": 0,
            "comment": f"Ошибка обработки ответа: {e}",
            "currency": "RUB",
        }


def analyze_multiple_damages(
    giga: GigaChat,
    image_paths: list[str],
    vehicle_info: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Анализирует несколько фотографий повреждений и оценивает общую сумму ущерба.

    Функция обрабатывает несколько изображений с разных ракурсов или разных
    повреждений одного автомобиля, предоставляя сводную оценку ущерба.

    Args:
        giga: клиент GigaChat
        image_paths: список путей к файлам изображений
        vehicle_info: информация об автомобиле (марка, модель, год)

    Returns:
        Словарь с результатами анализа:
        {
            "individual_analyses": list,   # список анализов для каждого фото
            "total_min_cost": float,       # общая минимальная стоимость
            "total_max_cost": float,       # общая максимальная стоимость
            "total_avg_cost": float,       # общая средняя стоимость
            "summary": str,                # сводное описание всех повреждений
            "currency": str = "RUB"        # валюта оценки
        }
    """
    if not image_paths:
        return {
            "individual_analyses": [],
            "total_min_cost": 0,
            "total_max_cost": 0,
            "total_avg_cost": 0,
            "summary": "Нет изображений для анализа",
            "currency": "RUB",
        }

    individual_results = []
    total_min = 0.0
    total_max = 0.0
    total_avg = 0.0

    for image_path in image_paths:
        try:
            result = analyze_damage(giga, image_path, vehicle_info)
            individual_results.append({
                "image_path": image_path,
                "analysis": result
            })
            total_min += result["min_cost"]
            total_max += result["max_cost"]
            total_avg += result["avg_cost"]
        except (FileNotFoundError, ValueError) as e:
            individual_results.append({
                "image_path": image_path,
                "error": str(e)
            })

    return {
        "individual_analyses": individual_results,
        "total_min_cost": total_min,
        "total_max_cost": total_max,
        "total_avg_cost": total_avg,
        "summary": f"Проанализировано {len(individual_results)} фото. "
                   f"Общая оценка ущерба: от {total_min:,.0f} до {total_max:,.0f} руб. "
                   f"Средняя стоимость: {total_avg:,.0f} руб.",
        "currency": "RUB",
    }