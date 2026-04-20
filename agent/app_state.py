"""
Глобальное состояние приложения.
Все тяжёлые объекты создаются ОДИН РАЗ при старте сервера.

Исправлено: убран импорт semantic_matcher (файл не существовал,
startup падал с ImportError). Прогрев semantic_matcher удалён.
"""

from rag.init_db import load_db, load_feedback_db


class AppState:
    def __init__(self):
        self.db = None
        self.feedback_db = None
        self._ready = False

    def initialize(self):
        """Вызвать один раз при старте сервера."""
        print("[startup] Загрузка ChromaDB...")
        self.db = load_db()

        print("[startup] Загрузка feedback DB...")
        self.feedback_db = load_feedback_db()

        self._ready = True
        print("[startup] Готово. Базы данных загружены.")

    @property
    def ready(self) -> bool:
        return self._ready


state = AppState()