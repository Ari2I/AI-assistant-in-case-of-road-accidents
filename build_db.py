"""
Скрипт индексации документов в ChromaDB.

Запуск (из папки AI-assistant):
    python build_db.py [--force]

Что делает:
    1. Проверяет manifest.json — изменились ли файлы
    2. Если изменились или --force — пересобирает базу
    3. Сохраняет новый manifest.json

Запускать повторно при:
    - добавлении новых документов в Docs_md/
    - смене модели эмбеддингов
    - необходимости полной пересборки (--force)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from langchain.schema import Document

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_gigachat import GigaChatEmbeddings
from langchain_chroma import Chroma

from config import GIGA_AUTH
from knowledge_loader import (
    discover_source_files,
    read_source_file,
    build_chunks,
    file_sha256,
    get_file_info,
)

# ---------------------------------------------------------------------------
# Настройки
# ---------------------------------------------------------------------------
DOCS_DIR = "Docs_md"
CHROMA_DIR = "chroma_db"
MANIFEST_FILE = "rag_manifest.json"

# Размер чанка и перекрытие — можно тюнить
# Меньше чанк → точнее поиск, но теряется контекст
# Больше чанк → больше контекста, но шум в результатах
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


# Модель эмбеддингов
EMBEDDINGS_MODEL = "Embeddings"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_manifest() -> dict | None:
    """Загружает манифест если существует."""
    path = Path(MANIFEST_FILE)
    if not path.exists():
        return None

    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Ошибка загрузки манифеста: {e}")
        return None


def save_manifest(manifest: dict) -> None:
    """Сохраняет манифест."""
    with open(MANIFEST_FILE, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    logger.info(f"Манифест сохранён: {MANIFEST_FILE}")


def needs_rebuild(force: bool = False) -> tuple[bool, str]:
    """
    Проверяет, нужно ли пересобирать базу.

    Args:
        force: принудительная пересборка

    Returns:
        (needs_rebuild, reason)
    """
    if force:
        return True, "Принудительная пересборка (--force)"

    manifest = load_manifest()
    if manifest is None:
        return True, "Манифест не найден — первая сборка"

    # Проверяем модель эмбеддингов
    if manifest.get("embeddings_model") != EMBEDDINGS_MODEL:
        return True, f"Модель эмбеддингов изменилась: {manifest.get('embeddings_model')} → {EMBEDDINGS_MODEL}"

    # Проверяем файлы
    old_sources = {s["path"]: s for s in manifest.get("sources", [])}
    current_files = discover_source_files(DOCS_DIR)

    # Проверяем удалённые файлы
    current_paths = {str(f) for f in current_files}
    for old_path in old_sources:
        if old_path not in current_paths:
            return True, f"Файл удалён: {old_path}"

    # Проверяем изменённые и новые файлы
    for file_path in current_files:
        path_str = str(file_path)

        if path_str not in old_sources:
            return True, f"Новый файл: {path_str}"

        old_info = old_sources[path_str]
        current_hash = file_sha256(file_path)

        if current_hash != old_info["sha256"]:
            return True, f"Файл изменён: {path_str}"

    return False, "Изменений нет — используем существующую базу"


def build_db(force: bool = False) -> None:
    """
    Строит или обновляет RAG базу.

    Args:
        force: принудительная пересборка
    """
    # Проверяем нужна ли пересборка
    rebuild_needed, reason = needs_rebuild(force)

    if not rebuild_needed:
        logger.info(f"✅ {reason}")
        logger.info("Пересборка не требуется.")
        return

    logger.info(f"📋 {reason}")
    # 1. Удаляем старую базу если есть
    if os.path.exists(CHROMA_DIR):
        print(f"[build_db] Удаляем старую базу {CHROMA_DIR}/...")
        shutil.rmtree(CHROMA_DIR)

    # 2. Загружаем документы через knowledge_loader
    logger.info(f"Загружаем документы из {DOCS_DIR}/...")
    files = discover_source_files(DOCS_DIR)

    if not files:
        logger.error("Ошибка: документы не найдены. Проверь путь к папке Docs_md/")
        return

        # Читаем все файлы и разбиваем на чанки
        all_chunks = []
        sources_info = []

        for file_path in files:
            try:
                content = read_source_file(file_path)
                chunks = build_chunks(content, CHUNK_SIZE, CHUNK_OVERLAP)
                all_chunks.extend(chunks)

                sources_info.append({
                    "path": str(file_path),
                    "sha256": file_sha256(file_path),
                    "size_bytes": file_path.stat().st_size,
                    "chunk_count": len(chunks),
                })
                logger.debug(f"  {file_path.name}: {len(chunks)} чанков")
            except Exception as e:
                logger.error(f"Ошибка чтения {file_path}: {e}")
                continue

        logger.info(f"Загружено файлов: {len(sources_info)}")
        logger.info(f"Получилось чанков: {len(all_chunks)}")

        if not all_chunks:
            logger.error("Ошибка: не удалось создать чанки")
            return

    # 3. Создаём эмбеддинги и сохраняем в ChromaDB
    logger.info("Загружаем в ChromaDB через GigaChat Embeddings...")
    logger.info("Это может занять несколько минут...")

    embeddings = GigaChatEmbeddings(
        credentials=GIGA_AUTH,
        verify_ssl_certs=False,
        scope="GIGACHAT_API_B2B",
    )

    # Создаём LangChain документы из чанков
    documents = [Document(page_content=chunk) for chunk in all_chunks]


    Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=CHROMA_DIR,
    )

    logger.info(f"Готово! База сохранена в {CHROMA_DIR}/")

    # 4. Сохраняем манифест
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "embeddings_model": EMBEDDINGS_MODEL,
        "sources": sources_info,
        "total_chunks": len(all_chunks),
    }
    save_manifest(manifest)


def main():
    parser = argparse.ArgumentParser(description="Сборка RAG базы документов")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Принудительная пересборка даже если файлы не изменились"
    )
    args = parser.parse_args()

    build_db(force=args.force)


if __name__ == "__main__":
    main()