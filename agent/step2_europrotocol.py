"""
Step 2: Interactive Europrotocol filling assistance.
Provides short instructions for each field and collects data for PDF generation.
Uses context from Step 1 to skip known fields.
Uses LLM for intelligent field extraction instead of keyword matching.
"""

from __future__ import annotations

import json

from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

from config import GIGA_AUTH
from agent.step_types import Step, StepResponse

# Константы лимитов выплат по Европротоколу
LIMIT_BASE = 100_000
LIMIT_WITH_APP_NO_DISAGREEMENT = 400_000
LIMIT_WITH_APP_DISAGREEMENT = 200_000


# ---------------------------------------------------------------------------
# Проверка возможности Европротокола
# ---------------------------------------------------------------------------

class StopFactor:
    """Стоп-фактор, блокирующий или ограничивающий оформление Европротокола."""

    def __init__(self, code: str, message: str, severity: str):
        self.code = code
        self.message = message
        self.severity = severity

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "severity": self.severity}


class EuroprotocolCheckResult:
    """Результат проверки возможности оформления Европротокола."""

    def __init__(
        self,
        is_possible: bool | str,
        stop_factors: list,
        recommendation: str,
        next_step: str,
        limits: dict,
    ):
        self.is_possible = is_possible
        self.stop_factors = stop_factors
        self.recommendation = recommendation
        self.next_step = next_step
        self.limits = limits

    def to_dict(self) -> dict:
        return {
            "is_possible": self.is_possible,
            "stop_factors": [
                sf.to_dict() if hasattr(sf, "to_dict") else sf
                for sf in self.stop_factors
            ],
            "recommendation": self.recommendation,
            "next_step": self.next_step,
            "limits": self.limits,
        }


def validate_slots_for_step2(slots: dict) -> tuple[bool, list[str]]:
    """
    Валидирует слоты для Step 2.

    Обязательные ключи: victims, participants_count, osago_both, disagreement.
    None-значения допустимы; проверяются только типы ненулевых значений.

    Возвращает:
        (True, []) если валидно
        (False, [список ошибок]) иначе
    """
    required_keys = ["victims", "participants_count", "osago_both", "disagreement"]
    errors: list[str] = []

    for key in required_keys:
        if key not in slots:
            errors.append(f"Missing required slot: {key}")

    if errors:
        return (False, errors)

    if slots["victims"] is not None and not isinstance(slots["victims"], bool):
        errors.append(f"victims must be bool or None, got {type(slots['victims']).__name__}")

    if slots["participants_count"] is not None and not isinstance(slots["participants_count"], int):
        errors.append(
            f"participants_count must be int or None, got {type(slots['participants_count']).__name__}"
        )

    if slots["osago_both"] is not None and not isinstance(slots["osago_both"], bool):
        errors.append(f"osago_both must be bool or None, got {type(slots['osago_both']).__name__}")

    if slots["disagreement"] is not None and not isinstance(slots["disagreement"], bool):
        errors.append(f"disagreement must be bool or None, got {type(slots['disagreement']).__name__}")

    return (not bool(errors), errors)


def process_step2_check(slots: dict, has_app: bool) -> EuroprotocolCheckResult:
    """
    Проверяет возможность оформления Европротокола на основе собранных слотов.

    Логика (None-значения не считаются стоп-факторами):
      - Собирает все критические стоп-факторы (victims, participants, osago).
      - Если критические факторы есть → is_possible=False, next_step="call_gibdd".
      - Если разногласия есть, но нет приложения → is_possible="conditional".
      - Если разногласия есть + есть приложение → is_possible=True, лимит 200к.
      - Без разногласий → is_possible=True, лимит зависит от has_app.
    """
    stop_factors: list[StopFactor] = []

    if slots.get("victims") is True:
        stop_factors.append(StopFactor("victims", "Есть пострадавшие", "critical"))

    p_count = slots.get("participants_count")
    if p_count is not None:
        if p_count > 2:
            stop_factors.append(StopFactor("participants_3plus", "Участников больше двух", "critical"))
        elif p_count == 1:
            stop_factors.append(StopFactor("participants_1", "ДТП с одним участником", "critical"))

    if slots.get("osago_both") is False:
        stop_factors.append(StopFactor("no_osago", "Нет ОСАГО у одного из участников", "critical"))

    if stop_factors:
        parts = []
        for sf in stop_factors:
            if sf.code == "victims":
                parts.append("Немедленно вызовите скорую (103) и ГИБДД (102).")
            else:
                parts.append("Вызовите ГИБДД (102).")
        return EuroprotocolCheckResult(
            is_possible=False,
            stop_factors=stop_factors,
            recommendation=" ".join(parts),
            next_step="call_gibdd",
            limits={},
        )

    disagreement = slots.get("disagreement")

    if disagreement is True and not has_app:
        return EuroprotocolCheckResult(
            is_possible="conditional",
            stop_factors=[StopFactor("disagreement_no_app", "Разногласия без приложения", "warning")],
            recommendation=(
                "При разногласиях рекомендуется использовать приложение "
                "«Помощник ОСАГО» или «Госуслуги Авто» для фиксации ДТП."
            ),
            next_step="step3_fixation_with_disagreement",
            limits={"base": 0, "with_app": LIMIT_WITH_APP_DISAGREEMENT},
        )

    if disagreement is True and has_app:
        return EuroprotocolCheckResult(
            is_possible=True,
            stop_factors=[],
            recommendation="Европротокол возможен с приложением. Максимальная выплата до 200 000 руб.",
            next_step="step3_fixation",
            limits={"base": LIMIT_WITH_APP_DISAGREEMENT},
        )

    # Нет разногласий
    if has_app:
        limit = LIMIT_WITH_APP_NO_DISAGREEMENT
        recommendation = (
            f"Европротокол возможен. С приложением максимальная выплата до {limit // 1000} 000 руб."
        )
    else:
        limit = LIMIT_BASE
        recommendation = (
            f"Европротокол возможен. Максимальная выплата до {limit // 1000} 000 руб. "
            "Рекомендуется использовать приложение для увеличения лимита до 400 000 руб."
        )

    return EuroprotocolCheckResult(
        is_possible=True,
        stop_factors=[],
        recommendation=recommendation,
        next_step="step3_fixation",
        limits={"base": limit},
    )


