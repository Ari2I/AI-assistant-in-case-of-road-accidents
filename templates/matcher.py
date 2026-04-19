"""
Матчер шаблонных ответов — переработанная архитектура.

Уровень 1 — Regex-whitelist (только очевидные случаи, узкие паттерны)
Уровень 2 — LLM-классификатор (понимает намерение, не просто слова)

Если оба уровня промахнулись — запрос уходит в полный LLM pipeline.

Изменения по сравнению с предыдущей версией:
  - Семантический матчер убран: давал слишком много ложных срабатываний
  - Regex сужен до "безопасных" однозначных паттернов (только приветствия)
  - LLM-классификатор добавлен как основной интеллектуальный уровень
  - match_template() принимает history и giga для передачи в классификатор
"""

import re
from typing import Optional

from gigachat import GigaChat

from templates.responses import TEMPLATES
from templates.llm_classifier import llm_classify


# ---------------------------------------------------------------------------
# Regex-whitelist — ТОЛЬКО однозначные паттерны без риска ложного срабатывания.
# Намеренно сужен: лучше пропустить в LLM, чем выдать неверный шаблон.
# ---------------------------------------------------------------------------
_SAFE_REGEX: dict[str, list[str]] = {
    # Чистое приветствие: короткое, без упоминания ДТП/аварии
    "greeting": [
        r"^(привет|хай|хелло|hi|hello)[\s!.]*$",
        r"^(добрый\s+(день|вечер|утро)|здравствуй(те)?)[\s!.]*$",
    ],
    # Запрос номеров телефонов — однозначно
    "emergency_numbers": [
        r"^(какой|какой номер|номер)\s+(телефона?\s+)?(полиции|гибдд|скорой|мчс|экстренн)[\w\s]*\??$",
        r"\b(куда|кому)\s+звонить\s+(при\s+дтп|при\s+аварии)\b",
    ],
}


def match_template(
    query: str,
    giga: Optional[GigaChat] = None,
    history_text: str = "",
) -> Optional[str]:
    """
    Ищет подходящий шаблонный ответ.

    Args:
        query:        сообщение пользователя (оригинал)
        giga:         активный клиент GigaChat (нужен для LLM-классификатора).
                      Если None — выполняется только regex-проверка.
        history_text: последние реплики диалога для контекста классификатора.

    Returns:
        Готовый текст ответа или None (передать дальше в LLM pipeline).
    """
    q = query.lower().strip()

    # ── Уровень 1: Regex-whitelist ───────────────────────────────────────────
    for key, patterns in _SAFE_REGEX.items():
        for pattern in patterns:
            if re.search(pattern, q, re.IGNORECASE):
                return TEMPLATES[key]["response"]

    # ── Уровень 2: LLM-классификатор ────────────────────────────────────────
    if giga is not None:
        category = llm_classify(giga, query, history_text)
        if category and category in TEMPLATES:
            return TEMPLATES[category]["response"]

    return None