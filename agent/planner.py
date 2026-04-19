import json
import re
from typing import Any

from gigachat import GigaChat

_FALLBACK_PLAN = {
    "intent": "unknown",
    "stage": "other",
    "answer_type": "explanation",
}

_PROMPT_TEMPLATE = """\
Ты определяешь текущий этап диалога по алгоритму ДТП-ассистента.

Этапы алгоритма:
- Блок 0: старт, безопасность
- Блок 1: аварийка и знак
- Блок 2: пострадавшие
- Блок 3: количество участников
- Блок 4: наличие ОСАГО
- Блок 5: разногласия
- Блок 6: фиксация
- Блок 7: заполнение извещения
- Блок 8: фотофиксация
- Блок 9: финальные действия

История диалога:
{history}

Новое сообщение:
{query}

Верни ТОЛЬКО валидный JSON:
{{
  "intent": "что хочет пользователь",
  "stage": "accident | europrotocol | insurance | dispute | other",
  "algorithm_block": число от 0 до 9,
  "answer_type": "steps | explanation | question"
}}
"""


def build_plan(giga: GigaChat, query: str, history_text: str) -> dict[str, Any]:
    """
    Определяет намерение пользователя и тип требуемого ответа.

    Args:
        giga: клиент GigaChat
        query: сообщение пользователя
        history_text: последние сообщения диалога

    Returns:
        Словарь с ключами intent, stage, answer_type.
        При ошибке парсинга возвращает _FALLBACK_PLAN.
    """
    prompt = _PROMPT_TEMPLATE.format(history=history_text, query=query)
    text = ""

    try:
        response = giga.chat(prompt)
        text = response.choices[0].message.content

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return _FALLBACK_PLAN

        return json.loads(match.group(0))

    except (json.JSONDecodeError, AttributeError, IndexError, ValueError) as e:
        print(f"[planner] parse error: {e}\nraw response: {text[:200]}")
        return _FALLBACK_PLAN