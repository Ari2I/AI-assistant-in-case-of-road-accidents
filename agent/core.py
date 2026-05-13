"""
Pipeline v4.2 — удаление general режима.

Изменения vs v4.1:
  - Удалён Step.GENERAL — агент работает только по шагам (step1, step2, step3)
  - Агент одновременно является консультантом по вопросам ДТП и ПДД на каждом шаге
  - Функция _try_handle_as_general_question удалена — общие вопросы обрабатываются
    в контексте текущего шага через meta_classifier и RAG
  - current_step=None больше не вызывает _run_general_consultant — это ошибка состояния
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


_CONFIDENCE_THRESHOLD = 0.65
_MAX_IMPROVE_ATTEMPTS = 2

_UNCERTAINTY_MARKERS = [
    "не уверен", "возможно", "наверное", "кажется", "точно не знаю",
    "затрудняюсь", "не могу сказать", "уточните", "не помню",
]

# Алгоритм загружается один раз при старте модуля
_ALGORITHM = load_algorithm()


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
    """
    Основная точка входа агента.

    Django передаёт инициализированные базы через параметры db/feedback_db/disagreement_db.
    При локальном запуске (None) используется db_manager как fallback.
    """
    history = history or []

    # Fallback к db_manager, если Django не передал базы
    db = db or get_main_db()
    feedback_db = feedback_db or get_feedback_db()
    disagreement_db = disagreement_db or get_disagreement_db()

    # ШАГ 0: шаблоны — проверяем первыми, без вызова LLM
    template_answer = match_template(query)
    if template_answer:
        return _ok(template_answer, "template", None)

    # ШАГ 1: маршрутизация по текущему шагу сценария
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
    """
    Запускает AI-критика. При высоких оценках сохраняет Q&A в базу дообучения.

    Args:
        query:       вопрос пользователя (из БД бэкенда)
        answer:      ответ агента (из БД бэкенда)
        rating:      оценка пользователя 0–5
        feedback_db: база дообучения (опционально, используется менеджер как fallback)
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
    """Направляет запрос к нужному обработчику в зависимости от current_step."""

    # --- STEP 1: сбор фактов ---
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

    # --- STEP 2: заполнение Европротокола ---
    if current_step == Step.STEP2:

        return _handle_with_error_guard(
            lambda giga: _step_response_to_dict(
                process_step2_with_llm(giga, query, history, slots, collected_fields),
                "step2",
            ),
            "step2",
        )

    # --- Предложение заполнить Европротокол ---
    if current_step == Step.OFFER_EUROPROTOCOL:
        return _run_offer_europrotocol(query, history, slots)

    # --- STEP 3: помощь со страховой ---
    if current_step == Step.STEP3:
        return _handle_with_error_guard(
            lambda giga: _step_response_to_dict(
                process_step3(giga, query, history, collected_fields, db, feedback_db),
                "step3",
            ),
            "step3",
        )

    # --- Режим консультанта (пользователь отказался от Европротокола) ---
    if current_step == Step.CONSULTANT_ONLY:
        return _run_consultant(query, history, db, feedback_db)

    # --- current_step is None или неизвестное значение ---
    # Ошибка состояния: должен быть установлен один из шагов или CONSULTANT_ONLY
    print(f"[core] WARNING: unknown current_step={current_step!r}, treating as consultant")
    return _run_consultant(query, history, db, feedback_db)


# ---------------------------------------------------------------------------
# Обработчики шагов
# ---------------------------------------------------------------------------

def _run_offer_europrotocol(query: str, history: list, slots: dict) -> dict:
    q = query.strip().lower()
    AGREE  = {"да", "хочу", "давайте", "готов", "заполним", "ок", "ok", "yes"}
    REFUSE = {"нет", "не хочу", "не буду", "откажусь", "гибдд", "no"}

    if any(kw in q for kw in AGREE):
        # Запускаем проверку Европротокола с учётом наличия приложения
        # has_app=True по умолчанию — если пользователь не указал иное,
        # считаем что приложение доступно (он может использовать «Помощник ОСАГО»)
        check_result = process_step2_check(slots, has_app=True)

        # Формируем ответ с конкретным лимитом выплаты
        limits = check_result.limits
        if limits:
            base_limit = limits.get("base", 0)
            if base_limit >= 400_000:
                limit_text = "400 000 руб."
            elif base_limit >= 200_000:
                limit_text = "200 000 руб."
            else:
                limit_text = "100 000 руб."
        else:
            limit_text = "100 000 руб."
        return {
            "answer": (
                f"Отлично, начинаем заполнение Европротокола. "
                f"Ваш максимальный лимит выплаты — {limit_text}. "
                f"{check_result.recommendation}"
            ),
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

    # Первое обращение к OFFER_EUROPROTOCOL — показываем предложение с лимитом
    # Вычисляем лимит заранее, чтобы пользователь знал условия
    check_result = process_step2_check(slots, has_app=True)
    limits = check_result.limits
    if limits:
        base_limit = limits.get("base", 0)
        if base_limit >= 400_000:
            limit_text = "400 000 руб."
        elif base_limit >= 200_000:
            limit_text = "200 000 руб."
        else:
            limit_text = "100 000 руб."
    else:
        limit_text = "100 000 руб."
    return {
        "answer": (
            f"Вы можете оформить Европротокол. Максимальная выплата — до {limit_text}. "
            f"Хотите заполнить его сейчас или предпочтёте вызвать ГИБДД?"
        ),
        "source": "offer",
        "category": None,
        "step_completed": False,
        "next_step": Step.OFFER_EUROPROTOCOL,
        "slots": slots,
        "collected_fields": None,
        "final_json": None,
    }


def _run_consultant(
    query: str,
    history: list,
    db,
    feedback_db,
) -> dict:
    """
    Режим консультанта по вопросам ДТП и ПДД.
    Используется при CONSULTANT_ONLY и как fallback для неизвестных current_step.

    Агент классифицирует вопрос через meta_classifier и отвечает на основе RAG-контекста.
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
        print(f"[core] consultant error: {e}")
        return _ok(
            "Произошла ошибка. Если нужна срочная помощь — звоните 112.",
            "error",
            None,
        )

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


def _looks_like_step_answer(query: str) -> bool:
    """Короткий ответ в контексте шага — скорее всего ответ, а не самостоятельный вопрос."""
    q = query.strip().lower().rstrip("!.,")
    if len(q.split()) <= 3:
        return True
    starts = ("да ", "нет ", "ага ", "нету ", "есть ", "нет,", "да,")
    return any(q.startswith(s) for s in starts)


def _should_run_selfcheck(answer: str) -> bool:
    """Запускаем self_check только при явных маркерах неуверенности."""
    answer_lower = answer.lower()
    return any(marker in answer_lower for marker in _UNCERTAINTY_MARKERS)


def _handle_with_error_guard(handler, step_name: str) -> dict:
    """
    Вызывает handler(giga) в контексте GigaChat.
    При любой ошибке возвращает безопасный ответ.
    """
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
    """Безопасный ответ при ошибке шагового режима."""
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