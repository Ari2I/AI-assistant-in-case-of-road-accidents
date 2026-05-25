"""
Подрежим помощи при разногласиях в рамках Step 1. Версия 2.2.

Изменения vs v2.1:
  - Детекция коррекции перенесена на LLM вместо hardcoded фраз:
    LLM понимает любые формулировки исправлений, опечатки, смену позиции
  - _is_correction() удалена, заменена на _detect_correction_with_llm()
  - _CORRECTION_PHRASES удалены
"""

from __future__ import annotations

import json
import re

from gigachat.models import Chat, Messages, MessagesRole

from agent.step_types import Step, StepResponse
from agent.history import build_history
from agent.disagreement_slots import (
    init_disagreement_slots,
    get_next_slot,
    get_next_clarifying_slot,
    are_required_slots_filled,
    get_uncertain_required_slot,
    SLOT_QUESTIONS,
    SKIPPABLE_SLOTS,
)

# ---------------------------------------------------------------------------
# Порог уверенности
# ---------------------------------------------------------------------------

_CONFIDENCE_THRESHOLD = 0.70

# ---------------------------------------------------------------------------
# LLM-детектор коррекции
# ---------------------------------------------------------------------------

_CORRECTION_DETECTION_PROMPT = """\
Пользователь общается с агентом, который собирает данные о ДТП для анализа разногласий.
Агент задаёт вопросы и записывает ответы. Уже записанные данные:

{known_data}

Последнее сообщение пользователя: "{message}"

Определи: пользователь исправляет или уточняет что-то из уже сказанного ранее?

Признаки коррекции:
- явное указание на ошибку («ошибся», «не то написал», «опечатка»)
- противоречие уже записанным данным с новой информацией
- фразы уточнения («точнее», «вернее», «имел в виду»)
- просьба забыть / отменить предыдущий ответ
- сообщение содержит данные, которые уже записаны, но в другом значении

Признаки обычного ответа (НЕ коррекция):
- ответ на текущий вопрос агента без противоречия записанным данным
- новая информация которой ещё нет в записанных данных
- уточнение деталей которые не были записаны

Верни ТОЛЬКО валидный JSON без пояснений:
{{"is_correction": true/false, "reason": "одна фраза почему"}}
"""


def _detect_correction_with_llm(
    giga,
    query: str,
    d_slots: dict,
) -> bool:
    """
    Определяет через LLM, является ли сообщение коррекцией ранее сказанного.

    Используется вместо hardcoded фраз — LLM понимает любые формулировки:
    опечатки, смену позиции, противоречия с уже записанными данными.
    При любой ошибке возвращает False — не перезаписываем данные случайно.
    """
    known_str = (
        "\n".join(f"  {k}: {v}" for k, v in d_slots.items()
                  if v is not None and not k.startswith("_"))
        or "  (нет данных)"
    )

    prompt = _CORRECTION_DETECTION_PROMPT.format(
        known_data=known_str,
        message=query,
    )

    try:
        payload = Chat(
            messages=[
                Messages(
                    role=MessagesRole.SYSTEM,
                    content=(
                        "Ты — классификатор намерений. "
                        "Определяй только по содержанию сообщения и контексту. "
                        "Отвечай только JSON."
                    ),
                ),
                Messages(role=MessagesRole.USER, content=prompt),
            ],
            temperature=0.0,
        )
        response = giga.chat(payload)
        content = response.choices[0].message.content.strip()

        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return False

        data = json.loads(match.group(0))
        result = bool(data.get("is_correction", False))

        if result:
            reason = data.get("reason", "")
            print(f"[disagreement_helper] correction detected: {reason}")

        return result

    except Exception as e:
        print(f"[disagreement_helper] correction detection error: {e}")
        return False


# ---------------------------------------------------------------------------
# Промпт извлечения — обычный (без перезаписи)
# ---------------------------------------------------------------------------

