import os
from pathlib import Path
from dotenv import load_dotenv


load_dotenv(Path(__file__).parent / ".env")

GIGA_AUTH = os.getenv("GIGA_AUTH")
GIGACHAT_SCOPE = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_B2B")

# Модель с поддержкой анализа изображений.
# Используется в profile/scanner.py для сканирования документов.
# При необходимости можно переопределить через переменную окружения.
GIGACHAT_VISION_MODEL = os.getenv("GIGACHAT_VISION_MODEL", "GigaChat-2-Max")