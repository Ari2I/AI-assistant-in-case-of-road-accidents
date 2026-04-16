"""
Матчер шаблонных ответов — двухуровневый.

Уровень 1 — Regex   (мгновенно, 0 токенов, 0 нейронной сети)
Уровень 2 — Semantic (sentence-transformers, ~5-20 мс, 0 токенов LLM)

Если оба уровня промахнулись — запрос уходит в LLM pipeline.
"""

import re
from typing import Optional

from templates.responses import TEMPLATES
from templates.semantic_matcher import semantic_match


def match_template(query: str) -> Optional[str]:
    """
    Ищет подходящий шаблонный ответ.

    Сначала пробует точное regex-совпадение, затем — семантическое.

    Args:
        query: сообщение пользователя (оригинал, без предобработки)

    Returns:
        Готовый текст ответа или None (передать дальше в LLM pipeline).
    """
    q = query.lower().strip()

    # ── Уровень 1: Regex ─────────────────────────────────────────────────────
    for key, data in TEMPLATES.items():
        for pattern in data["patterns"]:
            if re.search(pattern, q, re.IGNORECASE):
                return data["response"]

    # ── Уровень 2: Semantic ───────────────────────────────────────────────────
    return semantic_match(q)