_SLOT_EXTRACTION_PROMPT = """\
Извлеки данные для анализа разногласий при ДТП из сообщения пользователя.

Текущий вопрос был про: {current_slot_label}
Уже известные данные: {known_data}

Целевые поля (заполняй только те, данные для которых явно есть в сообщении):

road_type: тип места ДТП
  Значения: "перекрёсток" / "прямой участок" / "парковка" / "двор" / "другое"

priority_signs: приоритет на дороге
  Значения: "главная" / "второстепенная" / "равнозначные" / "светофор" / "неизвестно"

traffic_light_state: сигнал светофора для пользователя (ТС А)
  Значения: "зелёный" / "жёлтый мигающий" / "красный" / "не применимо"

traffic_light_state_b: сигнал светофора для второго участника (ТС Б)
  Значения: "зелёный" / "жёлтый мигающий" / "красный" / "не применимо" / "неизвестно"

vehicle_a_maneuver: манёвр пользователя (ТС А)
  Значения: "прямо" / "поворот налево" / "поворот направо" / "разворот" /
            "перестроение" / "задний ход" / "стоял"

vehicle_b_maneuver: манёвр второго участника (ТС Б)
  Значения: те же что для vehicle_a_maneuver

vehicle_a_version: версия пользователя (свободный текст, сохрани полностью)

vehicle_b_version: версия второго участника (свободный текст или "не сообщил")

road_markings: разметка
  Значения: "сплошная" / "прерывистая" / "пешеходный переход" /
            "стоп-линия" / "нет" / "неизвестно"

road_condition: состояние дороги
  Значения: "сухая" / "мокрая" / "лёд" / "снег" / "другое"

speed_a_approx: скорость ТС А в км/ч (целое число) или null

speed_b_approx: скорость ТС Б в км/ч (целое число) или null

visibility: видимость
  Значения: "хорошая" / "ограниченная" / "плохая"

road_signs: дорожные знаки в месте ДТП
  Значения: "уступи дорогу" / "стоп" / "главная дорога" / "нет знаков" / "неизвестно"

speed_limit: ограничение скорости на участке (число км/ч или "неизвестно")

vehicle_b_origin: откуда появился второй участник
  Значения: "ехал по дороге" / "выезжал со двора" / "выезжал с парковки" /
            "выезжал с прилегающей территории" / "выезжал с второстепенной дороги" / "неизвестно"

impact_point_a: место удара на автомобиле пользователя (ТС А)
  Значения: "передняя" / "передняя левая" / "передняя правая" /
            "левый бок" / "правый бок" / "задняя" / "задняя левая" / "задняя правая"

impact_point_b: место удара на автомобиле второго участника (ТС Б)
  Значения: те же что для impact_point_a

has_dashcam_a: есть ли видеорегистратор у пользователя (ТС А)
  Значения: "да" / "нет" / "неизвестно"

has_dashcam_b: есть ли видеорегистратор у второго участника (ТС Б)
  Значения: "да" / "нет" / "неизвестно"

Правила:
- Если данных для поля нет — не включай его в ответ
- Не перезаписывай уже заполненные поля из «Уже известные данные»
- Для vehicle_a_version и vehicle_b_version сохраняй полный текст
- "не знаю", "не помню", "не заметил" для пропускаемых полей → значение "неизвестно"
- Верни ТОЛЬКО валидный JSON без пояснений и markdown

Сообщение пользователя: "{message}"
"""

# ---------------------------------------------------------------------------
# Промпт извлечения — с разрешением перезаписи (при коррекции)
# ---------------------------------------------------------------------------

