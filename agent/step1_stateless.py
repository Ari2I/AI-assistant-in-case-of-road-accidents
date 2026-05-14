"""
Step 1: Stateless fact collection and early exit logic.
Collects minimal facts to determine if Europrotocol is applicable.
Supports flexible input (multiple slots per message) and context passing.
"""

from __future__ import annotations

import json
from typing import Any
import re

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


ВАЖНО ПРО РАЗНОГЛАСИЯ (disagreement):
- disagreement = true ТОЛЬКО если водители спорят об обстоятельствах ДТП (кто виноват, как произошло, кто куда ехал)
- Проблемы с полисом ОСАГО (не вписан водитель, просрочен полис, поддельный полис) — это НЕ разногласия!
- Если пользователь говорит про ОСАГО, но НЕ упоминает спор об обстоятельствах — disagreement = null

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
Ответ: {{"safety_confirmed": null, "emergency_sign": null, "victims": null, "participants_count": null, "osago_both": null, "disagreement": null}}
Пояснение: число на вопрос о пострадавших — неоднозначный ответ. Нужно уточнить: "Вы имеете в виду 2 пострадавших?" Не делай выводов самостоятельно.

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

Вопрос был про: osago_both (наличие ОСАГО)
Сообщение: "да, они у нас есть, но второй водитель не вписан в него"
Ответ: {{"safety_confirmed": null, "emergency_sign": null, "victims": null, "participants_count": null, "osago_both": false, "disagreement": null}}
Пояснение: проблема с полисом (не вписан водитель) — это НЕ разногласия об обстоятельствах ДТП.

Вопрос был про: osago_both (наличие ОСАГО)
Сообщение: "у меня есть, а у второго нет полиса"
Ответ: {{"safety_confirmed": null, "emergency_sign": null, "victims": null, "participants_count": null, "osago_both": false, "disagreement": null}}
Пояснение: если водитель не вписан в полис ОСАГО, полис для него не действует — это равносильно отсутствию ОСАГО. Проблема с полисом — это НЕ разногласия об обстоятельствах ДТП.

Вопрос был про: disagreement (разногласия)
Сообщение: "мы спорим кто виноват"
Ответ: {{"safety_confirmed": null, "emergency_sign": null, "victims": null, "participants_count": null, "osago_both": null, "disagreement": true}}

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

# --- prefill ---

_PREFILL_TARGET_KEYS: frozenset[str] = frozenset({
    "date", "time", "location",
    "vehicle_a_make_model", "vehicle_a_reg_number",
    "vehicle_b_make_model", "vehicle_b_reg_number",
})

_PREFILL_EXTRACTION_PROMPT = """\
Извлеки из сообщения пользователя данные для протокола о ДТП.
Извлекай ТОЛЬКО то, что явно указано. Не додумывай.

Целевые поля:
- date: дата ДТП (формат ДД.ММ.ГГГГ)
- time: время ДТП (формат ЧЧ:ММ)
- location: место ДТП — город, улица, дом или км трассы
- vehicle_a_make_model: марка и модель авто пользователя
- vehicle_a_reg_number: госномер авто пользователя
- vehicle_b_make_model: марка и модель авто второго участника
- vehicle_b_reg_number: госномер авто второго участника

Правила:
- Если данных нет — не включай ключ в ответ.
- Верни ТОЛЬКО валидный JSON без пояснений и markdown.

Примеры:

Сообщение: "столкнулся с Toyota Camry А123БВ777 на ул. Ленина"
Ответ: {{"location": "ул. Ленина", "vehicle_b_make_model": "Toyota Camry",
"vehicle_b_reg_number": "А123БВ777"}}

Сообщение: "ДТП было 15.01.2024 в 14:30, я на Honda Civic Е456РТ77"
Ответ: {{"date": "15.01.2024", "time": "14:30",
"vehicle_a_make_model": "Honda Civic",
"vehicle_a_reg_number": "Е456РТ77"}}

Сообщение: "нет пострадавших"
Ответ: {{}}

Сообщение пользователя: "{message}"
"""
# Ответ: {{}} только так, иначе выдаёт ошибку

