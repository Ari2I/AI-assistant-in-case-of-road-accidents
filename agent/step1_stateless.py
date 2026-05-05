"""
Step 1: Stateless fact collection and early exit logic.
Collects minimal facts to determine if Europrotocol is applicable.
Supports flexible input (multiple slots per message) and context passing.
"""

from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

from config import GIGA_AUTH
from agent.history import build_history


class Step1Result(BaseModel):
    """Result of Step 1 processing."""
    finished: bool = False
    next_step: str = "step1_collect_facts"
    stop_factor: Optional[str] = None
    instruction: str = ""
    extracted_data: Dict[str, Any] = Field(default_factory=dict)
    missing_slots: List[str] = Field(default_factory=list)
    question: str = ""


# Define slots and their order for questioning
SLOTS_ORDER = [
    "safety_measures",
    "victims",
    "participants_count",
    "osago_status",
    "disagreement",
]

STOP_FACTORS_MAP = {
    "victims": "call_gibdd_victims",
    "participants_count": "call_gibdd_participants",
    "osago_status": "call_gibdd_osago",
}

STEP1_EXTRACTION_PROMPT = """\
Ты — ассистент по сбору фактов о ДТП для определения возможности оформления Европротокола.

Твоя задача: извлечь из сообщения пользователя следующие данные (если они упоминаются):

1. safety_measures (bool) — включил ли водитель аварийную сигнализацию и выставил ли знак аварийной остановки
2. victims (bool) — есть ли пострадавшие (люди, требующие медицинской помощи)
3. participants_count (int) — количество транспортных средств, участвовавших в ДТП
4. osago_status (bool) — есть ли у всех водителей действующие полисы ОСАГО
5. disagreement (bool) — есть ли разногласия между участниками ДТП

ПРАВИЛА:
- Извлекай ТОЛЬКО явные факты из сообщения. Не додумывай.
- Если факт не упомянут — не включай его в результат.
- Возвращай ответ ТОЛЬКО в формате JSON без лишних комментариев.
- Используй null для полей, которые не удалось извлечь.

Пример ответа:
{{
    "victims": false,
    "participants_count": 2,
    "osago_status": true
}}

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


def _extract_data_with_llm(giga: GigaChat, user_message: str) -> Dict[str, Any]:
    """Use LLM to extract structured data from user message."""
    prompt = STEP1_EXTRACTION_PROMPT.format(user_message=user_message)

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

    if data.get("osago_status") is False:
        return "call_gibdd_osago", "❌ У одного из водителей нет ОСАГО. Вызовите ГИБДД (102)."

    return None


def _get_next_question(filled_slots: List[str], context: Dict[str, Any]) -> str:
    """Generate the next single question based on missing slots."""
    for slot in SLOTS_ORDER:
        if slot not in filled_slots:
            # Skip asking if we already have the data in context from previous turns
            if slot in context and context[slot] is not None:
                continue

            questions = {
                "safety_measures": "Вы включили аварийную сигнализацию и выставили знак аварийной остановки?",
                "victims": "Есть ли пострадавшие в результате ДТП (люди, требующие медицинской помощи)?",
                "participants_count": "Сколько всего транспортных средств участвовало в ДТП?",
                "osago_status": "Есть ли у всех водителей действующие полисы ОСАГО?",
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
        new_extracted = _extract_data_with_llm(giga, user_message)

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
    all_slots_filled = all(slot in filled_slots for slot in SLOTS_ORDER)

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
    missing = [s for s in SLOTS_ORDER if s not in filled_slots]

    return Step1Result(
        finished=False,
        next_step="step1_collect_facts",
        instruction=f"Понял. {next_q}" if next_q else "Расскажите подробнее.",
        extracted_data=current_data,
        missing_slots=missing,
        question=next_q
    )