_SLOT_EXTRACTION_OVERWRITE_PROMPT = """\
Пользователь ИСПРАВЛЯЕТ ранее сказанное. Обнови данные для анализа разногласий при ДТП.

Текущий вопрос был про: {current_slot_label}
Текущие данные (могут быть перезаписаны если пользователь их исправляет): {known_data}

Целевые поля:

road_type: тип места ДТП
  Значения: "перекрёсток" / "прямой участок" / "парковка" / "двор" / "другое"

priority_signs: приоритет на дороге
  Значения: "главная" / "второстепенная" / "равнозначные" / "светофор" / "неизвестно"

traffic_light_state: сигнал светофора для пользователя (ТС А)
  Значения: "зелёный" / "жёлтый мигающий" / "красный" / "не применимо"

traffic_light_state_b: сигнал светофора для второго участника (ТС Б)
  Значения: "зелёный" / "жёлтый мигающий" / "красный" / "не применимо" / "неизвестно"

vehicle_a_maneuver: манёвр пользователя (ТС А)
  Значения: "прямо" / "поворот налево" / "поворот направо" / "разворот" /
            "перестроение" / "задний ход" / "стоял"

vehicle_b_maneuver: манёвр второго участника (ТС Б)
  Значения: те же что для vehicle_a_maneuver

vehicle_a_version: версия пользователя (свободный текст, сохрани полностью)

vehicle_b_version: версия второго участника (свободный текст или "не сообщил")

road_markings: разметка
  Значения: "сплошная" / "прерывистая" / "пешеходный переход" /
            "стоп-линия" / "нет" / "неизвестно"

road_condition: состояние дороги
  Значения: "сухая" / "мокрая" / "лёд" / "снег" / "другое"

speed_a_approx: скорость ТС А в км/ч (целое число) или null

speed_b_approx: скорость ТС Б в км/ч (целое число) или null

visibility: видимость
  Значения: "хорошая" / "ограниченная" / "плохая"

road_signs: дорожные знаки в месте ДТП
  Значения: "уступи дорогу" / "стоп" / "главная дорога" / "нет знаков" / "неизвестно"

speed_limit: ограничение скорости на участке (число км/ч или "неизвестно")

vehicle_b_origin: откуда появился второй участник
  Значения: "ехал по дороге" / "выезжал со двора" / "выезжал с парковки" /
            "выезжал с прилегающей территории" / "выезжал с второстепенной дороги" / "неизвестно"

impact_point_a: место удара на автомобиле пользователя (ТС А)
  Значения: "передняя" / "передняя левая" / "передняя правая" /
            "левый бок" / "правый бок" / "задняя" / "задняя левая" / "задняя правая"

impact_point_b: место удара на автомобиле второго участника (ТС Б)
  Значения: те же что для impact_point_a

has_dashcam_a: есть ли видеорегистратор у пользователя (ТС А)
  Значения: "да" / "нет" / "неизвестно"

has_dashcam_b: есть ли видеорегистратор у второго участника (ТС Б)
  Значения: "да" / "нет" / "неизвестно"

Правила:
- РАЗРЕШЕНО перезаписывать уже заполненные поля если пользователь их исправляет
- Извлекай все поля которые пользователь упоминает в сообщении
- Для vehicle_a_version: обнови с учётом исправления
- Верни ТОЛЬКО валидный JSON без пояснений и markdown

Сообщение пользователя: "{message}"
"""

# ---------------------------------------------------------------------------
# Промпт анализа вины
# ---------------------------------------------------------------------------