def _try_prefill_fields(giga: GigaChat, message: str) -> dict:
    """
    Лёгкий вызов LLM для извлечения очевидных полей step2 из одного
    сообщения step1. При люб ой ошибке возвращает пустой dict -
    не блокирует основной pipeline.
    """
    prompt = _PREFILL_EXTRACTION_PROMPT.format(message=message)
    try:
        payload = Chat(
            messages=[
                Messages(
                    role=MessagesRole.SYSTEM,
                    content="Ты — экстрактор данных. Отвечай только JSON.",
                ),
                Messages(role=MessagesRole.USER, content=prompt),
            ],
            temperature=0.0,
        )
        response = giga.chat(payload)
        content = response.choices[0].message.content.strip()
        if "```" in content:
            for part in content.split("```"):
                if part.strip().startswith("{"):
                    content = part.strip()
                    break
        extracted = json.loads(content)
        return {
            k: v for k, v in extracted.items()
            if k in _PREFILL_TARGET_KEYS and v
        }
    except Exception as e:
        print(f"[step1] prefill extraction error: {e}")
        return {}

# --- конец prefill ---

_SLOT_DESCRIPTIONS = {
    "safety_confirmed": "безопасность места ДТП (нет пожара, угрозы взрыва)",
    "emergency_sign": "включена аварийная сигнализация и выставлен знак",
    "victims": "есть ли пострадавшие, требующие медицинской помощи",
    "participants_count": "количество транспортных средств — участников ДТП",
    "osago_both": "наличие действующих полисов ОСАГО у всех участников",
    "disagreement": "наличие разногласий об обстоятельствах ДТП",
}

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


# ---------------------------------------------------------------------------
# Публичные вспомогательные функции (используются в тестах)
# ---------------------------------------------------------------------------

def validate_slots(slots: dict) -> tuple[bool, list[str]]:
    """
    Проверяет наличие всех обязательных ключей и их типы.

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

    for key in required_keys:
        if key not in slots:
            errors.append(f"Missing required slot: {key}")

    if errors:
        return (False, errors)

    bool_fields = ["safety_confirmed", "emergency_sign", "victims", "osago_both", "disagreement"]
    for key in bool_fields:
        value = slots[key]
        if value is not None and not isinstance(value, bool):
            errors.append(f"{key} must be bool or None, got {type(value).__name__}")

    if slots["participants_count"] is not None and not isinstance(slots["participants_count"], int):
        errors.append(
            f"participants_count must be int or None, got {type(slots['participants_count']).__name__}"
        )

    return (not bool(errors), errors)


def _init_slots(initial: dict) -> dict:
    """Инициализирует слоты с None по умолчанию, подставляя известные значения."""
    result: dict[str, Any] = {
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
    # Дополнительные флаги (disagreement_help_offered и т.д.)
    for key, value in initial.items():
        if key not in result:
            result[key] = value
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
    Неизвестный слот → 0.
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
    """Возвращает вопрос на русском для каждого слота."""
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
    Если все значения None → строка "ничего не известно".
    """
    filled_items = [(k, v) for k, v in slots.items() if v is not None]
    if not filled_items:
        return "ничего не известно"
    return "\n".join(f"{k}: {v}" for k, v in filled_items)


class Step1Response:
    """
    Обёртка над dict для удобного доступа к полям ответа step1.
    Используется в тестах для проверки структуры ответа.
    """

    def __init__(self, data: dict):
        self._data = data
        self.step_completed = data.get("step_completed", False)
        self.answer = data.get("answer")
        self.next_step = data.get("next_step")

    @property
    def slots(self) -> dict:
        return self._data.get("slots", {})

    def __getitem__(self, key: str) -> Any:
        return self._data[key]


# ---------------------------------------------------------------------------
# Приватные функции
# ---------------------------------------------------------------------------

