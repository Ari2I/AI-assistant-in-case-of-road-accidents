"""
GigaChat Function Calling клиент для извлечения фактов ДТП.

Использует нативный Function Calling GigaChat для надёжного парсинга
структурированных данных вместо regex-парсинга JSON из текста.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from utils.catalog import SUPPORTED_CHAT_MODELS
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

logger = logging.getLogger(__name__)

EXTRACT_ACCIDENT_FACTS_FUNCTION = {
    "name": "extract_accident_facts",
    "parameters": {
        "type": "object",
        "properties": {
            "has_injured": {"type": "boolean"},
            "participants_count": {"type": "integer"},
            "has_other_property_damage": {"type": "boolean"},
            "all_have_osago": {"type": "boolean"},
            "has_disagreements": {"type": "boolean"},
            "can_use_photo_fixation": {"type": "boolean"}
        },
        "required": []
    }
}

_EXTRACT_PROMPT = """\
Извлеки факты о ДТП из сообщения пользователя.

Сообщение: "{query}"

Если пользователь уже сообщил какие-то факты (есть пострадавшие, количество участников,
наличие ОСАГО, разногласия, возможность фотофиксации) — верни их в структурированном виде.

Если факт не упомянут — не включай его в результат или верни null.

Верни ТОЛЬКО JSON-объект с полями:
- has_injured: true/false (есть ли пострадавшие)
- participants_count: число (сколько участников ДТП)
- has_other_property_damage: true/false (повреждено ли другое имущество кроме авто)
- all_have_osago: true/false (есть ли ОСАГО у всех участников)
- has_disagreements: true/false (есть ли разногласия между участниками)
- can_use_photo_fixation: true/false (можно ли применить фотофиксацию)
"""


def extract_accident_facts(
    giga: GigaChat,
    query: str,
    model_override: str | None = None,
) -> dict[str, Any]:
    """
    Извлекает факты ДТП через Function Calling.

    Args:
        giga: активный клиент GigaChat
        query: сообщение пользователя
        model_override: переопределение модели (опционально)

    Returns:
        dict с извлечёнными фактами (может быть пустым если ничего не найдено)
    """
    messages = [
        Messages(role=MessagesRole.SYSTEM, content=_EXTRACT_PROMPT.format(query=query)),
        Messages(role=MessagesRole.USER, content=query),
    ]

    model = model_override
    if model and model not in SUPPORTED_CHAT_MODELS:
        logger.warning(f"Неподдерживаемая модель {model}, использую default")
        model = None

    try:
        payload = Chat(
            messages=messages,
            temperature=0.0,  # Максимально детерминированный ответ
            functions=[EXTRACT_ACCIDENT_FACTS_FUNCTION],
            function_call="auto",
        )

        if model:
            payload.model = model

        response = giga.chat(payload)

        # Проверяем есть ли function call в ответе
        message = response.choices[0].message
        if message.function_call and message.function_call.name == "extract_accident_facts":
            args = message.function_call.arguments or {}
            # Фильтруем None значения
            return {k: v for k, v in args.items() if v is not None}

        # Если функция не вызвана — пробуем распарсить текст как fallback
        text = response.choices[0].message.content or ""
        return _parse_facts_from_text(text)

    except Exception as e:
        error_msg = str(e)
        if "No such model" in error_msg and model:
            # Fallback: повторяем без явного указания модели
            logger.warning(f"Модель {model} не найдена, пробую без model_override")
            return invoke_with_fallback(giga, query)

        logger.error(f"Ошибка extract_accident_facts: {e}")
        return {}


def invoke_with_fallback(
    giga: GigaChat,
    query: str,
) -> dict[str, Any]:
    """
    Повторяет запрос без явного указания модели при ошибке "No such model".
    """
    messages = [
        Messages(role=MessagesRole.SYSTEM, content=_EXTRACT_PROMPT.format(query=query)),
        Messages(role=MessagesRole.USER, content=query),
    ]

    try:
        payload = Chat(
            messages=messages,
            temperature=0.0,
            functions=[EXTRACT_ACCIDENT_FACTS_FUNCTION],
            function_call="auto",
        )

        response = giga.chat(payload)
        message = response.choices[0].message

        if message.function_call and message.function_call.name == "extract_accident_facts":
            args = message.function_call.arguments or {}
            return {k: v for k, v in args.items() if v is not None}

        return _parse_facts_from_text(message.content or "")

    except Exception as e:
        logger.error(f"Ошибка invoke_with_fallback: {e}")
        return {}


def _parse_facts_from_text(text: str) -> dict[str, Any]:
    """
    Fallback: парсит факты из текстового ответа (если Function Calling не сработал).
    """
    # Пытаемся найти JSON в тексте
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            return {k: v for k, v in data.items() if v is not None}
        except (json.JSONDecodeError, AttributeError):
            pass

    # Keyword-based extraction как последний fallback
    facts = {}
    text_lower = text.lower()

    if any(kw in text_lower for kw in ["пострадавш", "ранен", "травм"]):
        facts["has_injured"] = True
    elif "без пострадавших" in text_lower or "никто не пострадал" in text_lower:
        facts["has_injured"] = False

    if any(kw in text_lower for kw in ["разноглас", "не соглас", "спор"]):
        facts["has_disagreements"] = True
    elif "без разногласий" in text_lower or "согласны" in text_lower:
        facts["has_disagreements"] = False

    if any(kw in text_lower for kw in ["осаго", "страховк"]):
        if "нет осаго" in text_lower or "без страховки" in text_lower:
            facts["all_have_osago"] = False
        elif "есть осаго" in text_lower or "у всех осаго" in text_lower:
            facts["all_have_osago"] = True

    return facts