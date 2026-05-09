"""
Step 1: Stateless fact collection and early exit logic.
Collects minimal facts to determine if Europrotocol is applicable.
Supports flexible input (multiple slots per message) and context passing.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
import json

from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

from config import GIGA_AUTH
from agent.history import build_history
from agent.step_types import Step, StepResponse

# Порядок слотов для опроса (согласно алгоритму и meta_classifier)
SLOT_ORDER = [
    "safety_confirmed",
    "emergency_sign",
    "victims",
    "participants_count",
    "osago_both",
    "disagreement",
]

_SLOT_EXTRACTION_PROMPT = """\
Извлеки факты о ДТП из сообщения пользователя.

Текущие известные данные:
{current_slots}

Ассистент только что задал вопрос про: {current_slot_label}
Краткие ответы ("да", "нет", числа) относятся к этому вопросу.

Правила:
- "да", "ага", "конечно" → true для текущего слота
- "нет", "не знаю" → false для текущего слота  
- число → participants_count ТОЛЬКО если вопрос был про количество ТС/машин
- число → victims НЕ извлекается никогда, это булевый слот (true/false)
- Если информация явно не упомянута — ОБЯЗАТЕЛЬНО верни null

КРИТИЧЕСКИ ВАЖНО: заполняй ТОЛЬКО то, что явно сказано.
Не делай выводов и не додумывай.

--- ПРИМЕРЫ ---

Вопрос был про: victims (пострадавшие)
Сообщение: "я попал в дтп"
Ответ: {{"safety_confirmed": null, "emergency_sign": null, "victims": null, "participants_count": null, "osago_both": null, "disagreement": null}}
Пояснение: пользователь не сказал ничего про пострадавших — все null.

Вопрос был про: victims (пострадавшие)
Сообщение: "нет"
Ответ: {{"safety_confirmed": null, "emergency_sign": null, "victims": false, "participants_count": null, "osago_both": null, "disagreement": null}}

Вопрос был про: victims (пострадавшие)
Сообщение: "есть пострадавшие, один человек ранен"
Ответ: {{"safety_confirmed": null, "emergency_sign": null, "victims": true, "participants_count": null, "osago_both": null, "disagreement": null}}

Вопрос был про: participants_count (количество ТС)
Сообщение: "2"
Ответ: {{"safety_confirmed": null, "emergency_sign": null, "victims": null, "participants_count": 2, "osago_both": null, "disagreement": null}}

Вопрос был про: victims (пострадавшие)
Сообщение: "2"
Ответ: {{"safety_confirmed": null, "emergency_sign": null, "victims": true, "participants_count": null, "osago_both": null, "disagreement": null}}
Пояснение: вопрос был про пострадавших, число 2 → есть пострадавшие → true. Но не participants_count.

Вопрос был про: victims (пострадавшие)
Сообщение: "0"
Ответ: {{"safety_confirmed": null, "emergency_sign": null, "victims": false, "participants_count": null, "osago_both": null, "disagreement": null}}

--- КОНЕЦ ПРИМЕРОВ ---

История диалога (последние 3 реплики):
{recent_history}

Сообщение пользователя: "{message}"

Верни ТОЛЬКО валидный JSON без пояснений и markdown.