def _extract_slots_llm(
    giga: GigaChat,
    message: str,
    current_slots: dict,
    history: list,
    current_slot: str = "",
) -> dict:
    """Вызывает LLM для извлечения слотов из сообщения пользователя."""
    recent = history[-3:] if len(history) >= 3 else history
    recent_text = "\n".join(
        f"П: {h['query']} / А: {h['answer']}" for h in recent
    ) or "(начало диалога)"

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
            Messages(
                role=MessagesRole.SYSTEM,
                content="Ты — структурированный экстрактор данных. Отвечай только JSON.",
            ),
            Messages(role=MessagesRole.USER, content=prompt),
        ],
        temperature=0.0,
    )
    try:
        response = giga.chat(payload)
        content = response.choices[0].message.content.strip()
        if "```" in content:
            for part in content.split("```"):
                if part.strip().startswith("{"):
                    content = part.strip()
                    break
        extracted = json.loads(content)
        return {k: v for k, v in extracted.items() if v is not None}
    except Exception as e:
        print(f"[step1] slot extraction error: {e}")
        return {}


def _ask_question(slot: str, history: list) -> str:
    """
    Возвращает вопрос для слота без вызова LLM.
    Ротирует формулировки, если вопрос уже задавался.
    """
    variants = _FALLBACK_QUESTIONS.get(slot, ["Уточните детали."])
    if len(variants) == 1:
        return variants[0]

    asked_count = sum(
        1 for h in history
        if any(
            v.lower()[:15] in h.get("answer", "").lower()
            or v.lower()[:15] in h.get("query", "").lower()
            for v in variants
        )
    )
    return variants[min(asked_count, len(variants) - 1)]


def _check_early_exit_step1(slots: dict) -> tuple[str, str] | None:
    """
    Проверяет стоп-факторы в порядке: victims → participants_count → osago_both.
    Возвращает (код, инструкция) или None.
    """
    if slots.get("victims") is True:
        return (
            "call_gibdd_victims",
            "❌ Есть пострадавшие. Немедленно вызовите скорую (103) и ГИБДД (102). Европротокол оформлять нельзя.",
        )
    p_count = slots.get("participants_count")
    if p_count is not None:
        if p_count > 2:
            return (
                "call_gibdd_participants",
                "❌ Участников больше двух. Вызовите ГИБДД (102). Европротокол невозможен.",
            )
        if p_count == 1:
            return (
                "call_gibdd_participants",
                "❌ ДТП с одним участником (например, наезд на препятствие). Вызовите ГИБДД (102).",
            )
    if slots.get("osago_both") is False:
        return (
            "call_gibdd_osago",
            "❌ У одного из водителей нет ОСАГО. Вызовите ГИБДД (102).",
        )
    return None


def _try_simple_extraction(message: str, current_slot: str) -> dict:
    """
    Детерминированный маппинг для однозначных ответов.
    Не требует LLM. Возвращает {} если ответ неоднозначный.
    """
    if not current_slot:
        return {}

    text = message.strip().lower().rstrip("!.,?")
    bool_slots = {"safety_confirmed", "emergency_sign", "victims", "osago_both", "disagreement"}

    # Разбиваем сообщение на части (по запятым и союзам) для обработки нескольких фактов
    parts = [p.strip() for p in re.split(r'[,;]| и | но | а ', text) if p.strip()]

    result = {}

    for part in parts:
        # Маркеры для victims (пострадавшие)
        victims_markers = ["пострадавш", "ранен", "травм", "жертв"]
        if any(m in part for m in victims_markers):
            if part in _SIMPLE_NO or part.startswith("нет ") or " нет" in part or "0" in part:
                result["victims"] = False
            else:
                result["victims"] = True
            continue

        # Маркеры для osago_both (ОСАГО)
        osago_markers = ["осаго", "полис", "страховк"]
        if any(m in part for m in osago_markers):
            if part in _SIMPLE_NO or part.startswith("нет "):
                result["osago_both"] = False
            elif part in _SIMPLE_YES or part.startswith("есть "):
                result["osago_both"] = True
            continue

        # Маркеры для safety_confirmed (безопасность)
        safety_markers = ["пожар", "взрыв", "угроз", "бензин", "топлив", "искр"]
        if any(m in part for m in safety_markers):
            if part in _SIMPLE_NO or part.startswith("нет "):
                result["safety_confirmed"] = False
            elif part in _SIMPLE_YES or part.startswith("есть "):
                result["safety_confirmed"] = True
            continue

        # Маркеры для emergency_sign (аварийка/знак)
        emergency_markers = ["аварийк", "знак", "фонарь", "мигал"]
        if any(m in part for m in emergency_markers):
            if part in _SIMPLE_NO or part.startswith("нет "):
                result["emergency_sign"] = False
            elif part in _SIMPLE_YES or part.startswith("есть "):
                result["emergency_sign"] = True
            # Обработка случая "знак выставил" без явного "да/нет"
            elif "выставил" in part or "включил" in part or "поставил" in part:
                result["emergency_sign"] = True
            continue

        # Маркеры для disagreement (разногласия/спор)
        disagreement_markers = ["спор", "разноглас", "не соглас", "вина", "кто прав"]
        if any(m in part for m in disagreement_markers):
            if part in _SIMPLE_NO or part.startswith("нет "):
                result["disagreement"] = False
            elif part in _SIMPLE_YES or part.startswith("есть "):
                result["disagreement"] = True
            continue

    # Если ничего не извлекли по маркерам, используем общий подход по текущему слоту
    if not result and current_slot in bool_slots:
        if text in _SIMPLE_YES or text.startswith("есть "):
            return {current_slot: True}
        if text in _SIMPLE_NO or text.startswith("нет "):
            return {current_slot: False}

    if not result and current_slot == "participants_count":
        try:
            n = int(text)
            if 1 <= n <= 20:
                return {current_slot: n}
        except ValueError:
            pass
        if text in _WORD_NUMS:
            return {current_slot: _WORD_NUMS[text]}

    return result


