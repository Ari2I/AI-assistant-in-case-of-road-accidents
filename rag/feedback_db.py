import uuid
from rag.db_manager import get_feedback_db


def save_good_qa(query: str, answer: str) -> None:
    """Сохраняет хорошую пару Q&A в базу дообучения."""
    db = get_feedback_db()
    if db is None:
        print("[feedback_db] База недоступна, Q&A не сохранена.")
        return
    db.add_texts(
        texts=[f"Вопрос: {query}\nОтвет: {answer}"],
        ids=[str(uuid.uuid4())],
    )