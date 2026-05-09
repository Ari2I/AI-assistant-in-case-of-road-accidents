"""
Step 2: Interactive Europrotocol filling assistance.
Provides short instructions for each field and collects data for PDF generation.
Uses context from Step 1 to skip known fields.
Uses LLM for intelligent field extraction instead of keyword matching.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

from config import GIGA_AUTH
from agent.step_types import Step, StepResponse

# Константы лимитов выплат по Европротоколу
LIMIT_BASE = 100_000
LIMIT_WITH_APP_NO_DISAGREEMENT = 400_000
LIMIT_WITH_APP_DISAGREEMENT = 200_000


class StopFactor:
    """Класс стоп-фактора для проверки возможности Европротокола."""

    def __init__(self, code: str, message: str, severity: str):
        self.code = code
        self.message = message
        self.severity = severity

    def to_dict(self) -> dict:
        """Возвращает словарь с полями стоп-фактора."""
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
        }


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
        """Возвращает словарь с полями результата."""
        return {
            "is_possible": self.is_possible,
            "stop_factors": [sf.to_dict() if hasattr(sf, 'to_dict') else sf for sf in self.stop_factors],
            "recommendation": self.recommendation,
            "next_step": self.next_step,
            "limits": self.limits,
        }


def validate_slots_for_step2(slots: dict) -> tuple[bool, list[str]]:
    """
    Валидирует слоты для Step 2.

    Обязательные ключи: victims, participants_count, osago_both, disagreement
    - victims: bool или None (не str)
    - participants_count: int или None (не str)
    - osago_both: bool или None
    - disagreement: bool или None

    None значения допустимы.

    Возвращает:
        (True, []) если валидно
        (False, [список ошибок]) иначе
    """
    required_keys = ["victims", "participants_count", "osago_both", "disagreement"]
    errors = []

    # Проверка наличия всех ключей
    for key in required_keys:
        if key not in slots:
            errors.append(f"Missing required slot: {key}")

    if errors:
        return (False, errors)

    # Проверка типов
    if slots["victims"] is not None and not isinstance(slots["victims"], bool):
        errors.append(f"victims must be bool or None, got {type(slots['victims']).__name__}")

    if slots["participants_count"] is not None and not isinstance(slots["participants_count"], int):
        errors.append(f"participants_count must be int or None, got {type(slots['participants_count']).__name__}")

    if slots["osago_both"] is not None and not isinstance(slots["osago_both"], bool):
        errors.append(f"osago_both must be bool or None, got {type(slots['osago_both']).__name__}")

    if slots["disagreement"] is not None and not isinstance(slots["disagreement"], bool):
        errors.append(f"disagreement must be bool or None, got {type(slots['disagreement']).__name__}")

    if errors:
        return (False, errors)

    return (True, [])

def process_step2_check(slots: dict, has_app: bool) -> EuroprotocolCheckResult:
    """
    Проверяет возможность оформления Европротокола.

    Логика:
    - Собирает все критические стоп-факторы (не останавливается на первом):
      * victims == True -> StopFactor("victims", severity="critical")
      * participants_count > 2 -> StopFactor("participants_3plus", severity="critical")
      * participants_count == 1 -> StopFactor("participants_1", severity="critical")
      * osago_both == False -> StopFactor("no_osago", severity="critical")
    - Если есть критические стоп-факторы: is_possible=False, next_step="call_gibdd"
    - Иначе если disagreement == True и has_app == False:
        is_possible="conditional", рекомендация упоминает приложения
    - Иначе если disagreement == True и has_app == True:
        is_possible=True, limits={"base": LIMIT_WITH_APP_DISAGREEMENT}
    - Иначе (нет разногласий):
        is_possible=True, limits зависит от has_app

    None-значения слотов не считаются стоп-факторами.
    """
    stop_factors = []

    # Сбор критических стоп-факторов
    if slots.get("victims") is True:
        stop_factors.append(StopFactor(
            code="victims",
            message="Есть пострадавшие",
            severity="critical",
        ))

    p_count = slots.get("participants_count")
    if p_count is not None:
        if p_count > 2:
            stop_factors.append(StopFactor(
                code="participants_3plus",
                message="Участников больше двух",
                severity="critical",
            ))
        elif p_count == 1:
            stop_factors.append(StopFactor(
                code="participants_1",
                message="ДТП с одним участником",
                severity="critical",
            ))

    if slots.get("osago_both") is False:
        stop_factors.append(StopFactor(
            code="no_osago",
            message="Нет ОСАГО у одного из участников",
            severity="critical",
        ))

    # Если есть критические стоп-факторы
    if stop_factors:
        # Формирование рекомендации
        rec_parts = []
        for sf in stop_factors:
            if sf.code == "victims":
                rec_parts.append("Немедленно вызовите скорую (103) и ГИБДД (102).")
            else:
                rec_parts.append("Вызовите ГИБДД (102).")
        recommendation = " ".join(rec_parts)

        return EuroprotocolCheckResult(
            is_possible=False,
            stop_factors=stop_factors,
            recommendation=recommendation,
            next_step="call_gibdd",
            limits={},
        )

    # Проверка разногласий
    disagreement = slots.get("disagreement")

    if disagreement is True and has_app is False:
        # Разногласия без приложения - условно возможен
        return EuroprotocolCheckResult(
            is_possible="conditional",
            stop_factors=[StopFactor(
                code="disagreement_no_app",
                message="Разногласия без приложения",
                severity="warning",
            )],
            recommendation="При разногласиях рекомендуется использовать приложение «Помощник ОСАГО» или «Госуслуги Авто» для фиксации ДТП.",
            next_step="step3_fixation_with_disagreement",
            limits={"base": 0, "with_app": LIMIT_WITH_APP_DISAGREEMENT},
        )

    if disagreement is True and has_app is True:
        # Разногласия с приложением - возможен, лимит 200к
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
        recommendation = f"Европротокол возможен. С приложением максимальная выплата до {limit // 1000} 000 руб."
    else:
        limit = LIMIT_BASE
        recommendation = f"Европротокол возможен. Максимальная выплата до {limit // 1000} 000 руб. Рекомендуется использовать приложение для увеличения лимита до 400 000 руб."

    return EuroprotocolCheckResult(
        is_possible=True,
        stop_factors=[],
        recommendation=recommendation,
        next_step="step3_fixation",
        limits={"base": limit},
    )


class EuroprotocolField(BaseModel):
    """Structure for a single field in the protocol."""
    field_id: str
    value: Optional[str] = None
    instruction: str = ""
    is_complete: bool = False

class Step2Result(BaseModel):
    """Result of Step 2 processing."""
    finished: bool = False
    next_step: str = "step2_fill_europrotocol"
    current_field: str = ""
    instruction: str = ""
    question: str = ""
    collected_data: Dict[str, Any] = Field(default_factory=dict)
    final_json: Optional[Dict[str, Any]] = None

# Definition of fields to collect
FIELDS_CONFIG = {
    "datetime": {
        "prompt": "Когда произошло ДТП? (Дата и точное время)",
        "instruction": "Укажите дату и время в формате ДД.ММ.ГГГГ ЧЧ:ММ. Это важно для фиксации времени обращения."
    },
    "location": {
        "prompt": "Где точно произошло ДТП? (Адрес, км трассы, ориентиры)",
        "instruction": "Пишите полный адрес: город, улица, дом. Если трасса — название и километр. Укажите ближайшие ориентиры (магазин, светофор)."
    },
    "participant_a": {
        "prompt": "Данные владельца автомобиля А (ФИО, номер полиса ОСАГО).",
        "instruction": "Нужны ФИО собственника ТС и номер полиса ОСАГО. Если вы водитель, но не собственник, укажите данные собственника."
    },
    "participant_b": {
        "prompt": "Данные владельца автомобиля Б (ФИО, номер полиса ОСАГО).",
        "instruction": "Те же данные для второго участника. Сверьте номер полиса с базой РСА, если есть сомнения."
    },
    "circumstances": {
        "prompt": "Обстоятельства ДТП: какие маневры выполняли автомобили? (Например: обгон, разворот, стоянка)",
        "instruction": "Кратко опишите маневры. Пример: 'Авто А двигалось прямо, Авто Б поворачивало налево'. Отметьте знаки и сигналы светофора, если были."
    },
    "damage_description": {
        "prompt": "Опишите видимые повреждения обоих автомобилей.",
        "instruction": "Перечислите детали: бампер, крыло, дверь, фара. Характер повреждения: царапина, вмятина, трещина. Не пишите скрытые повреждения."
    },
    "scheme": {
        "prompt": "Схема ДТП. (Опишите словами расположение авто после удара и направление движения)",
        "instruction": "Опишите схему словами: 'Авто А стояло у края дороги, Авто Б наехало на него сзади'. Позже вы нарисуете это в бланке."
    },
    "signatures": {
        "prompt": "Подтвердите, что оба водителя подпишут извещение с обратной стороны.",
        "instruction": "Важно: оба водителя должны поставить подписи на лицевой стороне (в колонках 'А' и 'Б') и на обороте бланка."
    }
}

FIELDS_ORDER = list(FIELDS_CONFIG.keys())


STEP2_EXTRACTION_PROMPT = """\
Ты — ассистент по заполнению Европротокола. Твоя задача: извлечь из сообщения пользователя данные для следующих полей (если они упоминаются):