{{
  "safety_confirmed": true/false/null,
  "emergency_sign": true/false/null,
  "victims": true/false/null,
  "participants_count": <целое число>/null,
  "osago_both": true/false/null,
  "disagreement": true/false/null
}}
"""



_SLOT_DESCRIPTIONS = {
    "safety_confirmed": "безопасность места ДТП (нет пожара, угрозы взрыва)",
    "emergency_sign":   "включена аварийная сигнализация и выставлен знак",
    "victims":          "есть ли пострадавшие, требующие медицинской помощи",
    "participants_count": "количество транспортных средств — участников ДТП",
    "osago_both":       "наличие действующих полисов ОСАГО у всех участников",
    "disagreement":     "наличие разногласий об обстоятельствах ДТП",
}

def validate_slots(slots: dict) -> tuple[bool, list[str]]:
    """
    Проверяет наличие всех обязательных ключей и их типы.

    Обязательные ключи: safety_confirmed, emergency_sign, victims,
                        participants_count, osago_both, disagreement

    Возвращает:
        (True, []) если валидно
        (False, [список ошибок]) иначе
    """
    required_keys = [
        "safety_confirmed",
        "emergency_sign",
        "victims",
        "participants_count",
        "osago_both",
        "disagreement",
    ]
    errors = []

    # Проверка наличия всех ключей
    for key in required_keys:
        if key not in slots:
            errors.append(f"Missing required slot: {key}")

    if errors:
        return (False, errors)

    # Проверка типов
    bool_fields = ["safety_confirmed", "emergency_sign", "victims", "osago_both", "disagreement"]
    for key in bool_fields:
        value = slots[key]
        if value is not None and not isinstance(value, bool):
            errors.append(f"{key} must be bool or None, got {type(value).__name__}")

    if slots["participants_count"] is not None and not isinstance(slots["participants_count"], int):
        errors.append(f"participants_count must be int or None, got {type(slots['participants_count']).__name__}")

    if errors:
        return (False, errors)

    return (True, [])


def _init_slots(initial: dict) -> dict:
    """
    Возвращает словарь со всеми 6 ключами.
    Значения из initial сохраняются, остальные = None.
    Неизвестные ключи из initial игнорируются.
    """
    result = {
        "safety_confirmed": None,
        "emergency_sign": None,
        "victims": None,
        "participants_count": None,
        "osago_both": None,
        "disagreement": None,
    }
    for key in SLOT_ORDER:
        if key in initial:
            result[key] = initial[key]
    return result


def _get_empty_slots(slots: dict) -> list[str]:
    """
    Возвращает список ключей со значением None.
    Порядок соответствует SLOT_ORDER.
    """
    return [key for key in SLOT_ORDER if slots.get(key) is None]


def _slot_to_block(slot: str) -> int:
    """
    Маппинг слота на номер блока алгоритма.
    safety_confirmed->0, emergency_sign->1, victims->2,
    participants_count->3, osago_both->4, disagreement->5
    Неизвестный слот -> 0
    """
    mapping = {
        "safety_confirmed": 0,
        "emergency_sign": 1,
        "victims": 2,
        "participants_count": 3,
        "osago_both": 4,
        "disagreement": 5,
    }
    return mapping.get(slot, 0)


def _fallback_question(slot: str) -> str:
    """
    Возвращает вопрос на русском для каждого слота.
    """
    questions = {
        "safety_confirmed": "Обеспечили ли вы безопасность места ДТП (нет пожара, нет угрозы взрыва)?",
        "emergency_sign": "Включили ли вы аварийную сигнализацию и выставили ли знак аварийной остановки?",
        "victims": "Есть ли пострадавшие в результате ДТП?",
        "participants_count": "Сколько транспортных средств участвовало в ДТП?",
        "osago_both": "Есть ли у всех водителей действующие полисы ОСАГО?",
        "disagreement": "Согласны ли вы со вторым участником в обстоятельствах ДТП или есть разногласия?",
    }
    return questions.get(slot, "Уточните детали происшествия.")


def _format_known_facts(slots: dict) -> str:
    """
    Форматирует известные факты для промпта.
    Если все значения None -> строка "ничего не известно"
    Иначе -> строка вида "key: value\\n" только для не-None значений
    """
    filled_items = [(k, v) for k, v in slots.items() if v is not None]
    if not filled_items:
        return "ничего не известно"
    return "\n".join(f"{k}: {v}" for k, v in filled_items)


class Step1Response:
    """
    Класс ответа Step1.
    Принимает dict в __init__.
    Свойства: step_completed (bool, default False),
              answer (str|None), next_step (str|None)
    Поддерживает доступ по ключу через __getitem__.
    """
    def __init__(self, data: dict):
        self._data = data
        self.step_completed = data.get("step_completed", False)
        self.answer = data.get("answer")
        self.next_step = data.get("next_step")

    def __getitem__(self, key: str):
        return self._data[key]


class Step1Result(BaseModel):
    """Result of Step 1 processing."""
    finished: bool = False
    next_step: str = "step1_collect_facts"
    stop_factor: Optional[str] = None
    instruction: str = ""
    extracted_data: Dict[str, Any] = Field(default_factory=dict)
    missing_slots: List[str] = Field(default_factory=list)
    question: str = ""


# --- Приватные функции для process_step1_with_llm ---

def _extract_slots_llm(
    giga: GigaChat,
    message: str,
    current_slots: dict,
    history: list,
    current_slot: str = "",          # <- новый параметр
) -> dict:
    recent = history[-3:] if len(history) >= 3 else history
    recent_text = "\n".join(
        f"П: {h['query']} / А: {h['answer']}" for h in recent
    ) or "(начало диалога)"

    # Человекочитаемое описание текущего слота для промпта
    current_slot_label = _SLOT_DESCRIPTIONS.get(current_slot, "")
    if current_slot_label:
        current_slot_label = f"{current_slot} ({current_slot_label})"

    prompt = _SLOT_EXTRACTION_PROMPT.format(
        current_slots=_format_known_facts(current_slots),
        current_slot_label=current_slot_label or "неизвестно",
        recent_history=recent_text,
        message=message,
    )
    payload = Chat(
        messages=[
            Messages(role=MessagesRole.SYSTEM, content="Ты — структурированный экстрактор данных. Отвечай только JSON."),
            Messages(role=MessagesRole.USER, content=prompt),
        ],
        temperature=0.0,
    )
    try:
        response = giga.chat(payload)
        content = response.choices[0].message.content.strip()
        if "```" in content:
            parts = content.split("```")
            for part in parts:
                if part.strip().startswith("{"):
                    content = part.strip()
                    break
        content = content.strip()
        extracted = json.loads(content)
        return {k: v for k, v in extracted.items() if v is not None}
    except Exception as e:
        print(f"[step1] slot extraction error: {e}")
        return {}





_FALLBACK_QUESTIONS: dict[str, list[str]] = {
    "safety_confirmed": [
        "Место ДТП безопасно? Нет угрозы пожара или взрыва?",
        "Убедитесь в безопасности — нет пожара, утечки топлива?",
    ],
    "emergency_sign": [
        "Включили аварийную сигнализацию и выставили знак аварийной остановки?",
        "Аварийка включена, знак выставлен?",
    ],
    "victims": [
        "Есть ли пострадавшие — люди, которым нужна медицинская помощь?",
        "Кто-то из участников получил травмы?",
        "Есть раненые?",
    ],
    "participants_count": [
        "Сколько транспортных средств участвовало в ДТП?",
        "Сколько машин столкнулось?",
    ],
    "osago_both": [
        "У обоих водителей есть действующие полисы ОСАГО?",
        "Проверьте — у второго участника ОСАГО в порядке?",
    ],
    "disagreement": [
        "Вы с другим участником согласны насчёт обстоятельств ДТП, или есть разногласия?",
        "Оба водителя одинаково понимают произошедшее?",
    ],
}


def _ask_question(slot: str, history: list) -> str:
    """
    Возвращает вопрос для слота. Без LLM, детерминировано.
    Ротирует формулировки если вопрос уже задавался, чтобы не повторяться.
    """
    variants = _FALLBACK_QUESTIONS.get(slot, ["Уточните детали."])
    if len(variants) == 1:
        return variants[0]

    # Считаем сколько раз уже задавался вопрос по этому слоту
    asked_count = sum(
        1 for h in history
        if any(v.lower()[:15] in h.get("answer", "").lower() or
               v.lower()[:15] in h.get("query", "").lower()
               for v in variants)
    )
    idx = min(asked_count, len(variants) - 1)
    return variants[idx]


def _check_early_exit_step1(slots: dict) -> tuple[str, str] | None:
    """
    Проверяет стоп-факторы. Возвращает (код, инструкция) или None.
    Проверяет в порядке: victims -> participants_count -> osago_both.
    """
    if slots.get("victims") is True:
        return (
            "call_gibdd_victims",
            "❌ Есть пострадавшие. Немедленно вызовите скорую (103) и ГИБДД (102). Европротокол оформлять нельзя."
        )
    p_count = slots.get("participants_count")
    if p_count is not None:
        if p_count > 2:
            return (
                "call_gibdd_participants",
                "❌ Участников больше двух. Вызовите ГИБДД (102). Европротокол невозможен."
            )
        if p_count == 1:
            return (
                "call_gibdd_participants",
                "❌ ДТП с одним участником (например, наезд на препятствие). Вызовите ГИБДД (102)."
            )
    if slots.get("osago_both") is False:
        return (
            "call_gibdd_osago",
            "❌ У одного из водителей нет ОСАГО. Вызовите ГИБДД (102)."
        )
    return None


# --- Главная функция для шагового режима ---

_OVERRIDABLE_SLOTS = {"victims", "participants_count", "osago_both"}

def process_step1_with_llm(
    giga: GigaChat,
    query: str,
    history: list,
    current_slots: dict,
) -> StepResponse:
    merged = _init_slots(current_slots)

    next_slot_before = next(
        (k for k in SLOT_ORDER if merged.get(k) is None), None
    )

    # Сначала детерминированное извлечение (быстро, без токенов)
    result = _try_simple_extraction(query, next_slot_before or "")

    if not result:
        # Если простое не сработало — LLM
        result = _extract_slots_llm(
            giga, query, merged, history,
            current_slot=next_slot_before or "",
        )

    print(f"[step1] slot={next_slot_before}, extracted={result}")

    for k, v in result.items():
        if v is None:
            continue
        if merged.get(k) is None or k in _OVERRIDABLE_SLOTS:
            merged[k] = v

    stop = _check_early_exit_step1(merged)
    if stop:
        _, instruction = stop
        return StepResponse(
            answer=instruction,
            step_completed=True,
            next_step=Step.CALL_GIBDD,
            slots=merged,
        )

    empty = _get_empty_slots(merged)
    if not empty:
        return StepResponse(
            answer="Отлично! Все данные собраны. Переходим к оформлению Европротокола.",
            step_completed=True,
            next_step=Step.STEP2,
            slots=merged,
        )

    question = _ask_question(empty[0], history)

    return StepResponse(
        answer=question,
        step_completed=False,
        next_step=Step.STEP1,
        slots=merged,
    )

STOP_FACTORS_MAP = {
    "victims": "call_gibdd_victims",
    "participants_count": "call_gibdd_participants",
    "osago_both": "call_gibdd_osago",
}

STEP1_EXTRACTION_PROMPT = """\
Ты — ассистент по сбору фактов о ДТП для определения возможности оформления Европротокола.

