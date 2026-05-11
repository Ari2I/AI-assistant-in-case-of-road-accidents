"""
Обёртка для обратной совместимости с Django-бэкендом.
"""

from rag.db_manager import get_disagreement_db


def load_disagreement_db():
    """Возвращает базу знаний по разногласиям."""
    return get_disagreement_db()