# ---------------------------------------------------------------------------
# Главная функция для шагового режима
# ---------------------------------------------------------------------------

def process_step1_with_llm(
    giga: GigaChat,
    query: str,
    history: list,
    current_slots: dict,
) -> StepResponse:
    """
    Обрабатывает один шаг сбора фактов.
    Возвращает StepResponse с обновлёнными слотами и следующим действием.
    """
    # Извлекаем и удаляем накопленный prefill из входящих слотов,
    # чтобы _init_slots не скопировал его в merged как обычный слот.
    accumulated_prefill: dict = dict(current_slots.get("_prefilled", {}))
    current_slots_clean = {k: v for k, v in current_slots.items()
                           if k != "_prefilled"}
    merged = _init_slots(current_slots_clean)

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

    # Лёгкое извлечение данных для step2 из текущего сообщения
    new_prefill = _try_prefill_fields(giga, query)
    for k, v in new_prefill.items():
        if k not in accumulated_prefill:
            accumulated_prefill[k] = v

    for k, v in result.items():
        if v is not None:
            merged[k] = v

    # Проверка стоп-факторов
    stop = _check_early_exit_step1(merged)
    if stop:
        _, instruction = stop
        return StepResponse(
            answer=instruction,
            step_completed=True,
            next_step=Step.CALL_GIBDD,
            slots=merged,
            prefilled_fields=accumulated_prefill,
        )

    # Активация подрежима помощи при разногласиях
    if merged.get("disagreement") is True and not merged.get("disagreement_help_offered"):
        merged["disagreement_help_offered"] = True
        merged["disagreement_help_active"] = True
        return StepResponse(
            answer=(
                "Вы упомянули, что есть разногласия со вторым участником. "
                "Это важно — от этого зависит лимит выплаты. "
                "Хотите, я объясню, как правильно их зафиксировать?"
            ),
            step_completed=False,
            next_step=Step.STEP1,
            slots=merged,
            prefilled_fields=accumulated_prefill,
        )

    # Проверка завершения сбора слотов
    empty = _get_empty_slots(merged)
    if not empty:
        return StepResponse(
            answer=(
                "Все данные собраны. Вы можете оформить Европротокол — "
                "я помогу заполнить каждое поле. Хотите приступить?"
            ),
            step_completed=True,
            next_step=Step.OFFER_EUROPROTOCOL,
            slots=merged,
            prefilled_fields=accumulated_prefill,
        )

    question = _ask_question(empty[0], history)
    return StepResponse(
        answer=question,
        step_completed=False,
        next_step=Step.STEP1,
        slots=merged,
        prefilled_fields=accumulated_prefill,
    )