Твоя задача: извлечь из сообщения пользователя следующие данные (если они упоминаются):

1. safety_confirmed (bool) — обеспечена ли безопасность места ДТП (нет пожара, нет угрозы взрыва)
2. emergency_sign (bool) — включил ли водитель аварийную сигнализацию и выставил ли знак аварийной остановки
3. victims (bool) — есть ли пострадавшие (люди, требующие медицинской помощи)
4. participants_count (int) — количество транспортных средств, участвовавших в ДТП
5. osago_both (bool) — есть ли у всех водителей действующие полисы ОСАГО
6. disagreement (bool) — есть ли разногласия между участниками ДТП

ПРАВИЛА:
- Извлекай ТОЛЬКО явные факты из сообщения. Не додумывай.
- Если факт не упомянут — не включай его в результат.
- Возвращай ответ ТОЛЬКО в формате JSON без лишних комментариев.
- Используй null для полей, которые не удалось извлечь.
- Учитывай контекст диалога: краткие ответы ("да", "нет", числа) относятся к последнему заданному вопросу.

ВАЖНО: Пользователь может отвечать кратко:
- "да", "yes", "ага", "конечно" → true
- "нет", "no", "не", "никогда" → false
- Числа (например "2", "три", "один") → соответствующее целое число для participants_count

