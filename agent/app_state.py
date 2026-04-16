"""
Глобальное состояние приложения.
Все тяжёлые объекты создаются один раз при старте.
"""
from rag.init_db import load_db, load_feedback_db
from templates.semantic_matcher import _matcher  # синглтон

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

        print("[startup] Прогрев semantic matcher...")
        _matcher._lazy_init()  # явно прогреваем, не ждём первого запроса

        self._ready = True
        print("[startup] Готово.")

state = AppState()