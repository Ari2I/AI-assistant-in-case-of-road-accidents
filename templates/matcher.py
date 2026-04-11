"""
Матчер шаблонных ответов.
Работает на regex — без вызова LLM, без расхода токенов.
"""

import re
from typing import Optional

from templates.responses import TEMPLATES


def match_template(query: str) -> Optional[str]:
    """
    Ищет подходящий шаблонный ответ по ключевым словам.

    Args:
        query: сообщение пользователя

    Returns:
        Готовый ответ или None (передать в LLM pipeline).
    """
    q = query.lower().strip()

    for key, data in TEMPLATES.items():
        for pattern in data["patterns"]:
            if re.search(pattern, q, re.IGNORECASE):
                return data["response"]

    return None