"""
Pipeline v4.5

Исправления v4.5.1:
  - rate_answer: переданный feedback_db теперь действительно используется
    при сохранении хорошего Q&A (раньше параметр объявлялся, но игнорировался).

Исправления v4.5.2:
  - _make_giga(): один экземпляр GigaChat создаётся в run_agent и передаётся
    параметром во все вложенные функции. Раньше каждый _handle_with_error_guard
    создавал отдельное TCP-соединение, итого 2–3 соединения на один запрос.
  - _handle_with_error_guard переименован в _safe_call и больше не создаёт giga.
  - _answer_step_question, _inject_rag_if_question, _run_consultant,
    _route_by_step — принимают giga как параметр.
"""

from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

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
from agent.input_filter import filter_input, INJECTION_BLOCKED_MSG, OFFTOPIC_BLOCKED_MSG
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
# RAG для вопросов в step1/step2
# ---------------------------------------------------------------------------

_QUESTION_STARTS: tuple[str, ...] = (
    "что ", "как ", "когда ", "зачем ", "почему ", "можно ",
    "нужно ", "обязательно ", "куда ", "где ", "кто ", "чем ",
    "должен ", "должна ", "надо ", "стоит ", "следует ",
    "расскажи", "объясни", "поясни", "сколько ",
    "правильно ли", "верно ли", "обязан ли", "нужно ли",
)

_STEP_QUESTION_SYSTEM = """\
Ты — ДТП-ассистент. Пользователь задаёт вопрос в процессе оформления ДТП.
Дай краткий конкретный ответ, опираясь только на контекст из базы знаний.
Если ответа в контексте нет — скажи об этом одним предложением.
Не задавай уточняющих вопросов.

Контекст из базы знаний:
{context}
"""


def _looks_like_question(query: str) -> bool:
    """Детерминированная проверка — содержит ли сообщение вопрос."""
    q = query.strip().lower()
    if "?" in q:
        return True
    return any(q.startswith(s) for s in _QUESTION_STARTS)


def _answer_step_question(
    giga: GigaChat,
    query: str,
    db,
    feedback_db,
    category: str,
) -> str | None:
    """
    Отвечает на вопрос пользователя через RAG.
    Использует переданный экземпляр giga — не создаёт новый.
    При любой ошибке возвращает None — не блокирует основной flow.
    """
    try:
        context = get_context_for_category(db, feedback_db, query, category)
        payload = Chat(
            messages=[
                Messages(
                    role=MessagesRole.SYSTEM,
                    content=_STEP_QUESTION_SYSTEM.format(context=context),
                ),
                Messages(role=MessagesRole.USER, content=query),
            ],
            temperature=0.1,
        )
        response = giga.chat(payload)
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[core] step question error: {e}")
        return None


