"""
Адаптивное формирование истории диалога для разных компонентов pipeline.

Изменения v2:
  - _format_plain нумерует реплики — модель может точно найти сообщение [N]
  - _format_with_data_summary: заголовок явно помечен как служебный,
    чтобы модель не воспроизводила лейблы групп как текст пользователя
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Лимиты по компонентам (в репликах, одна реплика = Q + A)
# ---------------------------------------------------------------------------
_COMPONENT_LIMITS: dict[str, int | None] = {
    "filter": 2,
    "classifier": 5,
    "self_check": 3,
}

# Лимиты генератора по категориям (None = вся история)
_GENERATOR_LIMITS: dict[str, int | None] = {
    "first_steps": 6,
    "europrotocol_impossible": 6,
    "europrotocol_possible": 8,
    "insurance_communication": 10,
    "filling_europrotocol": None,
}

# Ключевые слова для извлечения данных из истории в блок «Данные из разговора»
_DATA_KEYWORDS: list[tuple[str, str]] = [
    ("марк", "Транспортные средства"),
    ("модел", "Транспортные средства"),
    ("номер", "Госномера / полисы"),
    ("осаго", "Госномера / полисы"),
    ("полис", "Госномера / полисы"),
    ("повреждени", "Повреждения"),
    ("вмятин", "Повреждения"),
    ("царапин", "Повреждения"),
    ("трещин", "Повреждения"),
    ("бампер", "Повреждения"),
    ("крыл", "Повреждения"),
    ("виноват", "Вина / разногласия"),
    ("не виноват", "Вина / разногласия"),
    ("разногласи", "Вина / разногласия"),
    ("свидетел", "Свидетели"),
    ("адрес", "Место ДТП"),
    ("улиц", "Место ДТП"),
    ("перекрест", "Место ДТП"),
    ("километр", "Место ДТП"),
    ("трасс", "Место ДТП"),
]


def build_history(
    history: list[dict],
    component: str,
    category: str | None = None,
) -> str:
    """
    Формирует текст истории диалога под конкретный компонент pipeline.

    Args:
        history:   список реплик [{"query": ..., "answer": ...}, ...]
        component: "filter" | "classifier" | "generator" | "self_check"
        category:  категория запроса (нужна только для component="generator")

    Returns:
        Отформатированная строка истории для передачи в LLM.
        Пустая строка если история пуста.
    """
    if not history:
        return ""

    if component == "generator" and category:
        limit = _GENERATOR_LIMITS.get(category, 6)
    else:
        limit = _COMPONENT_LIMITS.get(component, 4)

    slice_ = history if limit is None else history[-limit:]

    if component == "generator" and category == "filling_europrotocol":
        return _format_with_data_summary(history, slice_)

    return _format_plain(slice_)


# ---------------------------------------------------------------------------
# Форматтеры
# ---------------------------------------------------------------------------

def _format_plain(slice_: list[dict]) -> str:
    """
    Нумерованный формат Q/A.

    Нумерация позволяет модели точно найти сообщение по номеру,
    когда пользователь спрашивает «каким было моё второе сообщение».
    """
    lines = []
    for i, h in enumerate(slice_, 1):
        lines.append(f"[{i}] Пользователь: {h['query']}")
        lines.append(f"[{i}] Ассистент: {h['answer']}")
    return "\n".join(lines)


def _format_with_data_summary(
    full_history: list[dict],
    recent_slice: list[dict],
) -> str:
    """
    Расширенный формат для filling_europrotocol.

    Структура:
      [СЛУЖЕБНЫЙ БЛОК]   — ключевые факты из всего диалога, только для модели
      [ИСТОРИЯ ДИАЛОГА]  — все реплики с нумерацией

    Заголовок служебного блока явно запрещает модели воспроизводить его содержимое
    как сообщения пользователя.
    """
    data_lines: dict[str, list[str]] = {}

    for turn in full_history:
        combined = f"{turn['query']} {turn['answer']}".lower()
        for keyword, group in _DATA_KEYWORDS:
            if keyword in combined:
                sentence = turn["query"].strip()
                if sentence and group not in data_lines:
                    data_lines[group] = []
                if sentence and sentence not in data_lines.get(group, []):
                    data_lines.setdefault(group, []).append(sentence)

    history_text = _format_plain(full_history)

    if not data_lines:
        return history_text

    summary_parts = []
    for group, sentences in data_lines.items():
        summary_parts.append(f"  {group}: {' | '.join(sentences[:2])}")

    summary_block = (
        "=== СЛУЖЕБНЫЙ БЛОК — ТОЛЬКО ДЛЯ ТЕБЯ, НЕ ПОКАЗЫВАЙ ПОЛЬЗОВАТЕЛЮ ===\n"
        "Факты из разговора для помощи при заполнении извещения:\n"
        + "\n".join(summary_parts)
        + "\n=== КОНЕЦ СЛУЖЕБНОГО БЛОКА ===\n\n"
    )

    return summary_block + history_text