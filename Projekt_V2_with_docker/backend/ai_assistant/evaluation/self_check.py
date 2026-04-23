import json
import re
from typing import Tuple

from gigachat import GigaChat

_MIN_ANSWER_LENGTH = 30
_MAX_CONTEXT_CHARS = 1500  # обрезаем контекст чтобы не раздувать промпт

_PROMPT_TEMPLATE = """\
Ты эксперт по ДТП. Оцени качество ответа на вопрос пользователя.

Вопрос: {query}

Исходный ответ: {answer}

Контекст из базы знаний (фрагмент):
{context}

Критерии оценки:
1. Ответ содержит конкретные действия или чёткие объяснения
2. Ответ не противоречит контексту
3. Ответ не содержит выдуманных фактов или сумм

Если ответ хороший — оставь "final" без изменений.
Если плохой — перепиши его полностью.

Верни ТОЛЬКО валидный JSON, без пояснений и markdown:
{{"verdict": "GOOD" или "BAD", "confidence": число от 0.0 до 1.0, "issues": "что не так", "final": "готовый текст ответа"}}
"""

# Fallback confidence если парсинг упал, но ответ непустой
_FALLBACK_CONFIDENCE = 0.5


def improve_answer(
    giga: GigaChat,
    query: str,
    answer: str,
    context: str,
) -> Tuple[str, float, str, str]:
    # Обрезаем контекст — длинный RAG ломает JSON-ответ модели
    trimmed_context = context[:_MAX_CONTEXT_CHARS]
    if len(context) > _MAX_CONTEXT_CHARS:
        trimmed_context += "...[обрезано]"

    prompt = _PROMPT_TEMPLATE.format(
        query=query,
        answer=answer,
        context=trimmed_context,
    )

    try:
        review = giga.chat(prompt)
        text = review.choices[0].message.content

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            # JSON не найден — считаем ответ приемлемым, не обнуляем confidence
            return "GOOD", _FALLBACK_CONFIDENCE, "no json in response", answer

        data = json.loads(match.group(0))

        final = data.get("final", "").strip()
        if len(final) < _MIN_ANSWER_LENGTH:
            final = answer

        # Если confidence не пришёл или 0 — ставим fallback
        raw_confidence = data.get("confidence")
        try:
            confidence = float(raw_confidence)
            if confidence == 0.0:
                confidence = _FALLBACK_CONFIDENCE
        except (TypeError, ValueError):
            confidence = _FALLBACK_CONFIDENCE

        return (
            data.get("verdict", "GOOD"),
            confidence,
            data.get("issues", ""),
            final,
        )

    except (json.JSONDecodeError, AttributeError, IndexError):
        # При любой ошибке парсинга — не обнуляем, возвращаем исходный ответ
        return "GOOD", _FALLBACK_CONFIDENCE, "parse error", answer