# ---------------------------------------------------------------------------
# Заполнение полей Европротокола
# ---------------------------------------------------------------------------

FIELDS_CONFIG: dict[str, dict[str, str]] = {
    "datetime": {
        "prompt": "Когда произошло ДТП? (Дата и точное время)",
        "instruction": (
            "Укажите дату и время в формате ДД.ММ.ГГГГ ЧЧ:ММ. "
            "Это важно для фиксации времени обращения."
        ),
    },
    "location": {
        "prompt": "Где точно произошло ДТП? (Адрес, км трассы, ориентиры)",
        "instruction": (
            "Пишите полный адрес: город, улица, дом. Если трасса — название и километр. "
            "Укажите ближайшие ориентиры (магазин, светофор)."
        ),
    },
    "participant_a": {
        "prompt": "Данные владельца автомобиля А (ФИО, номер полиса ОСАГО).",
        "instruction": (
            "Нужны ФИО собственника ТС и номер полиса ОСАГО. "
            "Если вы водитель, но не собственник, укажите данные собственника."
        ),
    },
    "participant_b": {
        "prompt": "Данные владельца автомобиля Б (ФИО, номер полиса ОСАГО).",
        "instruction": (
            "Те же данные для второго участника. "
            "Сверьте номер полиса с базой РСА, если есть сомнения."
        ),
    },
    "circumstances": {
        "prompt": "Обстоятельства ДТП: какие маневры выполняли автомобили?",
        "instruction": (
            "Кратко опишите маневры. Пример: «Авто А двигалось прямо, Авто Б поворачивало налево». "
            "Отметьте знаки и сигналы светофора, если были."
        ),
    },
    "damage_description": {
        "prompt": "Опишите видимые повреждения обоих автомобилей.",
        "instruction": (
            "Перечислите детали: бампер, крыло, дверь, фара. "
            "Характер повреждения: царапина, вмятина, трещина. "
            "Не пишите скрытые повреждения."
        ),
    },
    "scheme": {
        "prompt": "Схема ДТП. (Опишите словами расположение авто после удара и направление движения)",
        "instruction": (
            "Опишите схему словами: «Авто А стояло у края дороги, Авто Б наехало на него сзади». "
            "Позже вы нарисуете это в бланке."
        ),
    },
    "signatures": {
        "prompt": "Подтвердите, что оба водителя подпишут извещение с обратной стороны.",
        "instruction": (
            "Важно: оба водителя должны поставить подписи на лицевой стороне "
            "(в колонках «А» и «Б») и на обороте бланка."
        ),
    },
}

FIELDS_ORDER = list(FIELDS_CONFIG.keys())

_FIELD_EXTRACTION_PROMPT = """\
Извлеки данные для Европротокола из сообщения пользователя.

Описание всех полей (что должно содержаться в каждом):
- datetime: дата и время ДТП в формате ДД.ММ.ГГГГ ЧЧ:ММ
- location: адрес места ДТП — город, улица, дом или км трассы
- participant_a: ФИО и номер полиса ОСАГО участника А
- participant_b: ФИО и номер полиса ОСАГО участника Б
- circumstances: какие манёвры выполняли автомобили (кто куда ехал, поворачивал, стоял)
- damage_description: перечень видимых повреждений каждого авто (вмятина, царапина, трещина)
- scheme: схема расположения авто ПОСЛЕ удара и направление движения (где стояли, с какой стороны столкнулись)
- signatures: подтверждение того, что оба водителя поставят подписи

Уже заполненные поля (не перезаписывай):
{filled_fields}

Поле, которое сейчас ожидается от пользователя: {current_field}
Остальные незаполненные поля: {empty_fields}

Сообщение пользователя: "{message}"

ПРАВИЛА:
- Если сообщение содержит данные для поля "{current_field}" — обязательно извлеки их.
- Если сообщение содержит данные и для других незаполненных полей — тоже извлеки.
- Не перезаписывай уже заполненные поля.
- Если данных для поля нет — верни null.
- Верни ТОЛЬКО валидный JSON без пояснений и markdown.

Пример ответа:
{{"scheme": "Авто А стояло у въезда, Авто Б въехало в правый бок"}}
"""