_FAULT_ANALYSIS_PROMPT = """\
Ты — эксперт по Правилам дорожного движения РФ. Проанализируй обстоятельства ДТП
и определи виновного на основе ПДД.

Контекст из базы знаний (ПДД):
{context}

Структурированные данные о ДТП:
{dtp_data}

История диалога (дополнительный контекст):
{history}

ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА ПО СИГНАЛАМ СВЕТОФОРА (ПДД РФ, раздел 6):
- Зелёный сигнал — движение разрешено
- Красный сигнал — движение ЗАПРЕЩЕНО, водитель обязан остановиться
- Жёлтый мигающий / Мигающий жёлтый — светофор работает в режиме
  предупреждения, перекрёсток считается НЕРЕГУЛИРУЕМЫМ.
  Водитель должен руководствоваться правилами проезда нерегулируемых
  перекрёстков (пп. 13.9, 13.11 ПДД), а НЕ правилами светофорного
  регулирования. Мигающий жёлтый НЕ является запрещающим сигналом.
- Если один участник ехал на красный, а другой на мигающий жёлтый:
  виновен тот, кто ехал на красный (нарушение п. 6.2, 6.13 ПДД).

ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА ПО ПРИОРИТЕТУ (ПДД РФ, раздел 13):
- Главная дорога имеет приоритет над второстепенной (п. 13.9)
- На равнозначном перекрёстке — помеха справа (п. 13.11)
- При нерегулируемом перекрёстке (мигающий жёлтый) действуют
  те же правила что и для нерегулируемых перекрёстков

ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА ПО МЕСТУ УДАРА:
- Если у ТС А повреждён перед, а у ТС Б — бок:
  А въехал в бок Б → А не уступил дорогу или не соблюдал приоритет
- Если у ТС А повреждён бок, а у ТС Б — перед:
  Б въехал в бок А → Б не уступил дорогу или не соблюдал приоритет
- Оба повреждены спереди → лобовое или встречное столкновение
- Учитывай impact_point_a и impact_point_b вместе с манёврами для точного вывода

ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА ПО ВЫЕЗДУ С ПРИЛЕГАЮЩЕЙ ТЕРРИТОРИИ (п. 8.3 ПДД):
- Выезд со двора, парковки, прилегающей территории →
  водитель ОБЯЗАН уступить дорогу всем участникам движения
- Если vehicle_b_origin содержит "двор", "парковка", "прилегающей территории" →
  второй участник нарушил п. 8.3 ПДД (при условии что А ехал по дороге)

ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА ПО ДОРОЖНЫМ ЗНАКАМ:
- Знак "Уступи дорогу" или "Стоп" у второго участника →
  он обязан был уступить (п. 13.9 ПДД)
- Знак "Главная дорога" у пользователя → он имел абсолютный приоритет

ДОКАЗАТЕЛЬНАЯ БАЗА (не влияет на вину, но важно для рекомендаций):
- Если has_dashcam_a = "да" → в reasoning укажи что нужно сохранить запись
- Если has_dashcam_b = "да" → в reasoning укажи что стоит запросить запись
- Наличие регистраторов влияет на рекомендацию по стратегии

ЗАДАЧА:
1. Определи виновного строго на основе ПДД и приведённых данных
2. Приведи конкретные пункты ПДД которые были нарушены
3. Объясни логику вывода понятным языком
4. Оцени уверенность от 0.0 до 1.0

ПРАВИЛА АНАЛИЗА:
- КРИТИЧЕСКИ ВАЖНО: мигающий жёлтый НЕ запрещает движение
- Если traffic_light_state_b = "красный" — второй участник нарушил п. 6.13 ПДД
- Анализируй impact_point_a + impact_point_b вместе — они часто определяют вину
- Если vehicle_b_origin указывает на выезд с прилегающей территории →
  это сильный аргумент вины второго участника (п. 8.3)
- Если has_dashcam_a = "да" → добавь в reasoning совет сохранить запись
- Если данных недостаточно — снизь confidence и укажи что нужно уточнить
- Не выдумывай статьи и пункты ПДД которых нет в контексте
- Учитывай все версии: vehicle_a_version, vehicle_b_version и слоты

Верни ТОЛЬКО валидный JSON без пояснений и markdown:
{{
    "fault": "A" / "B" / "both" / "unclear",
    "confidence": число от 0.0 до 1.0,
    "reasoning": [
        "пункт 1 объяснения",
        "пункт 2 объяснения"
    ],
    "pdd_references": ["13.9", "8.1"],
    "summary": "краткий вывод одним предложением для пользователя",
    "needs_clarification": true/false
}}
"""

_FALLBACK_ANALYSIS = (
    "Не удалось провести автоматический анализ. "
    "Рекомендую зафиксировать ДТП через приложение «Помощник ОСАГО» "
    "или «Госуслуги.Авто» — это позволит получить выплату до 200 000 руб. "
    "даже при наличии разногласий."
)

_SKIP_PHRASES: frozenset[str] = frozenset({
    "не знаю", "не помню", "не заметил", "не заметила",
    "не уверен", "не уверена", "пропустить", "пропусти",
    "дальше", "следующий", "skip",
})


# ---------------------------------------------------------------------------
# Извлечение слотов из сообщения
# ---------------------------------------------------------------------------

def _extract_slots_from_message(
    giga,
    message: str,
    current_slot: str,
    known_data: dict,
    allow_overwrite: bool = False,
) -> dict:
    known_str = (
        "\n".join(f"  {k}: {v}" for k, v in known_data.items() if v is not None)
        or "  (нет данных)"
    )
    slot_label = SLOT_QUESTIONS.get(current_slot, current_slot)[:60]

    template = (
        _SLOT_EXTRACTION_OVERWRITE_PROMPT
        if allow_overwrite
        else _SLOT_EXTRACTION_PROMPT
    )

    prompt = template.format(
        current_slot_label=slot_label,
        known_data=known_str,
        message=message,
    )

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
        return {k: v for k, v in extracted.items() if v is not None}

    except Exception as e:
        print(f"[disagreement_helper] slot extraction error: {e}")
        return {}


