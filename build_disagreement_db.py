"""
Скрипт индексации документов по разногласиям в ChromaDB.

Запуск:
    python build_disagreement_db.py

Что делает:
    1. Читает все .md файлы из Docs_disagreement/
    2. Разбивает на чанки
    3. Загружает в chroma_disagreement/
"""

import os
import shutil

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_gigachat import GigaChatEmbeddings
from langchain_chroma import Chroma

from config import GIGA_AUTH

DOCS_DIR   = "Docs_disagreement"
CHROMA_DIR = "chroma_disagreement"

CHUNK_SIZE    = 1000
CHUNK_OVERLAP = 200


def build_disagreement_db() -> None:
    if os.path.exists(CHROMA_DIR):
        print(f"[build_disagreement_db] Удаляем старую базу {CHROMA_DIR}/...")
        shutil.rmtree(CHROMA_DIR)

    print(f"[build_disagreement_db] Загружаем документы из {DOCS_DIR}/...")
    loader = DirectoryLoader(
        DOCS_DIR,
        glob="**/*.md",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
        show_progress=True,
    )
    docs = loader.load()
    print(f"[build_disagreement_db] Загружено документов: {len(docs)}")

    if not docs:
        print("[build_disagreement_db] Ошибка: документы не найдены.")
        return

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = splitter.split_documents(docs)
    print(f"[build_disagreement_db] Получилось чанков: {len(chunks)}")

    embeddings = GigaChatEmbeddings(
        credentials=GIGA_AUTH,
        verify_ssl_certs=False,
        scope="GIGACHAT_API_B2B",
    )

    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_DIR,
    )
    print(f"[build_disagreement_db] Готово! База сохранена в {CHROMA_DIR}/")


if __name__ == "__main__":
    build_disagreement_db()