Пример ответа:
{{
    "victims": false,
    "participants_count": 2,
    "osago_both": true
}}

Известные данные на текущий момент:
{known_data}

История диалога (последние 3 реплики):
{recent_history}

Сообщение пользователя:
{user_message}
"""


def _make_giga() -> GigaChat:
    """Create GigaChat client instance."""
    return GigaChat(
        credentials=GIGA_AUTH,
        verify_ssl_certs=False,
        scope="GIGACHAT_API_B2B",
    )


def _extract_data_with_llm(giga: GigaChat, user_message: str, conversation_context: Dict[str, Any]) -> Dict[str, Any]:
    """Use LLM to extract structured data from user message with context."""
    current_data = conversation_context.get("step1_data", {})
    history = conversation_context.get("history", [])

    # Format known data
    known_data_str = "ничего не известно" if not current_data else "\n".join(f"{k}: {v}" for k, v in current_data.items() if v is not None)

    # Format recent history (last 3 exchanges)
    recent_history = history[-3:] if len(history) >= 3 else history
    recent_history_str = "\n".join(
        f"Пользователь: {h['query']}\nАссистент: {h['answer']}"
        for h in recent_history
    ) or "(начало диалога)"

    prompt = STEP1_EXTRACTION_PROMPT.format(
        known_data=known_data_str,
        recent_history=recent_history_str,
        user_message=user_message
    )

    payload = Chat(
        messages=[
            Messages(role=MessagesRole.SYSTEM, content="Ты — структурированный экстрактор данных. Отвечай только JSON."),
            Messages(role=MessagesRole.USER, content=prompt),
        ],
        temperature=0.0,
    )

    try:
        response = giga.chat(payload)
        content = response.choices[0].message.content.strip()

        # Parse JSON response
        import json
        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        extracted = json.loads(content)
        return {k: v for k, v in extracted.items() if v is not None}
    except Exception as e:
        print(f"[step1] LLM extraction error: {e}")
        return {}

def _check_early_exit(data: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    """
    Check for stop factors immediately after data extraction.
    Returns (next_step_code, instruction_message) if stop factor found.
    """
    if data.get("victims") is True:
        return "call_gibdd_victims", "❌ Есть пострадавшие. Немедленно вызовите скорую (103) и ГИБДД (102). Европротокол оформлять нельзя."

    p_count = data.get("participants_count")
    if p_count is not None:
        if p_count > 2:
            return "call_gibdd_participants", "❌ Участников больше двух. Вызовите ГИБДД (102). Европротокол невозможен."
        if p_count == 1:
            return "call_gibdd_participants", "❌ ДТП с одним участником (например, наезд на препятствие). Вызовите ГИБДД (102)."

    if data.get("osago_both") is False:
        return "call_gibdd_osago", "❌ У одного из водителей нет ОСАГО. Вызовите ГИБДД (102)."

    return None


def _get_next_question(filled_slots: List[str], context: Dict[str, Any]) -> str:
    """Generate the next single question based on missing slots."""
    for slot in SLOT_ORDER:
        if slot not in filled_slots:
            # Skip asking if we already have the data in context from previous turns
            if slot in context and context[slot] is not None:
                continue

            questions = {
                "safety_confirmed": "Обеспечили ли вы безопасность места ДТП (нет пожара, нет угрозы взрыва)?",
                "emergency_sign": "Вы включили аварийную сигнализацию и выставили знак аварийной остановки?",
                "victims": "Есть ли пострадавшие в результате ДТП (люди, требующие медицинской помощи)?",
                "participants_count": "Сколько всего транспортных средств участвовало в ДТП?",
                "osago_both": "Есть ли у всех водителей действующие полисы ОСАГО?",
                "disagreement": "Согласны ли вы со вторым участником в обстоятельствах ДТП? Планируете ли использовать приложение 'Помощник ОСАГО'?",
            }
            return questions.get(slot, "Уточните детали происшествия.")

    return ""


def process_step1_query(
    user_message: str,
    conversation_context: Dict[str, Any]
) -> Step1Result:
    """
    Process user message for Step 1.
    Extracts facts flexibly (multiple slots at once) using LLM.
    Checks for early exit conditions.
    """
    # 1. Initialize state from context
    current_data = conversation_context.get("step1_data", {})
    filled_slots = conversation_context.get("step1_filled_slots", [])

    # 2. Use LLM to extract entities from user message
    with _make_giga() as giga:
        new_extracted = _extract_data_with_llm(giga, user_message, conversation_context)

    # Merge newly extracted data with existing data
    for key, value in new_extracted.items():
        if key not in current_data or current_data[key] is None:
            current_data[key] = value
            if key not in filled_slots:
                filled_slots.append(key)

    # 3. Check Early Exit (Stop Factors)
    stop_result = _check_early_exit(current_data)
    if stop_result:
        next_step_code, instruction = stop_result
        return Step1Result(
            finished=True,
            next_step=next_step_code,
            stop_factor=next_step_code,
            instruction=instruction,
            extracted_data=current_data
        )

    # 4. Check Completion
    all_slots_filled = all(slot in filled_slots for slot in SLOT_ORDER)

    if all_slots_filled:
        # Success: Move to Step 2
        return Step1Result(
            finished=True,
            next_step="step2_fill_europrotocol",
            instruction="✅ Отлично, все данные собраны. Переходим к заполнению Европротокола.",
            extracted_data=current_data,
            missing_slots=[]
        )

    # 5. Generate Next Question
    next_q = _get_next_question(filled_slots, current_data)

    # Identify missing slots for the response
    missing = [s for s in SLOT_ORDER if s not in filled_slots]

    return Step1Result(
        finished=False,
        next_step="step1_collect_facts",
        instruction=f"Понял. {next_q}" if next_q else "Расскажите подробнее.",
        extracted_data=current_data,
        missing_slots=missing,
        question=next_q
    )

_SIMPLE_YES = frozenset({
    "да", "yes", "ага", "конечно", "верно", "точно", "именно",
    "угу", "ок", "ok", "хорошо", "само собой", "есть"
})
_SIMPLE_NO = frozenset({
    "нет", "no", "не", "нету", "нети", "нетю", "неа", "нихт", "отсутствует"
})
_WORD_NUMS = {
    "один": 1, "одна": 1, "одно": 1,
    "два": 2, "две": 2,
    "три": 3, "четыре": 4, "пять": 5,
}


def _try_simple_extraction(message: str, current_slot: str) -> dict:
    """
    Детерминированный маппинг для однозначных ответов.
    Не требует LLM. Возвращает {} если ответ не однозначный.
    """
    if not current_slot:
        return {}

    text = message.strip().lower().rstrip("!.,?")

    bool_slots = {"safety_confirmed", "emergency_sign", "victims", "osago_both", "disagreement"}

    if current_slot in bool_slots:
        if text in _SIMPLE_YES:
            return {current_slot: True}
        if text in _SIMPLE_NO:
            return {current_slot: False}

    if current_slot == "participants_count":
        # Числа цифрами
        try:
            n = int(text)
            if 1 <= n <= 20:
                return {current_slot: n}
        except ValueError:
            pass
        # Числа словами
        if text in _WORD_NUMS:
            return {current_slot: _WORD_NUMS[text]}

    return {}