# ---------------------------------------------------------------------------
# Анализ вины
# ---------------------------------------------------------------------------

def _analyze_fault(
    giga,
    d_slots: dict,
    context: str,
    history_text: str,
) -> dict:
    dtp_data = json.dumps(d_slots, ensure_ascii=False, indent=2)
    prompt = _FAULT_ANALYSIS_PROMPT.format(
        context=context,
        dtp_data=dtp_data,
        history=history_text or "(нет)",
    )

    try:
        payload = Chat(
            messages=[
                Messages(
                    role=MessagesRole.SYSTEM,
                    content=(
                        "Ты — эксперт по ПДД РФ. "
                        "Анализируй только на основе предоставленного контекста. "
                        "Отвечай только JSON."
                    ),
                ),
                Messages(role=MessagesRole.USER, content=prompt),
            ],
            temperature=0.1,
        )
        response = giga.chat(payload)
        content = response.choices[0].message.content.strip()

        if "```" in content:
            for part in content.split("```"):
                if part.strip().startswith("{"):
                    content = part.strip()
                    break

        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return _fallback_analysis_result()

        data = json.loads(match.group(0))
        if data.get("fault") not in ("A", "B", "both", "unclear"):
            data["fault"] = "unclear"
        confidence = float(data.get("confidence", 0.5))
        data["confidence"] = max(0.0, min(1.0, confidence))
        return data

    except Exception as e:
        print(f"[disagreement_helper] fault analysis error: {e}")
        return _fallback_analysis_result()


def _fallback_analysis_result() -> dict:
    return {
        "fault": "unclear",
        "confidence": 0.0,
        "reasoning": [],
        "pdd_references": [],
        "summary": _FALLBACK_ANALYSIS,
        "needs_clarification": True,
    }


# ---------------------------------------------------------------------------
# Формирование текста результата
# ---------------------------------------------------------------------------

def _build_result_message(analysis: dict) -> str:
    fault = analysis.get("fault", "unclear")
    confidence = analysis.get("confidence", 0.0)
    summary = analysis.get("summary", "")
    reasoning = analysis.get("reasoning", [])
    pdd_refs = analysis.get("pdd_references", [])

    fault_labels = {
        "A": "По данным анализа, нарушение допустили **вы** (ТС А).",
        "B": "По данным анализа, нарушение допустил **второй участник** (ТС Б).",
        "both": "По данным анализа, **оба участника** допустили нарушения.",
        "unclear": "Ситуация **неоднозначна** — однозначный вывод затруднён.",
    }
    header = fault_labels.get(fault, "Результат анализа:")

    if confidence >= 0.8:
        conf_label = "Уверенность высокая."
    elif confidence >= 0.6:
        conf_label = "Уверенность средняя — рекомендую зафиксировать ДТП через приложение."
    else:
        conf_label = (
            "Уверенность низкая — рекомендую вызвать ГИБДД "
            "или зафиксировать через приложение."
        )

    reasoning_text = ""
    if reasoning:
        items = "\n".join(f"• {r}" for r in reasoning)
        reasoning_text = f"\n\n**Обоснование:**\n{items}"

    pdd_text = ""
    if pdd_refs:
        pdd_text = f"\n\n**Пункты ПДД:** {', '.join(pdd_refs)}"

    return (
        f"{header}\n\n"
        f"{summary}\n\n"
        f"{conf_label}"
        f"{reasoning_text}"
        f"{pdd_text}"
        f"\n\n---\n\n"
        f"Вы согласны с этим выводом?\n\n"
        f"**Да** — продолжим оформление Европротокола\n"
        f"**Нет** — предложу варианты: фиксация через приложение или вызов ГИБДД"
    )


# ---------------------------------------------------------------------------
# Обработка ответа на результат анализа
# ---------------------------------------------------------------------------

_AGREE_PHRASES: frozenset[str] = frozenset({
    "да", "согласен", "согласна", "верно", "правильно",
    "ок", "ok", "хорошо", "принято", "продолжим", "продолжаем",
})

