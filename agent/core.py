"""
Основной pipeline AI-агента — версия 3.0.

Pipeline:
  1. Regex-шаблоны    — строгие, без LLM, мгновенно
  2. Фильтр темы      — LLM, один вызов
  3. Классификатор    — LLM, определяет категорию из 5
  4. RAG (по категории) — ChromaDB с целевыми запросами
  5. Генерация        — LLM с категорийным промптом
  6. Самопроверка     — LLM, перегенерация если плохо
  7. Возврат ответа

История диалога передаётся снаружи — бэкенд хранит её сам.
GigaChat-клиент создаётся ОДИН РАЗ за запрос и переиспользуется.
Алгоритм загружается ОДИН РАЗ при старте модуля.
"""

from gigachat import GigaChat

from config import GIGA_AUTH
from agent.filter import is_dtp_related
from agent.classifier import classify_intent, CATEGORIES
from agent.retriever import get_context_for_category
from agent.generator import generate_answer
from agent.planner import build_plan
from agent.algorithm import load_algorithm
from agent.history import build_history
from evaluation.self_check import improve_answer
from evaluation.critic import critic_rate_answer
from rag.feedback_db import save_good_qa
from templates.matcher import match_template

# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------
_CONFIDENCE_THRESHOLD = 0.65
_MAX_IMPROVE_ATTEMPTS = 2

# Алгоритм загружается один раз при старте — не читаем файл на каждый запрос
_ALGORITHM = load_algorithm()


# ---------------------------------------------------------------------------
# Публичный API
# ---------------------------------------------------------------------------

def run_agent(
    query: str,
    history: list | None = None,
    db=None,
    feedback_db=None,
) -> dict:
    """
    Обрабатывает сообщение пользователя и возвращает ответ.

    Args:
        query:       сообщение пользователя
        history:     история диалога [{"query": ..., "answer": ...}, ...]
        db:          основная ChromaDB (может быть None)
        feedback_db: база дообучения (может быть None)

    Returns:
        {
            "answer":   str,   # текст ответа
            "source":   str,   # "template" | "llm" | "filter" | "error"
            "category": str | None  # категория запроса (для дебага/аналитики)
        }
    """
    history = history or []

    # ── ШАГ 1: Regex-шаблоны (без LLM, без истории) ─────────────────────────
    template_answer = match_template(query)
    if template_answer:
        return _ok(template_answer, "template", None)

    # ── ШАГ 2–6: LLM pipeline ───────────────────────────────────────────────
    try:
        with _make_giga() as giga:

            # ШАГ 2: Фильтр темы
            # Последние 2 реплики — достаточно чтобы понять, не сменил ли
            # пользователь тему. Вся история здесь избыточна.
            filter_history = build_history(history, component="filter")
            if not is_dtp_related(giga, query, filter_history):
                return _ok(
                    "Я консультирую только по вопросам ДТП и ОСАГО. "
                    "Если у вас произошла авария — опишите ситуацию.",
                    "filter",
                    None,
                )

            # ШАГ 3: Классификация намерения
            # 5 реплик — нужно отследить переходы между этапами диалога.
            classifier_history = build_history(history, component="classifier")
            category = classify_intent(giga, query, classifier_history)

            # ШАГ 4: Контекст из RAG (сфокусированный на категории)
            context = get_context_for_category(db, feedback_db, query, category)

            # ШАГ 5: Планировщик — определяет текущий блок алгоритма
            # 4 реплики — свежий контекст, старые ветки только мешают.
            planner_history = build_history(history, component="planner")
            plan = build_plan(giga, query, planner_history)
            plan["category"] = category

            # ШАГ 6: Генерация с самопроверкой
            # История адаптирована под категорию:
            #   filling_europrotocol → вся история + структурированный блок данных
            #   остальные → 3–7 реплик в зависимости от категории
            generator_history = build_history(history, component="generator", category=category)
            answer, _ = _generate_with_selfcheck(giga, query, context, plan, generator_history)

            return _ok(answer, "llm", category)

    except Exception as e:
        print(f"[core] pipeline error: {e}")
        # Безопасный fallback: не оставляем пользователя без помощи
        return _ok(
            "Произошла техническая ошибка. "
            "Если вы в опасной ситуации — немедленно звоните 112. "
            "Попробуйте повторить вопрос через несколько секунд.",
            "error",
            None,
        )


def rate_answer(
    query: str,
    answer: str,
    rating: int,
    feedback_db=None,
) -> dict:
    """
    Запускает AI-критика и при высоких оценках дообучает RAG.

    Args:
        query:       вопрос пользователя (из БД бэкенда)
        answer:      ответ агента (из БД бэкенда)
        rating:      оценка пользователя 0–5
        feedback_db: база дообучения

    Returns:
        {"critic_score": int, "critic_comment": str}
    """
    try:
        with _make_giga() as giga:
            score, comment = critic_rate_answer(giga, query, answer)

        # Сохраняем только если ОБА — пользователь И критик — оценили высоко
        if rating >= 4 and score >= 4:
            save_good_qa(query, answer)

        return {"critic_score": score, "critic_comment": comment}

    except Exception as e:
        print(f"[core] rate_answer error: {e}")
        return {"critic_score": 3, "critic_comment": "Ошибка оценки"}


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _make_giga() -> GigaChat:
    """Создаёт клиент GigaChat. Используется как контекстный менеджер."""
    return GigaChat(
        credentials=GIGA_AUTH,
        verify_ssl_certs=False,
        scope="GIGACHAT_API_B2B",
    )


def _generate_with_selfcheck(
    giga: GigaChat,
    query: str,
    context: str,
    plan: dict,
    generator_history: str,
) -> tuple[str, float]:
    """
    Генерирует ответ и проверяет его качество.

    generator_history — уже отформатированная адаптивная история
    (для filling_europrotocol это вся история + блок данных,
    для остальных — последние N реплик).

    self_check получает укороченную историю (3 реплики) — ему не нужен
    весь контекст, только проверка на противоречие последним репликам.
    """
    answer = "Не могу ответить на этот вопрос. Попробуйте уточнить ситуацию."
    confidence = 0.0

    for attempt in range(_MAX_IMPROVE_ATTEMPTS):
        raw = generate_answer(
            giga, query, context, plan,
            algorithm=_ALGORITHM,
            history_text=generator_history,
        )
        verdict, conf, issues, improved = improve_answer(giga, query, raw, context)

        confidence = conf

        if verdict == "GOOD":
            return raw, conf

        answer = improved
        if issues:
            print(f"[core] self-check attempt {attempt+1}: {issues[:80]}")

        if conf >= _CONFIDENCE_THRESHOLD:
            break

    return answer, confidence


def _ok(answer: str, source: str, category: str | None) -> dict:
    """Формирует стандартный dict ответа."""
    return {"answer": answer, "source": source, "category": category}