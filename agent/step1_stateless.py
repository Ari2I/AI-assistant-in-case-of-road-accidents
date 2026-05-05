"""
Step 1: Stateless fact collection and early exit logic.
Collects minimal facts to determine if Europrotocol is applicable.
Supports flexible input (multiple slots per message) and context passing.
"""

from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

try:
    from gigachat.models import Message, Role
    from agent.prompts import STEP1_SYSTEM_PROMPT
except ImportError:
    # Fallback for local testing without full environment
    class Message:
        pass
    STEP1_SYSTEM_PROMPT = ""


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
    Extracts facts flexibly (multiple slots at once).
    Checks for early exit conditions.
    """
    # 1. Initialize state from context
    current_data = conversation_context.get("step1_data", {})
    filled_slots = conversation_context.get("step1_filled_slots", [])

    # 2. Simulate LLM Extraction (In real implementation, call LLM here)
    # For now, we assume the 'user_message' might contain keywords or
    # we rely on a previous turn's extraction.
    # In a real agentic flow, an LLM tool would parse 'user_message'
    # and update 'current_data' with new findings.

    # MOCK EXTRACTION LOGIC FOR DEMONSTRATION
    # In production, replace this block with an LLM call that extracts entities
    # and merges them into current_data.
    lower_msg = user_message.lower()

    if "пострадавш" in lower_msg or "больн" in lower_msg or "кровь" in lower_msg:
        current_data["victims"] = True
        if "victims" not in filled_slots:
            filled_slots.append("victims")

    if "нет пострадавш" in lower_msg or "все целы" in lower_msg or "без пострадавших" in lower_msg:
        current_data["victims"] = False
        if "victims" not in filled_slots:
            filled_slots.append("victims")

    if "два" in lower_msg or "2" in lower_msg or "две машины" in lower_msg:
        if "participants_count" not in current_data: # Don't overwrite if already set
             current_data["participants_count"] = 2
             if "participants_count" not in filled_slots:
                filled_slots.append("participants_count")

    if "три" in lower_msg or "3" in lower_msg or "много" in lower_msg:
        current_data["participants_count"] = 3
        if "participants_count" not in filled_slots:
            filled_slots.append("participants_count")

    if "осаго" in lower_msg and ("нет" in lower_msg or "не" in lower_msg):
        current_data["osago_status"] = False
        if "osago_status" not in filled_slots:
            filled_slots.append("osago_status")

    if "осаго" in lower_msg and ("есть" in lower_msg or "да" in lower_msg):
        current_data["osago_status"] = True
        if "osago_status" not in filled_slots:
            filled_slots.append("osago_status")

    if "аварийк" in lower_msg or "знак" in lower_msg:
        current_data["safety_measures"] = True
        if "safety_measures" not in filled_slots:
            filled_slots.append("safety_measures")

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