_DISAGREE_PHRASES: frozenset[str] = frozenset({
    "нет", "не согласен", "не согласна", "неверно",
    "неправильно", "не так", "спорю",
})


def _handle_result_response(query: str, slots: dict) -> StepResponse | None:
    q = query.strip().lower().rstrip("!.,?")

    if q in _AGREE_PHRASES:
        updated_slots = {
            k: v for k, v in slots.items()
            if k != "disagreement_slots"
        }
        updated_slots["disagreement"] = False
        updated_slots["disagreement_help_active"] = False

        return StepResponse(
            answer=(
                "Отлично! Раз разногласия урегулированы, продолжаем оформление. "
                "У всех участников ДТП есть действующие полисы ОСАГО?"
            ),
            step_completed=False,
            next_step=Step.STEP1,
            slots=updated_slots,
        )

    if q in _DISAGREE_PHRASES:
        updated_slots = {
            k: v for k, v in slots.items()
            if k != "disagreement_slots"
        }
        updated_slots["disagreement_help_active"] = False

        return StepResponse(
            answer=(
                "Понял. В таком случае есть два варианта:\n\n"
                "**1. Зафиксировать разногласия через приложение** "
                "(«Помощник ОСАГО» или «Госуслуги.Авто») — Европротокол возможен, "
                "максимальная выплата до **200 000 руб.**\n\n"
                "**2. Вызвать ГИБДД** (102) — если фиксация через приложение невозможна "
                "или один из участников отказывается.\n\n"
                "Какой вариант выбираете?"
            ),
            step_completed=False,
            next_step=Step.STEP1,
            slots=updated_slots,
        )

    return None


# ---------------------------------------------------------------------------
# Получение контекста из RAG
# ---------------------------------------------------------------------------

def _get_context(disagreement_db, query: str, d_slots: dict) -> str:
    search_parts = [query]
    maneuver_a = d_slots.get("vehicle_a_maneuver", "")
    maneuver_b = d_slots.get("vehicle_b_maneuver", "")
    road_type = d_slots.get("road_type", "")
    priority = d_slots.get("priority_signs", "")

    if road_type:
        search_parts.append(f"ДТП на {road_type}")
    if priority:
        search_parts.append(f"приоритет {priority}")
    if maneuver_a and maneuver_b:
        search_parts.append(f"{maneuver_a} и {maneuver_b} столкновение ПДД")

    search_query = " ".join(search_parts)

    if not disagreement_db:
        return "База знаний по разногласиям недоступна."
    try:
        docs = disagreement_db.similarity_search(search_query, k=4)
        return "\n\n---\n\n".join(d.page_content for d in docs)
    except Exception as e:
        print(f"[disagreement_helper] RAG error: {e}")
        return "База знаний временно недоступна."


# ---------------------------------------------------------------------------
# Главная функция
# ---------------------------------------------------------------------------

