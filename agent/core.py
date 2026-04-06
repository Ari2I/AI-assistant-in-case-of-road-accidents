# 🔴 CHANGED

import uuid
from gigachat import GigaChat

from config import GIGA_AUTH
from storage.history import load_history, save_history
from rag.retrieval import get_context
from rag.feedback_db import save_good_qa

from agent.planner import plan
from agent.generator import generate_answer
from agent.filter import is_dtp_related
from evaluation.self_check import improve_answer
from evaluation.critic import critic_rate_answer


def run_agent(query, db, feedback_db, user_id):
    """
    Основной pipeline AI-агента.

    Этапы:
    1. Загрузка истории
    2. Проверка релевантности запроса
    3. Получение контекста (RAG)
    4. Планирование ответа (Planner)
    5. Генерация + самооценка
    6. Сохранение результата

    Args:
        query (str): сообщение пользователя
        db: основная RAG база
        feedback_db: база обученных ответов
        user_id (str): идентификатор пользователя

    Returns:
        dict: {answer, message_id}
    """
    try:
        history = load_history(user_id)

        history_text = "\n".join([
            f"Q: {h['query']} A: {h['answer']}"
            for h in history[-3:]
        ])

        with GigaChat(credentials=GIGA_AUTH, verify_ssl_certs=False) as giga:

            # ФИЛЬТР ТЕМЫ

            if not is_dtp_related(giga, query, history_text):
                return {
                    "answer": "Я консультирую только по вопросам ДТП.",
                    "message_id": None
                }

            # RAG
            context = get_context(db, feedback_db, query)

            # PLANNER
            plan_data = plan(giga, query, history_text)

            # GENERATE + SELF-CHECK
            answer = "Не знаю"
            confidence = 0.0

            for _ in range(2):
                raw = generate_answer(giga, query, context, plan_data)

                verdict, conf, issues, improved = improve_answer(
                    giga, query, raw, context
                )

                answer = improved
                confidence = conf

                if verdict == "GOOD" and conf > 0.7:
                    break

            # СОХРАНЕНИЕ
            entry = {
                "id": str(uuid.uuid4()),
                "query": query,
                "answer": answer,
                "confidence": confidence,
                "user_rating": None
            }

            history.append(entry)
            save_history(user_id, history)

            return {
                "answer": answer,
                "message_id": entry["id"]
            }

    except Exception as e:
        return {
            "answer": f"Ошибка: {str(e)}",
            "message_id": None
        }


def rate_answer(user_id, message_id, rating, db, feedback_db):
    """
    Обработка оценки ответа пользователем.

    Сохраняет оценку, запускает AI-критика и,
    при хорошем результате, добавляет пару вопрос-ответ в RAG базу.

    Args:
        user_id (str): ID пользователя
        message_id (str): ID сообщения
        rating (int): оценка пользователя (0-5)
        db: основная база
        feedback_db: база для дообучения
    """
    history = load_history(user_id)

    with GigaChat(credentials=GIGA_AUTH, verify_ssl_certs=False) as giga:

        for item in history:
            if item["id"] == message_id:

                # сохраняем оценку пользователя
                item["user_rating"] = rating  # 🔴 CHANGED

                # запускаем AI-критика
                score, comment = critic_rate_answer(
                    giga,
                    item["query"],
                    item["answer"]
                )

                item["critic_score"] = score  # 🔴 CHANGED
                item["critic_comment"] = comment  # 🔴 CHANGED

                # сохраняем в обучающую базу только хорошие ответы
                if rating >= 4 and score >= 4:
                    save_good_qa(item["query"], item["answer"])  # 🔴 CHANGED

    save_history(user_id, history)
