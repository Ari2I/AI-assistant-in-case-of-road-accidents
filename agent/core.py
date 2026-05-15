"""
Pipeline v4.4

Изменения vs v4.3:
  - OFFER_EUROPROTOCOL объединён с выбором метода: лимиты + 3 варианта в одном экране
  - OFFER_METHOD убран как пользовательский экран (маппится в OFFER_EUROPROTOCOL)
  - При выборе внешнего метода entry_message возвращается сразу, answer=None невозможен
  - Исправлен баг: process_step3 получает collected_fields, а не final_json
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
from rag.db_manager import get_main_db, get_feedback_db, get_disagreement_db
from templates.matcher import match_template
from agent.step2_europrotocol import process_step2_with_llm, process_step2_check
from agent.step1_stateless import process_step1_with_llm
from agent.disagreement_helper import run_disagreement_help
from agent.step3_insurance import process_step3
from agent.fill_external import (
    process_fill_external,
    _ENTRY_MESSAGE_APP,
    _ENTRY_MESSAGE_PAPER,
)

_CONFIDENCE_THRESHOLD = 0.65
_MAX_IMPROVE_ATTEMPTS = 2

_UNCERTAINTY_MARKERS = [
    "не уверен", "возможно", "наверное", "кажется", "точно не знаю",
    "затрудняюсь", "не могу сказать", "уточните", "не помню",
]

_ALGORITHM = load_algorithm()

# ---------------------------------------------------------------------------
# Ключевые слова выбора метода (используются в OFFER_EUROPROTOCOL)
# ---------------------------------------------------------------------------

_KW_OUR_APP: frozenset[str] = frozenset({
    "1", "наше", "ваше", "здесь", "тут",
    "через вас", "в этом приложении", "через это",
})
_KW_EXT_APP: frozenset[str] = frozenset({
    "2", "другое", "госуслуги", "помощник осаго",
    "помощник", "госуслуги авто", "другое приложение",
})
_KW_PAPER: frozenset[str] = frozenset({
    "3", "бумаг", "бланк", "на бумаге", "бумажный",
})
_KW_REFUSE: frozenset[str] = frozenset({
    "нет", "не хочу", "не буду", "откажусь",
    "гибдд", "no", "вызову гибдд", "отказываюсь",
})


# ---------------------------------------------------------------------------
# Публичный API
# ---------------------------------------------------------------------------

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
    db = db or get_main_db()
    feedback_db = feedback_db or get_feedback_db()
    disagreement_db = disagreement_db or get_disagreement_db()

    if current_step is None or current_step == Step.CONSULTANT_ONLY:
        template_answer = match_template(query)
        if template_answer:
            return _ok(template_answer, "template", None)

    return _route_by_step(
        query=query,
        current_step=current_step,
        history=history,
        slots=slots or {},
        collected_fields=collected_fields or {},
        db=db,
        feedback_db=feedback_db,
        disagreement_db=disagreement_db,
    )


def rate_answer(
    query: str,
    answer: str,
    rating: int,
    feedback_db=None,
) -> dict:
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
# Маршрутизация
# ---------------------------------------------------------------------------

def _route_by_step(
    query: str,
    current_step: str | None,
    history: list,
    slots: dict,
    collected_fields: dict,
    db,
    feedback_db,
    disagreement_db,
) -> dict:

    if current_step == Step.STEP1:
        if slots.get("disagreement_help_active"):
            return _handle_with_error_guard(
                lambda giga: _step_response_to_dict(
                    run_disagreement_help(giga, query, history, slots, disagreement_db),
                    "step1",
                ),
                "disagreement_help",
            )
        return _handle_with_error_guard(
            lambda giga: _step_response_to_dict(
                process_step1_with_llm(giga, query, history, slots),
                "step1",
            ),
            "step1",
        )

    # OFFER_METHOD маппится в тот же обработчик — один экран для пользователя
    if current_step in (Step.OFFER_EUROPROTOCOL, Step.OFFER_METHOD):
        return _run_offer_europrotocol(query, history, slots)

    if current_step == Step.STEP2:
        return _handle_with_error_guard(
            lambda giga: _step_response_to_dict(
                process_step2_with_llm(giga, query, history, slots, collected_fields),
                "step2",
            ),
            "step2",
        )

    if current_step == Step.FILL_EXTERNAL:
        return _handle_with_error_guard(
            lambda giga: _step_response_to_dict(
                process_fill_external(
                    giga, query, history, slots, collected_fields, db, feedback_db
                ),
                "fill_external",
            ),
            "fill_external",
        )

    if current_step == Step.STEP3:
        return _handle_with_error_guard(
            lambda giga: _step_response_to_dict(
                # Исправлен баг: передаём collected_fields, не final_json
                process_step3(giga, query, history, collected_fields, db, feedback_db),
                "step3",
            ),
            "step3",
        )

    if current_step == Step.CONSULTANT_ONLY:
        return _run_consultant(query, history, db, feedback_db)

    print(f"[core] WARNING: unknown current_step={current_step!r}, treating as consultant")
    return _run_consultant(query, history, db, feedback_db)


# ---------------------------------------------------------------------------
# OFFER_EUROPROTOCOL — лимиты + выбор метода в одном экране
# ---------------------------------------------------------------------------

def _run_offer_europrotocol(query: str, history: list, slots: dict) -> dict:
    """
    Единый экран предложения Европротокола.

    Первый вход: показывает лимиты + три варианта.
    Последующие: распознаёт выбор и маршрутизирует напрямую в нужный шаг.
    answer=None никогда не возвращается.
    """
    q = query.strip().lower()

    # --- Отказ ---
    if any(kw in q for kw in _KW_REFUSE):
        return {
            "answer": (
                "Понял. Для оформления ДТП вызовите ГИБДД (102). "
                "Продолжаю работать в режиме консультанта."
            ),
            "source": "offer",
            "category": None,
            "step_completed": True,
            "next_step": Step.CONSULTANT_ONLY,
            "slots": slots,
            "collected_fields": None,
            "final_json": None,
        }

    # --- Наше приложение ---
    if any(kw in q for kw in _KW_OUR_APP):
        prefilled = slots.get("_prefilled", {})
        slots_clean = {k: v for k, v in slots.items() if k != "_prefilled"}
        check_result = process_step2_check(slots_clean, has_app=True)
        return {
            "answer": (
                f"Отлично, начинаем заполнение. {check_result.recommendation}\n\n"
                "Укажите дату и точное время ДТП.\n"
                "Формат: ДД.ММ.ГГГГ ЧЧ:ММ — например, 15.01.2025 14:30"
            ),
            "source": "offer",
            "category": None,
            "step_completed": True,
            "next_step": Step.STEP2,
            "slots": slots_clean,
            "collected_fields": prefilled,
            "final_json": None,
        }

    # --- Стороннее приложение ---
    if any(kw in q for kw in _KW_EXT_APP):
        updated_slots = {**slots, "fill_method": "app_external"}
        return {
            "answer": _ENTRY_MESSAGE_APP,
            "source": "offer",
            "category": None,
            "step_completed": True,
            "next_step": Step.FILL_EXTERNAL,
            "slots": updated_slots,
            "collected_fields": slots.get("_prefilled", {}),
            "final_json": None,
        }

    # --- Бумажный бланк ---
    if any(kw in q for kw in _KW_PAPER):
        updated_slots = {**slots, "fill_method": "paper"}
        return {
            "answer": _ENTRY_MESSAGE_PAPER,
            "source": "offer",
            "category": None,
            "step_completed": True,
            "next_step": Step.FILL_EXTERNAL,
            "slots": updated_slots,
            "collected_fields": slots.get("_prefilled", {}),
            "final_json": None,
        }

    # --- Первый вход или нераспознанный ввод ---
    check_result = process_step2_check(slots, has_app=True)
    base = check_result.limits.get("base", 100_000)

    if base >= 400_000:
        limit_block = (
            "💰 Максимальная выплата:\n"
            "— **400 000 руб.** — с фиксацией через приложение\n"
            "— **100 000 руб.** — без приложения"
        )
    elif base >= 200_000:
        limit_block = (
            "💰 Максимальная выплата:\n"
            "— **200 000 руб.** — с фиксацией через приложение (есть разногласия)\n"
            "— Без приложения при разногласиях — Европротокол невозможен"
        )
    else:
        limit_block = "💰 Максимальная выплата: **100 000 руб.**"

    return {
        "answer": (
            f"Вы можете оформить Европротокол — без вызова ГИБДД.\n\n"
            f"{limit_block}\n\n"
            "Как хотите заполнить протокол?\n\n"
            "**1** — через наше приложение (я помогу заполнить каждое поле)\n"
            "**2** — через другое приложение (Госуслуги.Авто, Помощник ОСАГО)\n"
            "**3** — на бумажном бланке\n\n"
            "Чтобы вызвать ГИБДД — напишите «нет» или «ГИБДД»."
        ),
        "source": "offer",
        "category": None,
        "step_completed": False,
        "next_step": Step.OFFER_EUROPROTOCOL,
        "slots": slots,
        "collected_fields": None,
        "final_json": None,
    }


# ---------------------------------------------------------------------------
# Консультант
# ---------------------------------------------------------------------------

def _run_consultant(query: str, history: list, db, feedback_db) -> dict:
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
        print(f"[core] consultant error: {e}")
        return _ok("Произошла ошибка. Если нужна срочная помощь — звоните 112.", "error", None)


# ---------------------------------------------------------------------------
# Генерация с самопроверкой
# ---------------------------------------------------------------------------

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
    return any(marker in answer.lower() for marker in _UNCERTAINTY_MARKERS)


def _handle_with_error_guard(handler, step_name: str) -> dict:
    try:
        with _make_giga() as giga:
            return handler(giga)
    except Exception as e:
        print(f"[core] {step_name} error: {e}")
        return _step_error_response()


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


def _step_response_to_dict(result: StepResponse, source: str) -> dict:
    slots_out = dict(result.slots or {})
    if result.prefilled_fields:
        slots_out["_prefilled"] = result.prefilled_fields
    return {
        "answer": result.answer,
        "source": source,
        "category": None,
        "step_completed": result.step_completed,
        "next_step": result.next_step,
        "slots": slots_out,
        "collected_fields": result.collected_fields or {},
        "final_json": result.final_json,
    }


def _step_error_response() -> dict:
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