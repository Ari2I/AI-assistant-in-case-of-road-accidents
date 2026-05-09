"""
Pipeline v4.0 — оптимизированный по токенам.

Изменения vs v3.0:
  - filter + classifier + planner → один вызов (meta_classifier)
  - генератор получает только нужный блок алгоритма, не весь (~400 вместо ~3000 токенов)
  - self_check запускается только если ответ содержит маркеры неуверенности

Было: до 5 LLM-вызовов, ~10 000 токенов
Стало: 2-3 LLM-вызова, ~4 000-5 000 токенов
"""

from gigachat import GigaChat

from config import GIGA_AUTH
from agent.meta_classifier import meta_classify
from agent.step_types import Step, StepResponse
from agent.retriever import get_context_for_category
from agent.generator import generate_answer
from agent.algorithm import load_algorithm, get_algorithm_slice
from agent.history import build_history
from evaluation.self_check import improve_answer
from evaluation.critic import critic_rate_answer
from rag.feedback_db import save_good_qa
from templates.matcher import match_template
from agent.step2_europrotocol import process_step2_with_llm
from agent.step1_stateless import process_step1_with_llm

_CONFIDENCE_THRESHOLD = 0.65
_MAX_IMPROVE_ATTEMPTS = 2

# Маркеры неуверенности в ответе — если есть, запускаем self_check
# Иначе пропускаем (~2500 токенов экономии на уверенных ответах)
_UNCERTAINTY_MARKERS = [
    "не уверен", "возможно", "наверное", "кажется", "точно не знаю",
    "затрудняюсь", "не могу сказать", "уточните", "не помню",
]

# Алгоритм загружается один раз при старте — не читаем файл на каждый запрос
_ALGORITHM = load_algorithm()


def run_agent(
    query: str,
    current_step: str | None = None,
    history: list | None = None,
    slots: dict | None = None,
    collected_fields: dict | None = None,
    db=None,
    feedback_db=None,
) -> dict:
    """
    Обрабатывает сообщение пользователя и возвращает ответ.

    Args:
        query:       сообщение пользователя
        current_step: текущий шаг ("general", "step1", "step2", "done", "call_gibdd")
        history:     история диалога [{"query": ..., "answer": ...}, ...]
        slots:       собранные слоты для step1/step2
        collected_fields: собранные поля для europrotocol
        db:          основная ChromaDB (может быть None)
        feedback_db: база дообучения (может быть None)

    Returns:
        {
            "answer":   str,
            "source":   str,   # "template" | "llm" | "filter" | "error" | "step1" | "step2"
            "category": str | None,
            "step_completed": bool,
            "next_step": str | None,
            "slots": dict | None,
            "collected_fields": dict | None,
            "final_json": dict | None,
        }
    """
    history = history or []

    # --- Проверка на общий вопрос (приоритет над шаговым режимом) ---
    # Даже если мы в step1 или step2, общие вопросы обрабатываются через RAG
    try:
        with _make_giga() as giga:
            classifier_history = build_history(history, component="classifier")
            meta = meta_classify(giga, query, classifier_history)

            # Если распознан общий вопрос — отвечаем через RAG, не прерывая шаг
            if meta["category"] == "general_questions":
                context = get_context_for_category(db, feedback_db, query, "general_questions")

                # План для общего вопроса — без привязки к блоку алгоритма
                plan = {
                    "category": "general_questions",
                    "stage": "general_questions",
                    "answer_type": "info",
                    "algorithm_block": -1,
                }

                generator_history = build_history(
                    history, component="generator", category="general_questions"
                )

                answer, _ = _generate_with_selfcheck(
                    giga, query, context, plan,
                    algorithm_slice="",  # Нет блока алгоритма для общих вопросов
                    generator_history=generator_history,
                )

                return _ok(answer, "llm", "general_questions")

    except Exception as e:
        print(f"[core] general question check error: {e}")
        # Продолжаем работу, если проверка на общий вопрос упала

    # --- Шаговый режим (если не общий вопрос) ---
    if current_step in (Step.STEP1, "step1"):
        try:
            with _make_giga() as giga:
                result = _run_step1(giga, query, history, slots or {})
            return _step_response_to_dict(result, "step1")
        except Exception as e:
            print(f"[core] step1 error: {e}")
            return _step_error_response()

    if current_step in (Step.STEP2, "step2"):
        try:
            with _make_giga() as giga:
                result = _run_step2(
                    giga, query, history,
                    slots or {}, collected_fields or {}
                )
            return _step_response_to_dict(result, "step2")
        except Exception as e:
            print(f"[core] step2 error: {e}")
            return _step_error_response()

    # --- Иначе: существующий general-пайплайн ---

    # ШАГ 1: Regex-шаблоны (0 токенов, мгновенно)
    template_answer = match_template(query)
    if template_answer:
        return _ok(template_answer, "template", None)

    try:
        with _make_giga() as giga:

            # ШАГ 2: Один вызов вместо трёх (filter + classifier + planner)
            category = meta["category"]
            block = meta["block"]

            if not meta["relevant"]:
                return _ok(
                    "Я консультирую только по вопросам ДТП и ОСАГО. "
                    "Если у вас произошла авария — опишите ситуацию.",
                    "filter",
                    None,
                )


            # ШАГ 3: RAG — контекст по категории
            context = get_context_for_category(db, feedback_db, query, category)

            # ШАГ 4: Только нужный блок алгоритма ± 1 соседний
            algorithm_slice = get_algorithm_slice(block, window=1)

            plan = {
                "category": category,
                "stage": category,
                "answer_type": "steps",
                "algorithm_block": block,
            }

            # ШАГ 5: Генерация с условной самопроверкой
            generator_history = build_history(
                history, component="generator", category=category
            )
            answer, _ = _generate_with_selfcheck(
                giga, query, context, plan,
                algorithm_slice, generator_history,
            )

            return _ok(answer, "llm", category)

    except Exception as e:
        print(f"[core] pipeline error: {e}")
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

        if rating >= 4 and score >= 4:
            save_good_qa(query, answer)

        return {"critic_score": score, "critic_comment": comment}

    except Exception as e:
        print(f"[core] rate_answer error: {e}")
        return {"critic_score": 3, "critic_comment": "Ошибка оценки"}


