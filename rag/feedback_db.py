import uuid
from rag.db_manager import get_feedback_db


def save_good_qa(query: str, answer: str, db=None) -> None:
    """
    Сохраняет хорошую пару Q&A в базу дообучения.

    Args:
        query:  вопрос пользователя
        answer: ответ агента
        db:     экземпляр ChromaDB. Если None — берётся синглтон из db_manager.
    """
    actual_db = db or get_feedback_db()
    if actual_db is None:
        print("[feedback_db] База недоступна, Q&A не сохранена.")
        return
    actual_db.add_texts(
        texts=[f"Вопрос: {query}\nОтвет: {answer}"],
        ids=[str(uuid.uuid4())],
    )