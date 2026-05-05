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


def _generate_field_instruction(field_id: str) -> tuple[str, str]:
    """Get instruction and question for a specific field."""
    config = FIELDS_CONFIG.get(field_id, {})
    return config.get("instruction", ""), config.get("prompt", "")


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