def run_disagreement_help(
    giga,
    query: str,
    history: list,
    slots: dict,
    disagreement_db,
) -> StepResponse:
    d_slots = init_disagreement_slots(slots.get("disagreement_slots"))

    # --- Детектируем коррекцию через LLM ---
    # Запускаем только если уже есть хоть один заполненный слот —
    # на пустых данных коррекция невозможна по определению
    has_any_data = any(
        v is not None and not k.startswith("_")
        for k, v in d_slots.items()
    )
    correction_detected = (
        _detect_correction_with_llm(giga, query, d_slots)
        if has_any_data
        else False
    )

    if correction_detected:
        # Сбрасываем флаг завершённого анализа — нужно пересчитать
        d_slots.pop("_analysis_done", None)
        d_slots.pop("_last_analysis", None)
        d_slots.pop("_clarifying_asked", None)

    # --- Если анализ уже проведён и нет коррекции — ждём ответа ---
    if d_slots.get("_analysis_done") and not correction_detected:
        result = _handle_result_response(query, slots)
        if result:
            return result
        updated_slots = {**slots, "disagreement_slots": d_slots}
        return StepResponse(
            answer=(
                "Пожалуйста, ответьте «да» если согласны с выводом, "
                "или «нет» если хотите рассмотреть другие варианты."
            ),
            step_completed=False,
            next_step=Step.STEP1,
            slots=updated_slots,
        )

    # --- Определяем текущий незаполненный слот ---
    current_slot = get_next_slot(d_slots) or ""

    # --- Пропуск слота ---
    q_lower = query.strip().lower()
    if (
        current_slot
        and q_lower in _SKIP_PHRASES
        and current_slot in SKIPPABLE_SLOTS
        and not correction_detected
    ):
        d_slots[current_slot] = "неизвестно"
        current_slot = get_next_slot(d_slots) or ""

    # --- Извлечение данных (с перезаписью если коррекция) ---
    extracted = _extract_slots_from_message(
        giga,
        query,
        current_slot,
        d_slots,
        allow_overwrite=correction_detected,
    )

    # При коррекции перезаписываем, при обычном вводе — только новые поля
    for k, v in extracted.items():
        if k in d_slots:
            if correction_detected or d_slots[k] is None:
                d_slots[k] = v

    # --- Уведомляем пользователя о принятой коррекции ---
    correction_note = ""
    if correction_detected and extracted:
        updated_fields = ", ".join(extracted.keys())
        correction_note = f"Принял исправление ({updated_fields}).\n\n"

    # --- Проверяем есть ли обязательные слоты с неопределённым значением ---
    uncertain_slot = get_uncertain_required_slot(d_slots)
    if uncertain_slot:
        updated_slots = {**slots, "disagreement_slots": d_slots}
        return StepResponse(
            answer=(
                f"{correction_note}"
                f"Мне нужно уточнить один важный момент."
                f"{SLOT_QUESTIONS[uncertain_slot]}"
            ),
            step_completed=False,
            next_step=Step.STEP1,
            slots=updated_slots,
        )

    # --- Проверяем готовность к анализу ---
    if are_required_slots_filled(d_slots):
        context = _get_context(disagreement_db, query, d_slots)
        history_text = build_history(history, component="classifier")

        analysis = _analyze_fault(giga, d_slots, context, history_text)
        confidence = analysis.get("confidence", 0.0)

        # Уточняющие вопросы при низкой уверенности
        if confidence < _CONFIDENCE_THRESHOLD and not d_slots.get("_clarifying_asked"):
            next_clarifying = get_next_clarifying_slot(d_slots)
            if next_clarifying:
                d_slots["_clarifying_asked"] = True
                updated_slots = {**slots, "disagreement_slots": d_slots}
                return StepResponse(
                    answer=(
                        f"{correction_note}"
                        "Для более точного анализа уточните ещё одну деталь.\n\n"
                        + SLOT_QUESTIONS[next_clarifying]
                    ),
                    step_completed=False,
                    next_step=Step.STEP1,
                    slots=updated_slots,
                )

        d_slots["_analysis_done"] = True
        d_slots["_last_analysis"] = analysis

        result_message = correction_note + _build_result_message(analysis)
        updated_slots = {**slots, "disagreement_slots": d_slots}

        return StepResponse(
            answer=result_message,
            step_completed=False,
            next_step=Step.STEP1,
            slots=updated_slots,
        )

    # --- Задаём следующий вопрос ---
    next_slot = get_next_slot(d_slots)

    if next_slot is None:
        updated_slots = {**slots, "disagreement_slots": d_slots}
        return StepResponse(
            answer=f"{correction_note}Все данные собраны. Провожу анализ...",
            step_completed=False,
            next_step=Step.STEP1,
            slots=updated_slots,
        )

    is_first_entry = all(
        v is None
        for k, v in d_slots.items()
        if not k.startswith("_")
    )

    if is_first_entry:
        intro = (
            "Чтобы разобраться в ситуации, мне нужно задать несколько вопросов. "
            "На основе ваших ответов я проведу анализ по ПДД и определю, "
            "кто вероятнее всего несёт ответственность.\n\n"
            "Если не знаете ответа — напишите «не знаю». "
            "Если ошиблись — напишите «я ошибся» и поправку.\n\n"
        )
        answer_text = intro + SLOT_QUESTIONS[next_slot]
    else:
        answer_text = correction_note + SLOT_QUESTIONS[next_slot]

    updated_slots = {**slots, "disagreement_slots": d_slots}

    return StepResponse(
        answer=answer_text,
        step_completed=False,
        next_step=Step.STEP1,
        slots=updated_slots,
    )