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
from agent.disagreement_helper import run_disagreement_help
from agent.step3_insurance import process_step3


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


def _looks_like_step_answer(query: str) -> bool:
    """
    Короткий ответ в контексте шага — почти наверняка ответ на вопрос,
    а не самостоятельный общий вопрос. Пропускаем meta_classify.
    """
    q = query.strip().lower().rstrip("!.,")
    words = q.split()
    if len(words) <= 3:
        return True
    starts = ("да ", "нет ", "ага ", "нету ", "есть ", "нет,", "да,")
    if any(q.startswith(s) for s in starts):
        return True
    return False


def run_agent(
    query: str,
    current_step: str | None = None,
    history: list | None = None,
    slots: dict | None = None,
    collected_fields: dict | None = None,
    db=None,
    feedback_db=None,
    disagreement_db=None,
) -> dict:

    history = history or []

    # ШАГ 0: Шаблоны — всегда первыми
    template_answer = match_template(query)
    if template_answer:
        return _ok(template_answer, "template", None)

    # ШАГ 1: Шаговый режим
    if current_step in (Step.STEP1, "step1"):
        if slots and slots.get("disagreement_help_active"):
            try:
                with _make_giga() as giga:
                    result = run_disagreement_help(
                        giga, query, history, slots, disagreement_db
                    )
                return _step_response_to_dict(result, "step1")
            except Exception as e:
                print(f"[core] disagreement_help error: {e}")
                return _step_error_response()

        general_result = _try_handle_as_general_question(query, history, db, feedback_db)
        if general_result:
            return general_result

        try:
            with _make_giga() as giga:
                result = _run_step1(giga, query, history, slots or {})
            return _step_response_to_dict(result, "step1")
        except Exception as e:
            print(f"[core] step1 error: {e}")
            return _step_error_response()

    if current_step in (Step.STEP2, "step2"):
        general_result = _try_handle_as_general_question(query, history, db, feedback_db)
        if general_result:
            return general_result

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

    if current_step in (Step.OFFER_EUROPROTOCOL, "offer_europrotocol"):
        return _run_offer_europrotocol(query, history, slots or {})

    if current_step in (Step.STEP3, "step3"):
        try:
            with _make_giga() as giga:
                result = process_step3(
                    giga, query, history,
                    collected_fields, db, feedback_db
                )
            return _step_response_to_dict(result, "step3")
        except Exception as e:
            print(f"[core] step3 error: {e}")
            return _step_error_response()

    if current_step in (Step.CONSULTANT_ONLY, "consultant_only"):
        return _run_general_consultant(query, history, db, feedback_db)

    # Fallback — нет current_step или неизвестный шаг
    return _ok(
        "Я консультирую по вопросам оформления ДТП. Опишите вашу ситуацию.",
        "filter",
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


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

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


def _try_handle_as_general_question(
    query: str,
    history: list,
    db,
    feedback_db,
) -> dict | None:
    """
    Проверяет, является ли запрос общим вопросом (не ответом на текущий шаг).
    Если да — генерирует ответ и возвращает его.
    Если нет или произошла ошибка — возвращает None.
    """
    if _looks_like_step_answer(query):
        return None

    try:
        with _make_giga() as giga:
            classifier_history = build_history(history, component="classifier")
            meta = meta_classify(giga, query, classifier_history)

            if meta["category"] != "general_questions":
                return None

            context = get_context_for_category(db, feedback_db, query, "general_questions")
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
                algorithm_slice="",
                generator_history=generator_history,
            )
            return _ok(answer, "llm", "general_questions")

    except Exception as e:
        print(f"[core] general question check error: {e}")
        return None


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


def _run_step1(giga: GigaChat, query: str, history: list, slots: dict) -> StepResponse:
    """Делегирует в step1_stateless.process_step1_with_llm()."""
    return process_step1_with_llm(giga, query, history, slots)


def _run_step2(
    giga: GigaChat,
    query: str,
    history: list,
    slots: dict,
    collected_fields: dict,
) -> StepResponse:
    """Делегирует в step2_europrotocol.process_step2_with_llm()."""
    return process_step2_with_llm(giga, query, history, slots, collected_fields)


def _step_response_to_dict(result: StepResponse, source: str) -> dict:
    """Преобразует StepResponse в dict для возврата бэкенду."""
    return {
        "answer": result.answer,
        "source": source,
        "category": None,
        "step_completed": result.step_completed,
        "next_step": result.next_step,
        "slots": result.slots or {},
        "collected_fields": result.collected_fields or {},
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


def _run_offer_europrotocol(query: str, history: list, slots: dict) -> dict:
    q = query.strip().lower()
    AGREE  = {"да", "хочу", "давайте", "готов", "заполним", "ок", "ok", "yes"}
    REFUSE = {"нет", "не хочу", "не буду", "откажусь", "гибдд", "no"}

    if any(kw in q for kw in AGREE):
        return {
            "answer": "Отлично, начинаем заполнение Европротокола.",
            "source": "offer",
            "category": None,
            "step_completed": True,
            "next_step": Step.STEP2,
            "slots": slots,
            "collected_fields": {},
            "final_json": None,
        }

    if any(kw in q for kw in REFUSE):
        return {
            "answer": (
                "Понял. Для оформления ДТП вам необходимо вызвать ГИБДД (102). "
                "Я продолжу отвечать на ваши вопросы в режиме консультанта."
            ),
            "source": "offer",
            "category": None,
            "step_completed": True,
            "next_step": Step.CONSULTANT_ONLY,
            "slots": slots,
            "collected_fields": None,
            "final_json": None,
        }

    return {
        "answer": (
            "Скажите, пожалуйста: хотите заполнить Европротокол сейчас, "
            "или предпочтёте вызвать ГИБДД?"
        ),
        "source": "offer",
        "category": None,
        "step_completed": False,
        "next_step": Step.OFFER_EUROPROTOCOL,
        "slots": slots,
        "collected_fields": None,
        "final_json": None,
    }


def _run_general_consultant(
    query: str,
    history: list,
    db,
    feedback_db,
) -> dict:
    """
    Режим консультанта без шагового сценария.
    Пользователь отказался от заполнения протокола.
    """
    try:
        with _make_giga() as giga:
            classifier_history = build_history(history, component="classifier")
            meta = meta_classify(giga, query, classifier_history)
            category = meta.get("category", "first_steps")
            block = meta.get("block", 0)

            context = get_context_for_category(db, feedback_db, query, category)
            algorithm_slice = get_algorithm_slice(block) if block >= 0 else ""
            generator_history = build_history(
                history, component="generator", category=category
            )
            plan = {"category": category, "block": block}
            answer, _ = _generate_with_selfcheck(
                giga, query, context, plan, algorithm_slice, generator_history
            )

        return _ok(answer, "llm", category)
    except Exception as e:
        print(f"[core] consultant_only error: {e}")
        return _ok(
            "Произошла ошибка. Если нужна срочная помощь — звоните 112.",
            "error",
            None,
        )