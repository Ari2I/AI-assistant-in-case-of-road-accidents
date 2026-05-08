"""
Скрипт индексации документов в ChromaDB.

Запуск (из папки AI-assistant):
    python build_db.py

Что делает:
    1. Читает все .md файлы из Docs_md/
    2. Разбивает на чанки
    3. Загружает в chroma_db/ через GigaChat Embeddings

Запускать повторно при:
    - добавлении новых документов в Docs_md/
    - смене модели эмбеддингов
"""

import os
import shutil
from pathlib import Path

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_gigachat import GigaChatEmbeddings
from langchain_chroma import Chroma

from config import GIGA_AUTH

# ---------------------------------------------------------------------------
# Настройки
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DOCS_DIR = BASE_DIR / "Docs_md"
CHROMA_DIR = BASE_DIR / "chroma_db"

# Размер чанка и перекрытие — можно тюнить
# Меньше чанк → точнее поиск, но теряется контекст
# Больше чанк → больше контекста, но шум в результатах
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


def build_db() -> None:
    # 1. Удаляем старую базу если есть
    if os.path.exists(CHROMA_DIR):
        print(f"[build_db] Удаляем старую базу {CHROMA_DIR}/...")
        shutil.rmtree(CHROMA_DIR)

    # 2. Загружаем документы
    print(f"[build_db] Загружаем документы из {DOCS_DIR}/...")
    loader = DirectoryLoader(
        str(DOCS_DIR),
        glob="**/*.md",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
        show_progress=True,
    )
    docs = loader.load()
    print(f"[build_db] Загружено документов: {len(docs)}")

    if not docs:
        print("[build_db] Ошибка: документы не найдены. Проверь путь к папке Docs_md/")
        return

    # 3. Разбиваем на чанки
    print(f"[build_db] Разбиваем на чанки (размер={CHUNK_SIZE}, перекрытие={CHUNK_OVERLAP})...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = splitter.split_documents(docs)
    print(f"[build_db] Получилось чанков: {len(chunks)}")

    # 4. Создаём эмбеддинги и сохраняем в ChromaDB
    print("[build_db] Загружаем в ChromaDB через GigaChat Embeddings...")
    print("[build_db] Это может занять несколько минут...")

    embeddings = GigaChatEmbeddings(
        credentials=GIGA_AUTH,
        verify_ssl_certs=False,
        scope="GIGACHAT_API_B2B",
    )

    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(CHROMA_DIR),
    )

    print(f"[build_db] Готово! База сохранена в {CHROMA_DIR}/")


if __name__ == "__main__":
    build_db()