def _inject_rag_if_question(
    giga: GigaChat,
    query: str,
    step_result: dict,
    db,
    feedback_db,
    category: str,
) -> dict:
    """
    Если запрос содержит вопрос и шаг ещё не завершён —
    добавляет RAG-ответ перед вопросом агента.
    Использует переданный экземпляр giga.
    """
    if (
        _looks_like_question(query)
        and not step_result.get("step_completed")
        and step_result.get("answer")
    ):
        rag_answer = _answer_step_question(giga, query, db, feedback_db, category)
        if rag_answer:
            step_result = dict(step_result)
            step_result["answer"] = (
                rag_answer + "\n\n---\n\n" + step_result["answer"]
            )
    return step_result


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
    Главная точка входа агента.

    Создаёт ОДИН экземпляр GigaChat на весь вызов и передаёт его
    во все вложенные функции. Это предотвращает создание 2–3 отдельных
    TCP-соединений на один запрос пользователя.
    """
    history = history or []
    db = db or get_main_db()
    feedback_db = feedback_db or get_feedback_db()
    disagreement_db = disagreement_db or get_disagreement_db()

    is_blocked, reason, query = filter_input(query)
    if is_blocked:
        return _ok(
            INJECTION_BLOCKED_MSG if reason == "injection" else OFFTOPIC_BLOCKED_MSG,
            "filter",
            None,
        )

    # Шаблонные ответы не требуют LLM — возвращаем до создания соединения
    if current_step is None or current_step == Step.CONSULTANT_ONLY:
        template_answer = match_template(query)
        if template_answer:
            return _ok(template_answer, "template", None)

    try:
        with _make_giga() as giga:
            return _route_by_step(
                giga=giga,
                query=query,
                current_step=current_step,
                history=history,
                slots=slots or {},
                collected_fields=collected_fields or {},
                db=db,
                feedback_db=feedback_db,
                disagreement_db=disagreement_db,
            )
    except Exception as e:
        print(f"[core] run_agent error: {e}")
        return _step_error_response()


def rate_answer(
    query: str,
    answer: str,
    rating: int,
    feedback_db=None,
) -> dict:
    """
    Оценивает качество ответа агента с помощью AI-критика.
    При оценке пользователя >= 4 и оценке критика >= 4 сохраняет Q&A
    в базу дообучения.

    rate_answer вызывается отдельно от run_agent, поэтому создаёт
    собственное соединение — это нормально.
    """
    try:
        with _make_giga() as giga:
            score, comment = critic_rate_answer(giga, query, answer)
        if rating >= 4 and score >= 4:
            save_good_qa(query, answer, db=feedback_db)
        return {"critic_score": score, "critic_comment": comment}
    except Exception as e:
        print(f"[core] rate_answer error: {e}")
        return {"critic_score": 3, "critic_comment": "Ошибка оценки"}


# ---------------------------------------------------------------------------
# Маршрутизация
# ---------------------------------------------------------------------------

def _route_by_step(
    giga: GigaChat,
    query: str,
    current_step: str | None,
    history: list,
    slots: dict,
    collected_fields: dict,
    db,
    feedback_db,
    disagreement_db,
) -> dict:
    """Маршрутизирует запрос на нужный шаг. Принимает giga как параметр."""

    # --- STEP 1: сбор фактов + RAG для вопросов ---
    if current_step == Step.STEP1:
        if slots.get("disagreement_help_active"):
            step_result = _safe_call(
                lambda: _step_response_to_dict(
                    run_disagreement_help(giga, query, history, slots, disagreement_db),
                    "step1",
                ),
                "disagreement_help",
            )
        else:
            step_result = _safe_call(
                lambda: _step_response_to_dict(
                    process_step1_with_llm(giga, query, history, slots),
                    "step1",
                ),
                "step1",
            )
        return _inject_rag_if_question(giga, query, step_result, db, feedback_db, "general_questions")

    # --- OFFER_EUROPROTOCOL + OFFER_METHOD ---
    if current_step in (Step.OFFER_EUROPROTOCOL, Step.OFFER_METHOD):
        return _run_offer_europrotocol(query, history, slots)

    # --- STEP 2: заполнение протокола + RAG для вопросов ---
    if current_step == Step.STEP2:
        step_result = _safe_call(
            lambda: _step_response_to_dict(
                process_step2_with_llm(giga, query, history, slots, collected_fields),
                "step2",
            ),
            "step2",
        )
        return _inject_rag_if_question(giga, query, step_result, db, feedback_db, "filling_europrotocol")

    # --- FILL_EXTERNAL ---
    if current_step == Step.FILL_EXTERNAL:
        return _safe_call(
            lambda: _step_response_to_dict(
                process_fill_external(
                    giga, query, history, slots, collected_fields, db, feedback_db
                ),
                "fill_external",
            ),
            "fill_external",
        )

    # --- STEP 3 ---
    if current_step == Step.STEP3:
        return _safe_call(
            lambda: _step_response_to_dict(
                process_step3(giga, query, history, collected_fields, db, feedback_db),
                "step3",
            ),
            "step3",
        )

    # --- Консультант (включая consultant_only) ---
    if current_step == Step.CONSULTANT_ONLY:
        return _run_consultant(giga, query, history, db, feedback_db)

    print(f"[core] WARNING: unknown current_step={current_step!r}, treating as consultant")
    return _run_consultant(giga, query, history, db, feedback_db)


# ---------------------------------------------------------------------------
# OFFER_EUROPROTOCOL
# ---------------------------------------------------------------------------

def _run_offer_europrotocol(query: str, history: list, slots: dict) -> dict:
    """Не требует giga — только детерминированная логика выбора метода."""
    q = query.strip().lower()

    if any(kw in q for kw in _KW_REFUSE):
        return {
            "answer": (
                "Понял. Для оформления ДТП вызовите ГИБДД (102). "
                "Продолжаю работать в режиме консультанта."
            ),
            "source": "offer", "category": None,
            "step_completed": True, "next_step": Step.CONSULTANT_ONLY,
            "slots": slots, "collected_fields": None, "final_json": None,
        }

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
            "source": "offer", "category": None,
            "step_completed": True, "next_step": Step.STEP2,
            "slots": slots_clean, "collected_fields": prefilled, "final_json": None,
        }

    if any(kw in q for kw in _KW_EXT_APP):
        updated_slots = {**slots, "fill_method": "app_external"}
        return {
            "answer": _ENTRY_MESSAGE_APP,
            "source": "offer", "category": None,
            "step_completed": True, "next_step": Step.FILL_EXTERNAL,
            "slots": updated_slots,
            "collected_fields": slots.get("_prefilled", {}),
            "final_json": None,
        }

    if any(kw in q for kw in _KW_PAPER):
        updated_slots = {**slots, "fill_method": "paper"}
        return {
            "answer": _ENTRY_MESSAGE_PAPER,
            "source": "offer", "category": None,
            "step_completed": True, "next_step": Step.FILL_EXTERNAL,
            "slots": updated_slots,
            "collected_fields": slots.get("_prefilled", {}),
            "final_json": None,
        }

    # Первый вход — показываем лимиты + варианты
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
        "source": "offer", "category": None,
        "step_completed": False, "next_step": Step.OFFER_EUROPROTOCOL,
        "slots": slots, "collected_fields": None, "final_json": None,
    }


# ---------------------------------------------------------------------------
# Консультант
# ---------------------------------------------------------------------------

# СТАЛО:
def _run_consultant(giga: GigaChat, query: str, history: list, db, feedback_db) -> dict:
    """Использует переданный giga — не создаёт новый."""
    try:
        classifier_history = build_history(history, component="classifier")
        meta = meta_classify(giga, query, classifier_history)

        # Блокируем нерелевантные запросы — LLM явно пометил как off-topic
        if not meta.get("relevant", True):
            return _ok(
                "Я ДТП-ассистент и специализируюсь только на помощи при дорожно-транспортных "
                "происшествиях и вопросах ОСАГО. Опишите вашу ситуацию — помогу разобраться.",
                "filter",
                None,
            )

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


def _safe_call(handler, step_name: str) -> dict:
    """
    Вызывает handler() с обработкой ошибок.
    В отличие от старого _handle_with_error_guard НЕ создаёт новый giga —
    giga уже передан в замыкание через lambda.
    """
    try:
        return handler()
    except Exception as e:
        print(f"[core] {step_name} error: {e}")
        return _step_error_response()


def _ok(answer: str, source: str, category: str | None) -> dict:
    return {
        "answer": answer, "source": source, "category": category,
        "step_completed": False, "next_step": None,
        "slots": None, "collected_fields": None, "final_json": None,
    }


def _step_response_to_dict(result: StepResponse, source: str) -> dict:
    slots_out = dict(result.slots or {})
    if result.prefilled_fields:
        slots_out["_prefilled"] = result.prefilled_fields
    return {
        "answer": result.answer, "source": source, "category": None,
        "step_completed": result.step_completed, "next_step": result.next_step,
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
        "source": "error", "category": None,
        "step_completed": False, "next_step": Step.STEP1,
        "slots": {}, "collected_fields": {}, "final_json": None,
    }