def _make_giga() -> GigaChat:
    return GigaChat(
        credentials=GIGA_AUTH,
        verify_ssl_certs=False,
        scope="GIGACHAT_API_B2B",
    )


def _should_run_selfcheck(answer: str) -> bool:
    """Запускаем self_check только при явных маркерах неуверенности."""
    answer_lower = answer.lower()
    return any(marker in answer_lower for marker in _UNCERTAINTY_MARKERS)


def _generate_with_selfcheck(
    giga: GigaChat,
    query: str,
    context: str,
    plan: dict,
    algorithm_slice: str,
    generator_history: str,
) -> tuple[str, float]:
    raw = generate_answer(
        giga, query, context, plan,
        algorithm=algorithm_slice,
        history_text=generator_history,
    )

    if not _should_run_selfcheck(raw):
        return raw, 1.0

    for attempt in range(_MAX_IMPROVE_ATTEMPTS):
        verdict, conf, issues, improved = improve_answer(giga, query, raw, context)

        if verdict == "GOOD":
            return raw, conf

        raw = improved
        if issues:
            print(f"[core] self-check attempt {attempt + 1}: {issues[:80]}")

        if conf >= _CONFIDENCE_THRESHOLD:
            break

    return raw, 0.0


def _ok(answer: str, source: str, category: str | None) -> dict:
    return {
        "answer": answer,
        "source": source,
        "category": category,
        "step_completed": False,
        "next_step": None,
        "slots": None,
        "collected_fields": None,
        "final_json": None,
    }

# ---------------------------------------------------------------------------
# Вспомогательные функции для шагового режима
# ---------------------------------------------------------------------------

def _run_step1(giga, query: str, history: list, slots: dict) -> StepResponse:
    """Делегирует в step1_stateless.process_step1_with_llm()."""

    return process_step1_with_llm(giga, query, history, slots)

def _run_step2(
        giga,
        query: str,
        history: list,
        slots: dict,
        collected_fields: dict,
) -> StepResponse:
    """Делегирует в step2_europrotocol.process_step2_with_llm()."""


    return process_step2_with_llm(
        giga,
        query,
        history,
        slots,
        collected_fields,
    )

def _step_response_to_dict(result: StepResponse, source: str) -> dict:
    """Преобразует StepResponse в dict для возврата бэкенду."""
    return {
        "answer": result.answer,
        "source": source,
        "category": None,
        "step_completed": result.step_completed,
        "next_step": result.next_step,
        "slots": result.slots,
        "collected_fields": result.collected_fields,
        "final_json": result.final_json,
    }

def _step_error_response() -> dict:
    """Возвращает безопасный ответ при ошибке шагового режима."""
    return {
        "answer": (
            "Произошла техническая ошибка. "
            "Если вы в опасной ситуации — немедленно звоните 112."
        ),
        "source": "error",
        "category": None,
        "step_completed": False,
        "next_step": Step.STEP1,
        "slots": {},
        "collected_fields": {},
        "final_json": None,
    }