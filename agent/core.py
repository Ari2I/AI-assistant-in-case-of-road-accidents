"""
Основной pipeline AI-агента.

Это единственный core.py в проекте. Файл agent/core.py удалён —
вся логика находится здесь.
"""

import uuid
from typing import Optional

from gigachat import GigaChat

from config import GIGA_AUTH
from storage.history import load_history, save_history
from rag.retrieval import get_context
from rag.feedback_db import save_good_qa

from agent.planner import build_plan
from agent.generator import generate_answer
from agent.filter import is_dtp_related
from evaluation.self_check import improve_answer
from evaluation.critic import critic_rate_answer
from templates.matcher import match_template
from agent.algorithm import load_algorithm

# Порог уверенности: выше — прекращаем цикл self-check
_CONFIDENCE_THRESHOLD = 0.7
# Максимальное число попыток self-check
_MAX_IMPROVE_ATTEMPTS = 2
# Сколько последних сообщений попадает в history_text для контекста
_HISTORY_CONTEXT_SIZE = 3
# Загружается один раз при импорте модуля
_ALGORITHM = load_algorithm()

def run_agent(query: str, db, feedback_db, user_id: str) -> dict:
    """
    Обрабатывает сообщение пользователя и возвращает ответ.

    Pipeline:
    0. Шаблонный матчер (0 токенов).
    1. Загрузка истории диалога.
    2. Фильтр нерелевантных запросов.
    3. Получение контекста из RAG.
    4. Планирование (намерение + тип ответа).
    5. Генерация + self-check (до _MAX_IMPROVE_ATTEMPTS попыток).
    6. Сохранение в историю.

    Args:
        query: сообщение пользователя
        db: основная RAG-база (может быть None)
        feedback_db: база дообучения на фидбеке (может быть None)
        user_id: идентификатор пользователя

    Returns:
        dict с ключами: answer (str), message_id (str | None), source (str)
    """
    # ШАГ 0: шаблонный ответ — без LLM, без токенов
    template_answer = match_template(query)
    if template_answer:
        _save_to_history(user_id, query, template_answer, confidence=1.0, source="template")
        return {
            "answer": template_answer,
            "message_id": None,
            "source": "template",
        }

    try:
        history = load_history(user_id)
        history_text = _build_history_text(history)

        with GigaChat(credentials=GIGA_AUTH, verify_ssl_certs=False) as giga:

            # ФИЛЬТР ТЕМЫ
            if not is_dtp_related(giga, query, history_text):
                return {
                    "answer": "Я консультирую только по вопросам ДТП.",
                    "message_id": None,
                    "source": "filter",
                }

            # RAG
            context = get_context(db, feedback_db, query)

            # PLANNER
            plan = build_plan(giga, query, history_text)

            # GENERATE + SELF-CHECK
            answer, confidence = _generate_with_selfcheck(giga, query, context, plan)

            # СОХРАНЕНИЕ
            message_id = str(uuid.uuid4())
            entry = {
                "id": message_id,
                "query": query,
                "answer": answer,
                "confidence": confidence,
                "user_rating": None,
                "source": "llm",
            }
            history.append(entry)
            save_history(user_id, history)

            return {
                "answer": answer,
                "message_id": message_id,
                "source": "llm",
            }

    except Exception as e:
        return {
            "answer": f"Произошла ошибка: {e}",
            "message_id": None,
            "source": "error",
        }


def rate_answer(
    user_id: str,
    message_id: Optional[str],
    rating: int,
    db,
    feedback_db,
) -> None:
    """
    Обрабатывает оценку ответа от пользователя.

    Запускает AI-критика. При высокой оценке (≥4 у пользователя и критика)
    добавляет пару Q&A в базу дообучения.

    Args:
        user_id: ID пользователя
        message_id: ID сообщения (None для template-ответов — пропускаем)
        rating: оценка пользователя от 0 до 5
        db: основная RAG-база
        feedback_db: база дообучения
    """
    if message_id is None:
        # Шаблонные ответы не нуждаются в оценке критиком
        return

    history = load_history(user_id)

    with GigaChat(credentials=GIGA_AUTH, verify_ssl_certs=False) as giga:
        for item in history:
            if item.get("id") != message_id:
                continue

            item["user_rating"] = rating

            score, comment = critic_rate_answer(giga, item["query"], item["answer"])
            item["critic_score"] = score
            item["critic_comment"] = comment

            if rating >= 4 and score >= 4:
                save_good_qa(item["query"], item["answer"])

            break  # нашли нужное сообщение — дальше не ходим

    save_history(user_id, history)


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _build_history_text(history: list) -> str:
    """Формирует текстовый контекст из последних _HISTORY_CONTEXT_SIZE сообщений."""
    return "\n".join(
        f"Q: {h['query']} A: {h['answer']}"
        for h in history[-_HISTORY_CONTEXT_SIZE:]
    )


def _generate_with_selfcheck(giga, query, context, plan):
    answer = "Не знаю"
    confidence = 0.0

    for _ in range(_MAX_IMPROVE_ATTEMPTS):
        raw = generate_answer(giga, query, context, plan, algorithm=_ALGORITHM)
        verdict, conf, _issues, improved = improve_answer(giga, query, raw, context)

        confidence = conf

        if verdict == "GOOD":
            answer = raw
            break
        else:
            answer = improved
            if conf >= _CONFIDENCE_THRESHOLD:
                break

    return answer, confidence


def _save_to_history(
    user_id: str,
    query: str,
    answer: str,
    confidence: float,
    source: str,
) -> None:
    """Сохраняет сообщение в историю без message_id (для template-ответов)."""
    history = load_history(user_id)
    history.append({
        "id": None,
        "query": query,
        "answer": answer,
        "confidence": confidence,
        "user_rating": None,
        "source": source,
    })
    save_history(user_id, history)