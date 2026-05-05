"""
Step 2: Interactive Europrotocol filling assistance.
Provides short instructions for each field and collects data for PDF generation.
Uses context from Step 1 to skip known fields.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

try:
    from gigachat.models import Message
except ImportError:
    pass

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


def _extract_field_data(message: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract data for any pending fields from the user message.
    In production, this uses LLM to map text to specific fields.
    Here we use simple keyword matching for demonstration.
    """
    updates = {}
    lower_msg = message.lower()

    # Simple heuristic extraction (Replace with LLM call in prod)
    if "datetime" not in context:
        if "сегодня" in lower_msg or "вчера" in lower_msg or ":" in message:
            # Mock extraction
            updates["datetime"] = message.split("?")[0].strip()

    if "location" not in context:
        if "ул." in lower_msg or "дом" in lower_msg or "км" in lower_msg:
            updates["location"] = message.split("?")[0].strip()

    # Add more extraction logic as needed...

    return updates


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

    # 1. Try to extract data from current message for ANY missing field
    new_data = _extract_field_data(user_message, collected)
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