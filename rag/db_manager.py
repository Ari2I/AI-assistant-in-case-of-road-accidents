"""
Ленивый синглтон-менеджер векторных баз данных.

Гарантирует:
  - Одна инициализация embeddings за время жизни процесса
  - Одна инициализация каждой Chroma-базы
  - Graceful-деградацию при отсутствии базы на диске (RAG не работает,
    но агент продолжает работать без контекста)

Django передаёт свои инстансы через параметры run_agent() — менеджер
используется только как fallback (локальный запуск, тесты).
"""

from __future__ import annotations

from langchain_gigachat import GigaChatEmbeddings
from langchain_chroma import Chroma
import threading

from config import GIGA_AUTH

_embeddings: GigaChatEmbeddings | None = None
_main_db:    Chroma | None = None
_feedback_db: Chroma | None = None
_disagreement_db: Chroma | None = None

# Locks для thread-safe инициализации синглтонов
_embeddings_lock = threading.Lock()
_main_db_lock = threading.Lock()
_feedback_db_lock = threading.Lock()
_disagreement_db_lock = threading.Lock()


def _get_embeddings() -> GigaChatEmbeddings:
    global _embeddings
    if _embeddings is None:
        with _embeddings_lock:
            if _embeddings is None:
                _embeddings = GigaChatEmbeddings(
                    credentials=GIGA_AUTH,
                    verify_ssl_certs=False,
                    scope="GIGACHAT_API_B2B",
                )
    return _embeddings


def get_main_db() -> Chroma | None:
    """Основная база документов (chroma_db/)."""
    global _main_db
    if _main_db is None:
        with _main_db_lock:
            if _main_db is None:
                _main_db = _load_chroma("chroma_db", "main_db")
    return _main_db


def get_feedback_db() -> Chroma | None:
    """База хороших Q&A для RAG-дообучения (chroma_feedback/)."""
    global _feedback_db
    if _feedback_db is None:
        with _feedback_db_lock:
            if _feedback_db is None:
                _feedback_db = _load_chroma("chroma_feedback", "feedback_db")
    return _feedback_db


def get_disagreement_db() -> Chroma | None:
    """База знаний для режима разногласий (chroma_disagreement/)."""
    global _disagreement_db
    if _disagreement_db is None:
        with _disagreement_db_lock:
            if _disagreement_db is None:
                _disagreement_db = _load_chroma("chroma_disagreement", "disagreement_db")
    return _disagreement_db


def _load_chroma(persist_dir: str, name: str) -> Chroma | None:
    try:
        db = Chroma(
            persist_directory=persist_dir,
            embedding_function=_get_embeddings(),
        )
        print(f"[db_manager] Loaded {name} from '{persist_dir}'")
        return db
    except Exception as e:
        print(f"[db_manager] Failed to load {name} from '{persist_dir}': {e}")
        return None