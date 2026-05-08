import uuid
from rag.init_db import load_feedback_db

def save_good_qa(query, answer):
    feedback_db = load_feedback_db()
    feedback_db.add_texts(
        texts=[f"Вопрос: {query}\nОтвет: {answer}"],
        ids=[str(uuid.uuid4())]
    )