def _generate_field_instruction(field_id: str) -> tuple[str, str]:
    """Возвращает (инструкция, вопрос) для конкретного поля."""
    config = FIELDS_CONFIG.get(field_id, {})
    return config.get("instruction", ""), config.get("prompt", "")


def _map_slots_to_fields(slots: dict, history: list) -> dict:
    """
    Переносит релевантные данные из step1 в поля step2.
    Базовая версия возвращает пустой dict.
    """
    return {}


def _extract_fields_llm(
    giga: GigaChat,
    message: str,
    existing: dict,
    current_field: str = "",
) -> dict:
    """
    Вызывает GigaChat для извлечения полей Европротокола.
    При ошибке парсинга — возвращает {}.
    Делает до 2 попыток при пустом результате.
    """
    filled_str = (
        "\n".join(f"- {k}: {v}" for k, v in existing.items())
        if existing else "(нет заполненных полей)"
    )
    all_empty = [f for f in FIELDS_ORDER if not existing.get(f)]
    other_empty = [f for f in all_empty if f != current_field]
    empty_str = ", ".join(other_empty) if other_empty else "(только текущее поле)"

    prompt = _FIELD_EXTRACTION_PROMPT.format(
        filled_fields=filled_str,
        current_field=current_field or "не определено",
        empty_fields=empty_str,
        message=message,
    )

    for attempt in range(2):
        try:
            payload = Chat(
                messages=[
                    Messages(
                        role=MessagesRole.SYSTEM,
                        content=(
                            "Ты — структурированный экстрактор данных для Европротокола. "
                            "Отвечай только JSON. Никаких пояснений."
                        ),
                    ),
                    Messages(role=MessagesRole.USER, content=prompt),
                ],
                temperature=0.0,
            )
            response = giga.chat(payload)
            content = response.choices[0].message.content.strip()

            if "```" in content:
                for part in content.split("```"):
                    stripped = part.strip()
                    if stripped.startswith("{"):
                        content = stripped
                        break

            extracted = json.loads(content)
            result = {k: v for k, v in extracted.items() if v is not None}
            if result:
                return result

        except json.JSONDecodeError as e:
            print(f"[step2] JSON parse error (attempt {attempt + 1}): {e}, content: {content[:100]}")
        except Exception as e:
            print(f"[step2] field extraction error (attempt {attempt + 1}): {e}")

    return {}


# ---------------------------------------------------------------------------
# Главная функция для шагового режима
# ---------------------------------------------------------------------------

def process_step2_with_llm(
    giga: GigaChat,
    query: str,
    history: list,
    slots: dict,
    collected_fields: dict,
) -> StepResponse:
    """
    Обрабатывает один шаг заполнения Европротокола.
    Извлекает данные из сообщения, обновляет собранные поля
    и возвращает инструкцию по следующему полю или финальный JSON.
    """
    if not collected_fields:
        collected_fields = _map_slots_to_fields(slots, history)

    # Определяем текущее поле ДО извлечения — передаём как подсказку LLM
    current_field = next(
        (f for f in FIELDS_ORDER if not collected_fields.get(f)), None
    )

    try:
        new_data = _extract_fields_llm(giga, query, collected_fields, current_field or "")
        for k, v in new_data.items():
            if v is not None:
                collected_fields[k] = v
    except Exception as e:
        print(f"[step2] field extraction error: {e}")

    # Пересчитываем текущее поле после обновления
    current_field = next(
        (f for f in FIELDS_ORDER if not collected_fields.get(f)), None
    )

    if current_field is None:
        final_json = {
            "type": "europrotocol",
            "status": "ready_for_pdf",
            "data": collected_fields,
        }
        return StepResponse(
            answer=(
                "✅ Протокол заполнен! Направьте извещение в страховую "
                "компанию в течение 5 рабочих дней. "
                "Данные переданы для формирования PDF."
            ),
            step_completed=True,
            next_step=Step.DONE,
            collected_fields=collected_fields,
            final_json=final_json,
        )

    instr, question = _generate_field_instruction(current_field)
    return StepResponse(
        answer=f"{instr}\n\n{question}",
        step_completed=False,
        next_step=Step.STEP2,
        collected_fields=collected_fields,
    )