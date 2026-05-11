"""
Обёртка для обратной совместимости с Django-бэкендом.
Django вызывает load_db() / load_feedback_db() при старте
и передаёт результат в run_agent() как параметры.

Новый код агента использует rag.db_manager напрямую.
"""

from rag.db_manager import get_main_db, get_feedback_db


def load_db():
    """Возвращает основную Chroma-базу документов."""
    return get_main_db()


def load_feedback_db():
    """Возвращает базу хороших Q&A."""
    return get_feedback_db()