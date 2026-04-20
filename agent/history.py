"""
Адаптивное формирование истории диалога для разных компонентов pipeline.

Проблема фиксированного окна:
  - Маленькое (3 сообщения) — классификатор теряет контекст середины диалога,
    генератор не знает, что пользователь уже сообщил о повреждениях и участниках.
  - Большое (всё) — фильтр темы получает 20 сообщений ради проверки одного,
    planner путается в старых ветках диалога.

Решение — каждый компонент получает ровно столько истории, сколько ему нужно:

  filter         → 2 реплики  (нужно понять, не сменил ли пользователь тему)
  classifier     → 5 реплик   (нужно отследить переход между этапами)
  planner        → 4 реплики  (нужно определить текущий блок алгоритма)
  self_check     → 3 реплики  (нужно проверить, что ответ не противоречит диалогу)

  generator зависит от КАТЕГОРИИ:
    first_steps             → 4   (ситуация свежая, ранний контекст не нужен)
    europrotocol_impossible → 3   (нужно объяснить почему — достаточно последнего)
    europrotocol_possible   → 6   (нужно знать, что уже установлено: ОСАГО, фиксация)
    insurance_communication → 7   (нужна предыстория: виновник/потерпевший, суммы)
    filling_europrotocol    → ALL (нужны все данные: марки, повреждения, участники)

Для filling_europrotocol история дополнительно форматируется с блоком
«Данные из разговора» — чтобы генератор не перечитывал весь диалог,
а получил выжимку ключевых фактов.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Лимиты по компонентам (в репликах, одна реплика = Q + A)
# ---------------------------------------------------------------------------
_COMPONENT_LIMITS: dict[str, int | None] = {
    "filter": 2,
    "classifier": 5,
    "planner": 4,
    "self_check": 3,
}

# Лимиты генератора по категориям (None = вся история)
_GENERATOR_LIMITS: dict[str, int | None] = {
    "first_steps": 4,
    "europrotocol_impossible": 3,
    "europrotocol_possible": 6,
    "insurance_communication": 7,
    "filling_europrotocol": None,  # вся история — генератор должен знать все детали
}

# Ключевые слова для извлечения данных из истории в блок «Данные из разговора»
# (используется только для filling_europrotocol, чтобы структурировать длинную историю)
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
        component: "filter" | "classifier" | "planner" | "generator" | "self_check"
        category:  категория запроса (нужна только для component="generator")

    Returns:
        Отформатированная строка истории для передачи в LLM.
        Пустая строка если история пуста или не нужна.
    """
    if not history:
        return ""

    if component == "generator" and category:
        limit = _GENERATOR_LIMITS.get(category, 5)
    else:
        limit = _COMPONENT_LIMITS.get(component, 4)

    # Обрезаем историю (None = берём всё)
    slice_ = history if limit is None else history[-limit:]

    # Для filling_europrotocol добавляем структурированный блок данных
    if component == "generator" and category == "filling_europrotocol":
        return _format_with_data_summary(history, slice_)

    return _format_plain(slice_)


# ---------------------------------------------------------------------------
# Форматтеры
# ---------------------------------------------------------------------------

def _format_plain(slice_: list[dict]) -> str:
    """Простой формат Q/A для большинства компонентов."""
    return "\n".join(
        f"Q: {h['query']}\nA: {h['answer']}"
        for h in slice_
    )


def _format_with_data_summary(
    full_history: list[dict],
    recent_slice: list[dict],
) -> str:
    """
    Расширенный формат для filling_europrotocol.

    Структура:
      [ДАННЫЕ ИЗ РАЗГОВОРА]   — ключевые факты, упомянутые за весь диалог
      [ИСТОРИЯ ДИАЛОГА]       — все реплики (для контекста заполнения)

    Блок данных помогает генератору быстро найти нужные факты
    без перебора всего диалога.
    """
    # Собираем ключевые факты из всей истории
    data_lines: dict[str, list[str]] = {}

    for turn in full_history:
        combined = f"{turn['query']} {turn['answer']}".lower()
        for keyword, group in _DATA_KEYWORDS:
            if keyword in combined:
                # Берём исходный текст пользователя — там факты, а не интерпретации
                sentence = turn["query"].strip()
                if sentence and group not in data_lines:
                    data_lines[group] = []
                if sentence and sentence not in data_lines.get(group, []):
                    data_lines.setdefault(group, []).append(sentence)

    # Форматируем блок данных
    summary_parts = []
    for group, sentences in data_lines.items():
        # Берём не более 2 реплик на группу, чтобы не раздувать промпт
        summary_parts.append(f"  {group}: {' | '.join(sentences[:2])}")

    history_text = _format_plain(full_history)  # вся история

    if summary_parts:
        summary_block = "=== ДАННЫЕ ИЗ РАЗГОВОРА (для заполнения извещения) ===\n"
        summary_block += "\n".join(summary_parts)
        summary_block += "\n=== КОНЕЦ ДАННЫХ ===\n\n"
        return summary_block + history_text

    return history_text