"""
Основной pipeline AI-агента.

История диалога передаётся снаружи при каждом запросе — бэкенд
хранит её сам и передаёт списком. Агент ничего не сохраняет локально.
"""

from gigachat import GigaChat

from config import GIGA_AUTH
from rag.retrieval import get_context
from rag.feedback_db import save_good_qa

from agent.planner import build_plan
from agent.generator import generate_answer
from agent.filter import is_dtp_related
from evaluation.self_check import improve_answer
from evaluation.critic import critic_rate_answer
from templates.matcher import match_template

_CONFIDENCE_THRESHOLD = 0.7
_MAX_IMPROVE_ATTEMPTS = 2
_HISTORY_CONTEXT_SIZE = 3


def run_agent(query: str, history=None, db=None, feedback_db=None) -> dict:
    """
    Обрабатывает сообщение пользователя и возвращает ответ.

    Args:
        query: сообщение пользователя
        history: история диалога от бэкенда, список вида:
                 [{"query": "...", "answer": "..."}, ...]
        db: основная RAG-база (может быть None)
        feedback_db: база дообучения (может быть None)

    Returns:
        {"answer": "...", "source": "template" | "llm" | "filter" | "error"}
    """
    history_text = _build_history_text(history or [])

    # ШАГ 0: Regex-whitelist — без LLM, мгновенно
    template_answer = match_template(query)
    if template_answer:
        return {"answer": template_answer, "source": "template"}

    try:
        with _make_giga() as giga:

            # ШАГ 1: LLM-классификатор шаблонов (один вызов, дешевле полного pipeline)
            # Передаём giga — теперь matcher использует его для классификации
            template_answer = match_template(query, giga=giga, history_text=history_text)
            if template_answer:
                return {"answer": template_answer, "source": "template"}

            # ФИЛЬТР ТЕМЫ
            if not is_dtp_related(giga, query, history_text):
                return {
                    "answer": "Я консультирую только по вопросам ДТП.",
                    "source": "filter",
                }

            # RAG
            context = get_context(db, feedback_db, query)

            # PLANNER
            plan = build_plan(giga, query, history_text)

            # GENERATE + SELF-CHECK
            answer, _ = _generate_with_selfcheck(giga, query, context, plan)

            return {"answer": answer, "source": "llm"}

    except Exception as e:
        return {"answer": f"Произошла ошибка: {e}", "source": "error"}


def rate_answer(
    query: str,
    answer: str,
    rating: int,
    feedback_db=None,
) -> dict:
    """
    Запускает AI-критика и при хорошей оценке дообучает RAG.

    Бэкенд сам достаёт query и answer из своей БД по message_id
    и передаёт сюда.

    Args:
        query: вопрос пользователя
        answer: ответ агента
        rating: оценка пользователя от 0 до 5
        feedback_db: база дообучения (может быть None)

    Returns:
        {"critic_score": 1-5, "critic_comment": "..."}
    """
    with _make_giga() as giga:
        score, comment = critic_rate_answer(giga, query, answer)

    if rating >= 4 and score >= 4:
        save_good_qa(query, answer)

    return {"critic_score": score, "critic_comment": comment}


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _make_giga() -> GigaChat:
    return GigaChat(credentials=GIGA_AUTH, verify_ssl_certs=False, scope="GIGACHAT_API_B2B")


def _build_history_text(history: list) -> str:
    return "\n".join(
        f"Q: {h['query']} A: {h['answer']}"
        for h in history[-_HISTORY_CONTEXT_SIZE:]
    )


def _generate_with_selfcheck(giga: GigaChat, query: str, context: str, plan: dict):
    answer = "Не знаю"
    confidence = 0.0

    for _ in range(_MAX_IMPROVE_ATTEMPTS):
        raw = generate_answer(giga, query, context, plan)
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