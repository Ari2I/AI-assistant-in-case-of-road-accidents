"""
Фильтрация пользовательского ввода.

Два уровня защиты:
  1. Санитизация  — удаление специальных токенов и ограничение длины.
                    Применяется ко всем запросам без вызова LLM.
  2. Injection    — регулярные выражения по известным паттернам атак.
                    Применяется ко всем шагам, до любого вызова LLM.

Off-topic фильтрация в режиме консультанта реализована через поле
`relevant` в meta_classifier — см. agent/core.py, _run_consultant().
"""

from __future__ import annotations

import re
from typing import Tuple

# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------

_MAX_QUERY_LENGTH = 2000  # символов; длиннее — обрезаем

INJECTION_BLOCKED_MSG = (
    "Не могу обработать этот запрос. "
    "Задайте вопрос, связанный с оформлением ДТП или ОСАГО — я готов помочь."
)

OFFTOPIC_BLOCKED_MSG = (
    "Я ДТП-ассистент и специализируюсь только на помощи при дорожно-транспортных "
    "происшествиях и вопросах ОСАГО. Опишите вашу ситуацию — с удовольствием помогу."
)

# ---------------------------------------------------------------------------
# Паттерны prompt injection
# ---------------------------------------------------------------------------

# Русские формулировки
_INJECTION_RU = [
    r"игнорируй\s+(все\s+)?(предыдущие|прошлые|прежние)\s+(инструкции|правила|указания)",
    r"забудь\s+(все\s+)?(свои\s+)?(инструкции|правила|ограничения|системный\s+промпт)",
    r"ты\s+теперь\s+(являешься\s+)?(новым|другим|иным)\s+(ии|ботом|ассистентом|помощником)",
    r"отключи\s+(все\s+)?(свои\s+)?ограничения",
    r"новый\s+режим\s+работы",
    r"режим\s+разработчика",
    r"обход\s+защиты",
    r"раскрой\s+(свой\s+)?(системный\s+промпт|инструкции|контекст)",
    r"покажи\s+(свой\s+)?(системный\s+промпт|инструкции)",
    r"притворись\s+(что\s+ты\s+)?(другой|иной|не\s+ии)",
    r"действуй\s+как\s+(другой|иной|обычный)\s+(ии|ассистент|помощник)",
]

# Английские формулировки (пользователи иногда переключаются)
_INJECTION_EN = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?",
    r"disregard\s+(all\s+)?previous\s+instructions?",
    r"forget\s+(all\s+)?your\s+(previous\s+)?instructions?",
    r"you\s+are\s+now\s+(a\s+)?(new|different)\s+(ai|assistant|bot|llm)",
    r"disable\s+(all\s+)?restrictions?",
    r"override\s+(your\s+)?instructions?",
    r"reveal\s+(your\s+)?(system\s+prompt|instructions|context)",
    r"print\s+(your\s+)?system\s+prompt",
    r"\bjailbreak\b",
    r"\bDAN\s+mode\b",
    r"\bdeveloper\s+mode\b",
]

# Специальные токены форматирования, характерные для атак через шаблоны промптов
_INJECTION_TOKENS = [
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"\[INST\]",
    r"\[/INST\]",
    r"<<SYS>>",
    r"<</SYS>>",
    r"</?system>",
    r"</?user>",
    r"</?assistant>",
    # Попытки вставить маркеры ролей в текст
    r"###\s*System\s*:",
    r"###\s*Assistant\s*:",
    r"###\s*Instruction\s*:",
]

_INJECTION_REGEX = re.compile(
    "|".join(_INJECTION_RU + _INJECTION_EN + _INJECTION_TOKENS),
    re.IGNORECASE | re.DOTALL,
)

# ---------------------------------------------------------------------------
# Правила санитизации (применяются всегда, до проверки injection)
# ---------------------------------------------------------------------------

# (pattern, replacement) — заменяем опасные паттерны нейтральным символом
_SANITIZE_RULES: list[tuple[str, str]] = [
    # Специальные токены LLM → пробел
    (r"<\|.*?\|>", " "),
    (r"\[/?INST\]|<</?SYS>>", " "),
    (r"</?system>|</?user>|</?assistant>", " "),
    # Попытки через разделители вставить «системный» блок
    (r"###\s*(System|Assistant|Instruction|Human|AI)\s*:", "[filtered]"),
    # Нулевые байты и управляющие символы
    (r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " "),
    # Чрезмерно длинные последовательности одинаковых символов
    # (типичный паттерн при попытке «протолкнуть» инструкцию)
    (r"(.)\1{50,}", r"\1\1\1"),
]


def sanitize_input(query: str) -> str:
    """
    Очищает пользовательский ввод:
      - обрезает до _MAX_QUERY_LENGTH
      - удаляет специальные токены и управляющие символы
      - нормализует аномальные повторения символов

    Всегда возвращает строку, никогда не бросает исключений.
    """
    if not query:
        return query

    # Ограничение длины — до применения regex, чтобы не обрабатывать гигантские строки
    if len(query) > _MAX_QUERY_LENGTH:
        query = query[:_MAX_QUERY_LENGTH]

    for pattern, replacement in _SANITIZE_RULES:
        try:
            query = re.sub(pattern, replacement, query, flags=re.IGNORECASE)
        except Exception:
            pass  # Не падаем при непредвиденных ошибках regex

    return query.strip()


def detect_injection(query: str) -> bool:
    """
    Проверяет наличие паттернов prompt injection в тексте.

    Args:
        query: уже санитизированный запрос

    Returns:
        True если обнаружена попытка инъекции.
    """
    return bool(_INJECTION_REGEX.search(query))


def filter_input(query: str) -> Tuple[bool, str, str]:
    """
    Основная точка входа для фильтрации одного запроса.

    Порядок:
      1. Санитизация (применяется всегда)
      2. Проверка injection (блокировка при обнаружении)

    Args:
        query: исходное сообщение пользователя

    Returns:
        Кортеж (is_blocked, reason, sanitized_query), где:
          is_blocked      — True если запрос заблокирован
          reason          — "injection" | "" — причина блокировки
          sanitized_query — очищенный текст запроса (возвращается всегда)
    """
    if not query:
        return False, "", query

    sanitized = sanitize_input(query)

    if detect_injection(sanitized):
        print(f"[input_filter] injection blocked: {sanitized[:80]!r}")
        return True, "injection", sanitized

    return False, "", sanitized