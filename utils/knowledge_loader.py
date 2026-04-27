"""
Загрузчик знаний для RAG.

Поддерживаемые форматы:
- .md, .txt — текстовые файлы с fallback кодировок
- .json — JSON файлы с pretty-print
- .pdf — PDF через pypdf (постраничное извлечение)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

from pypdf import PdfReader

logger = logging.getLogger(__name__)

# Поддерживаемые расширения
SUPPORTED_EXTENSIONS = frozenset([".md", ".txt", ".json", ".pdf"])

# Fallback кодировки для текстовых файлов
TEXT_ENCODINGS = ["utf-8", "utf-8-sig", "cp1251"]

# Параметры нарезки по умолчанию
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200


def discover_source_files(path: str | Path) -> list[Path]:
    """
    Находит все поддерживаемые файлы в директории (рекурсивно).

    Args:
        path: путь к директории

    Returns:
        список путей к файлам
    """
    path = Path(path)

    if not path.exists():
        logger.warning(f"Директория не найдена: {path}")
        return []

    if not path.is_dir():
        logger.warning(f"Путь не является директорией: {path}")
        return []

    files = []
    for ext in SUPPORTED_EXTENSIONS:
        files.extend(path.rglob(f"*{ext}"))

    logger.info(f"Найдено файлов: {len(files)}")
    for f in files:
        logger.debug(f"  - {f}")

    return sorted(files)


def read_source_file(path: str | Path) -> str:
    """
    Читает файл с поддержкой всех форматов.

    Args:
        path: путь к файлу

    Returns:
        содержимое файла как строка
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {path}")

    ext = path.suffix.lower()

    if ext == ".pdf":
        return _read_pdf(path)
    elif ext == ".json":
        return _read_json(path)
    else:
        # .md, .txt и другие текстовые
        return _read_text(path)


def _read_text(path: Path) -> str:
    """
    Читает текстовый файл с fallback кодировок.

    Args:
        path: путь к файлу

    Returns:
        содержимое файла
    """
    last_error = None

    for encoding in TEXT_ENCODINGS:
        try:
            with open(path, 'r', encoding=encoding) as f:
                content = f.read()
            logger.debug(f"Прочитан {path.name} с кодировкой {encoding}")
            return content
        except UnicodeDecodeError as e:
            last_error = e
            continue

    # Если все кодировки не подошли
    raise ValueError(
        f"Не удалось прочитать файл {path} ни одной из кодировок: {TEXT_ENCODINGS}"
    ) from last_error


def _read_json(path: Path) -> str:
    """
    Читает JSON файл и возвращает formatted строку.

    Args:
        path: путь к файлу

    Returns:
        JSON как строка с pretty-print
    """
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Возвращаем formatted JSON для лучшего разбиения на чанки
    return json.dumps(data, ensure_ascii=False, indent=2)


def _read_pdf(path: Path) -> str:
    """
    Читает PDF файл постранично.

    Args:
        path: путь к файлу

    Returns:
        текст из всех страниц
    """
    reader = PdfReader(str(path))
    pages_text = []

    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text()
            if text:
                pages_text.append(f"[Страница {i+1}]\n{text}")
        except Exception as e:
            logger.warning(f"Ошибка извлечения текста со страницы {i+1} в {path.name}: {e}")

    if not pages_text:
        logger.warning(f"PDF пуст или не содержит извлекаемого текста: {path.name}")
        return ""

    return "\n\n".join(pages_text)


def file_sha256(path: str | Path) -> str:
    """
    Вычисляет SHA256 хэш файла побайтово.

    Args:
        path: путь к файлу

    Returns:
        hex строка хэша
    """
    path = Path(path)
    sha256_hash = hashlib.sha256()

    with open(path, "rb") as f:
        # Читаем порциями для больших файлов
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)

    return sha256_hash.hexdigest()


def build_chunks(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """
    Разбивает текст на чанки.

    Сначала разбивает по параграфам (\n\n), затем по chunk_size.

    Args:
        text: исходный текст
        chunk_size: максимальный размер чанка
        chunk_overlap: перекрытие между чанками

    Returns:
        список чанков
    """
    if not text.strip():
        return []

    # Сначала разбиваем по параграфам
    paragraphs = text.split("\n\n")
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    chunks = []
    current_chunk = ""

    for para in paragraphs:
        # Если параграф сам по себе больше chunk_size
        if len(para) > chunk_size:
            # Если есть накопленный чанк — сохраняем
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""

            # Разбиваем длинный параграф по chunk_size
            para_chunks = _split_long_text(para, chunk_size)
            chunks.extend(para_chunks)
        elif len(current_chunk) + len(para) + 2 <= chunk_size:
            # Параграф помещается в текущий чанк
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para
        else:
            # Параграф не помещается — сохраняем текущий и начинаем новый
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = para

    # Сохраняем последний чанк
    if current_chunk:
        chunks.append(current_chunk)

    # Применяем overlap если нужно
    if chunk_overlap > 0 and len(chunks) > 1:
        chunks = _apply_overlap(chunks, chunk_overlap)

    logger.debug(f"Разбито на чанков: {len(chunks)}")
    return chunks


def _split_long_text(text: str, chunk_size: int) -> list[str]:
    """
    Разбивает длинный текст на части по chunk_size.

    Старается разбивать по предложениям или словам.
    """
    chunks = []

    while len(text) > chunk_size:
        # Пытаемся разбить по последнему предложению
        split_idx = text.rfind(". ", 0, chunk_size)

        # Если не нашли точку — пробуем по последному пробелу
        if split_idx == -1:
            split_idx = text.rfind(" ", 0, chunk_size)

        # Если и пробела нет — режем жёстко
        if split_idx == -1:
            split_idx = chunk_size

        chunks.append(text[:split_idx].strip())
        text = text[split_idx:].strip()

    if text:
        chunks.append(text)

    return chunks


def _apply_overlap(chunks: list[str], overlap_size: int) -> list[str]:
    """
    Применяет перекрытие между чанками.

    Берёт последние overlap_size символов из предыдущего чанка
    и добавляет их в начало следующего.
    """
    if not chunks:
        return []

    result = [chunks[0]]

    for i in range(1, len(chunks)):
        prev_chunk = result[-1]
        current_chunk = chunks[i]

        # Берём конец предыдущего чанка
        overlap_text = prev_chunk[-overlap_size:] if len(prev_chunk) > overlap_size else prev_chunk

        # Добавляем перекрытие к текущему
        overlapped = overlap_text + "\n\n" + current_chunk
        result.append(overlapped)

    return result


def get_file_info(path: str | Path) -> dict[str, Any]:
    """
    Получает информацию о файле для манифеста.

    Args:
        path: путь к файлу

    Returns:
        dict с path, sha256, size_bytes
    """
    path = Path(path)

    return {
        "path": str(path),
        "sha256": file_sha256(path),
        "size_bytes": path.stat().st_size,
    }