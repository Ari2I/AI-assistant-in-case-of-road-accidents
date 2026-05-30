"""
Утилиты для работы с изображениями документов.

Используется при локальном тестировании через main_AI.py:
  - Поиск изображений в папке test_docs/
  - Конвертация файла в base64 для передачи в scanner.py
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

# Поддерживаемые форматы изображений
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({
    ".jpg", ".jpeg", ".png", ".webp",
})

# MIME-типы по расширению (mimetypes иногда даёт неточный результат)
_EXT_TO_MEDIA_TYPE: dict[str, str] = {
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
    ".webp": "image/webp",
}


def image_to_base64(image_path: str | Path) -> tuple[str, str]:
    """
    Конвертирует файл изображения в base64-строку.

    Args:
        image_path: путь к файлу изображения

    Returns:
        Кортеж (base64_string, media_type).
        media_type — например "image/jpeg" или "image/png".

    Raises:
        FileNotFoundError: если файл не найден
        ValueError: если формат файла не поддерживается
    """
    path = Path(image_path)

    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Неподдерживаемый формат: {ext!r}. "
            f"Допустимые: {sorted(SUPPORTED_EXTENSIONS)}"
        )

    media_type = _EXT_TO_MEDIA_TYPE.get(ext, "image/jpeg")

    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    return b64, media_type


def find_images(folder: str | Path) -> list[Path]:
    """
    Ищет все изображения в папке (без рекурсии в подпапки).

    Args:
        folder: путь к папке

    Returns:
        Отсортированный список путей к найденным изображениям.
        Пустой список если папка пуста или не существует.
    """
    folder = Path(folder)
    if not folder.exists():
        return []

    images = [
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    return sorted(images)


def ensure_test_docs_dir(folder: str | Path = "test_docs") -> Path:
    """
    Создаёт папку для тестовых документов если она не существует.

    Returns:
        Path к папке.
    """
    path = Path(folder)
    path.mkdir(exist_ok=True)
    return path