Доступные поля:
- datetime: дата и время ДТП
- location: место ДТП (адрес, км трассы, ориентиры)
- participant_a: данные владельца автомобиля А (ФИО, номер полиса ОСАГО)
- participant_b: данные владельца автомобиля Б (ФИО, номер полиса ОСАГО)
- circumstances: обстоятельства ДТП (маневры автомобилей)
- damage_description: описание видимых повреждений
- scheme: схема ДТП (расположение автомобилей)
- signatures: подтверждение о подписях

ПРАВИЛА:
- Извлекай ТОЛЬКО явные данные из сообщения. Не додумывай.
- Если поле уже заполнено в существующих данных (показаны ниже), не извлекай его повторно.
- Возвращай ответ ТОЛЬКО в формате JSON без лишних комментариев.
- Используй null для полей, которые не удалось извлечь или которые уже заполнены.

Существующие данные (уже заполненные поля):
{existing_data}

Сообщение пользователя:
{user_message}

Пример ответа:
{{
    "location": "г. Москва, ул. Ленина, д. 10",
    "datetime": "15.01.2024 14:30"
}}
"""


def _make_giga() -> GigaChat:
    """Create GigaChat client instance."""
    return GigaChat(
        credentials=GIGA_AUTH,
        verify_ssl_certs=False,
        scope="GIGACHAT_API_B2B",
    )


def _extract_field_data_with_llm(giga: GigaChat, message: str, existing_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Use LLM to extract data for any pending fields from the user message.
    Returns only new/updated fields.
    """
    # Format existing data for prompt
    if existing_data:
        existing_str = "\n".join(f"- {k}: {v}" for k, v in existing_data.items())
    else:
        existing_str = "(нет заполненных полей)"

    prompt = STEP2_EXTRACTION_PROMPT.format(
        existing_data=existing_str,
        user_message=message
    )

    payload = Chat(
        messages=[
            Messages(role=MessagesRole.SYSTEM, content="Ты — структурированный экстрактор данных для Европротокола. Отвечай только JSON."),
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
        # Filter out None values and already filled fields
        return {
            k: v for k, v in extracted.items()
            if v is not None and k not in existing_data
        }
    except Exception as e:
        print(f"[step2] LLM extraction error: {e}")
        return {}

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
    """Get instruction and question for a specific field."""
    config = FIELDS_CONFIG.get(field_id, {})
    return config.get("instruction", ""), config.get("prompt", "")

def _map_slots_to_fields(slots: dict, history: list) -> dict:
    """
    Переносит релевантные данные из step1 в поля step2.
    Базовая версия: возвращает пустой dict.
    Расширенная версия может анализировать history на наличие
    адреса, времени, марок авто и предзаполнять соответствующие поля.
    """
    return {}


def _extract_fields_llm(giga, message: str, existing: dict, current_field: str = "") -> dict:
    """
    Вызывает GigaChat для извлечения полей Европротокола.
    При ошибке парсинга — возвращает {}.
    """
    import json
    from gigachat.models import Chat, Messages, MessagesRole

    filled_str = "\n".join(f"- {k}: {v}" for k, v in existing.items()) \
        if existing else "(нет заполненных полей)"

    all_empty = [f for f in FIELDS_ORDER if not existing.get(f)]
    # Убираем текущее поле из списка "остальных", чтобы не дублировать
    other_empty = [f for f in all_empty if f != current_field]
    empty_str = ", ".join(other_empty) if other_empty else "(только текущее поле)"

    prompt = _FIELD_EXTRACTION_PROMPT.format(
        filled_fields=filled_str,
        current_field=current_field or "не определено",
        empty_fields=empty_str,
        message=message,
    )

    for attempt in range(2):  # одна повторная попытка при ошибке
        try:
            payload = Chat(
                messages=[
                    Messages(
                        role=MessagesRole.SYSTEM,
                        content=(
                            "Ты — структурированный экстрактор данных для Европротокола. "
                            "Отвечай только JSON. Никаких пояснений."
                        )
                    ),
                    Messages(role=MessagesRole.USER, content=prompt),
                ],
                temperature=0.0,
            )
            response = giga.chat(payload)
            content = response.choices[0].message.content.strip()

            # Убираем markdown-обёртку если есть
            if "```" in content:
                parts = content.split("```")
                for part in parts:
                    stripped = part.strip()
                    if stripped.startswith("{"):
                        content = stripped
                        break

            extracted = json.loads(content)
            result = {k: v for k, v in extracted.items() if v is not None}

            if result:  # если что-то извлекли — успех
                return result
            # если пустой результат — попробуем ещё раз (может LLM вернула всё null)

        except json.JSONDecodeError as e:
            print(f"[step2] JSON parse error (attempt {attempt + 1}): {e}, content: {content[:100]}")
        except Exception as e:
            print(f"[step2] field extraction error (attempt {attempt + 1}): {e}")

    return {}


def process_step2_with_llm(
    giga,
    query: str,
    history: list,
    slots: dict,
    collected_fields: dict,
) -> StepResponse:

    if not collected_fields:
        collected_fields = _map_slots_to_fields(slots, history)

    # Определяем текущее ожидаемое поле ДО извлечения — передаём как подсказку
    current_field = next(
        (f for f in FIELDS_ORDER if not collected_fields.get(f)),
        None
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
        (f for f in FIELDS_ORDER if not collected_fields.get(f)),
        None
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

def process_step2_fill(
    user_message: str,
    conversation_context: Dict[str, Any]
) -> Step2Result:
    """
    Process Step 2: Fill protocol fields.
    Merges new data with context. Moves to next field if current is filled.
    """
    # Load existing data
    collected = conversation_context.get("step2_data", {})
    # Merge data from Step 1 if available (e.g., car models, circumstances)
    step1_data = conversation_context.get("step1_data", {})
    if step1_data:
        # Map relevant Step 1 data to Step 2 fields if logic allows
        pass

    # 1. Use LLM to extract data from current message for ANY missing field
    with _make_giga() as giga:
        new_data = _extract_field_data_with_llm(giga, user_message, collected)
    collected.update(new_data)

    # 2. Find the first incomplete field
    current_field = None
    for field in FIELDS_ORDER:
        if field not in collected or not collected[field]:
            current_field = field
            break

    # 3. If all fields are filled -> Finish
    if current_field is None:
        # Construct final JSON for backend
        final_payload = {
            "type": "europrotocol",
            "status": "ready_for_pdf",
            "data": collected
        }
        return Step2Result(
            finished=True,
            next_step="generate_pdf",
            instruction="✅ Протокол сформирован! Данные переданы для генерации PDF.",
            final_json=final_payload,
            collected_data=collected
        )

    # 4. Generate instruction for the current missing field
    instr, question = _generate_field_instruction(current_field)

    # If user just provided data for THIS field in the message, acknowledge it
    ack = ""
    if current_field in new_data:
        ack = f"Принято: {new_data[current_field]}. \n\n"

    return Step2Result(
        finished=False,
        next_step="step2_fill_europrotocol",
        current_field=current_field,
        instruction=f"{ack}{instr}",
        question=question,
        collected_data=collected
    )