"""
Диалоговый поток — детерминированная машина состояний для сбора фактов ДТП.

В отличие от meta_classifier.py, который определяет категорию вопроса,
этот модуль управляет переходами между шагами диалога по жёсткому сценарию.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# === Шаги диалога ===
STEP_ASK_INJURED = "ask_injured"
STEP_ASK_PARTICIPANTS = "ask_participants"
STEP_ASK_OTHER_DAMAGE = "ask_other_damage"
STEP_ASK_OSAGO = "ask_osago"
STEP_ASK_DISAGREEMENTS = "ask_disagreements"
STEP_ASK_PHOTO_FIXATION = "ask_photo_fixation"
STEP_READY_EUROPROTOCOL = "ready_europrotocol"
STEP_POLICE_REQUIRED = "police_required"
STEP_SPECIAL_CASE = "special_case"

# Терминальные шаги (сбор фактов завершён)
_TERMINAL_STEPS = frozenset([
    STEP_READY_EUROPROTOCOL,
    STEP_POLICE_REQUIRED,
    STEP_SPECIAL_CASE,
])

# === Банк вопросов (ротация чтобы не повторяться) ===
QUESTION_BANK: dict[str, list[str]] = {
    STEP_ASK_INJURED: [
        "Есть ли пострадавшие в результате ДТП?",
        "Пострадал ли кто-нибудь в аварии?",
        "Есть ли люди, которым нужна медицинская помощь?",
    ],
    STEP_ASK_PARTICIPANTS: [
        "Сколько всего участников ДТП (включая вас)?",
        "Какое количество транспортных средств задействовано?",
        "Сколько машин участвовало в столкновении?",
    ],
    STEP_ASK_OTHER_DAMAGE: [
        "Повреждено ли какое-либо другое имущество кроме автомобилей?",
        "Есть ли повреждения других объектов (забор, столб, здание)?",
        "Пострадало ли что-то ещё помимо транспортных средств?",
    ],
    STEP_ASK_OSAGO: [
        "Есть ли ОСАГО у всех участников ДТП?",
        "Все ли водители застрахованы по ОСАГО?",
        "Наличие полиса ОСАГО есть у каждого участника?",
    ],
    STEP_ASK_DISAGREEMENTS: [
        "Есть ли разногласия между участниками ДТП?",
        "Согласны ли все участники с обстоятельствами аварии?",
        "Есть ли споры о том, как произошло ДТП?",
    ],
    STEP_ASK_PHOTO_FIXATION: [
        "Можно ли применить фотофиксацию (есть ли смартфон с камерой)?",
        "Есть ли у вас возможность сделать фотографии места ДТП?",
        "Можете ли вы зафиксировать обстановку на фото?",
    ],
}

# === Упрощённые перефразировки при запросе уточнения ===
SIMPLE_REPHRASE: dict[str, list[str]] = {
    STEP_ASK_INJURED: [
        "Повторю вопрос: есть ли пострадавшие?",
        "Уточните: кто-нибудь пострадал?",
        "Нужно знать: есть ли раненые?",
    ],
    STEP_ASK_PARTICIPANTS: [
        "Сколько машин участвовало в ДТП?",
        "Назовите количество участников аварии.",
        "Сколько всего водителей задействовано?",
    ],
    STEP_ASK_OTHER_DAMAGE: [
        "Повреждено ли что-то кроме автомобилей?",
        "Есть ли ущерб другому имуществу?",
        "Пострадали ли другие объекты?",
    ],
    STEP_ASK_OSAGO: [
        "У всех есть действующий полис ОСАГО?",
        "Все ли застрахованы по ОСАГО?",
        "ОСАГО есть у каждого водителя?",
    ],
    STEP_ASK_DISAGREEMENTS: [
        "Все ли согласны с обстоятельствами ДТП?",
        "Есть ли разногласия между водителями?",
        "Спорите ли вы о том, как всё произошло?",
    ],
    STEP_ASK_PHOTO_FIXATION: [
        "Можете ли вы сделать фотографии?",
        "Есть ли у вас камера или смартфон?",
        "Возможно ли зафиксировать место ДТП на фото?",
    ],
}

# === Короткие подтверждения перед следующим вопросом ===
ACK_BY_STEP: dict[str, str] = {
    STEP_ASK_INJURED: "Понял.",
    STEP_ASK_PARTICIPANTS: "Хорошо.",
    STEP_ASK_OTHER_DAMAGE: "Ясно.",
    STEP_ASK_OSAGO: "Запомнил.",
    STEP_ASK_DISAGREEMENTS: "Принято.",
    STEP_ASK_PHOTO_FIXATION: "Отлично.",
}


@dataclass
class AIConversationFacts:
    """Структурированные факты о ДТП."""
    has_injured: bool | None = None
    participants_count: int | None = None
    has_other_property_damage: bool | None = None
    all_have_osago: bool | None = None
    has_disagreements: bool | None = None
    can_use_photo_fixation: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "has_injured": self.has_injured,
            "participants_count": self.participants_count,
            "has_other_property_damage": self.has_other_property_damage,
            "all_have_osago": self.all_have_osago,
            "has_disagreements": self.has_disagreements,
            "can_use_photo_fixation": self.can_use_photo_fixation,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AIConversationFacts":
        return cls(
            has_injured=data.get("has_injured"),
            participants_count=data.get("participants_count"),
            has_other_property_damage=data.get("has_other_property_damage"),
            all_have_osago=data.get("all_have_osago"),
            has_disagreements=data.get("has_disagreements"),
            can_use_photo_fixation=data.get("can_use_photo_fixation"),
        )


@dataclass
class AIConversationState:
    """Состояние диалога с машиной состояний."""
    current_step: str = STEP_ASK_INJURED
    scenario: str = "standard"  # standard, dispute_resolution, scheme_creation
    last_assistant_question: str = ""
    facts: AIConversationFacts = field(default_factory=AIConversationFacts)
    question_index: dict[str, int] = field(default_factory=dict)  # ротация вопросов

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_step": self.current_step,
            "scenario": self.scenario,
            "last_assistant_question": self.last_assistant_question,
            "facts": self.facts.to_dict(),
            "question_index": self.question_index,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AIConversationState":
        facts_data = data.get("facts", {})
        return cls(
            current_step=data.get("current_step", STEP_ASK_INJURED),
            scenario=data.get("scenario", "standard"),
            last_assistant_question=data.get("last_assistant_question", ""),
            facts=AIConversationFacts.from_dict(facts_data),
            question_index=data.get("question_index", {}),
        )


def is_terminal_step(step: str) -> bool:
    """Проверяет, является ли шаг терминальным (сбор фактов завершён)."""
    return step in _TERMINAL_STEPS


def get_next_question(step: str, state: AIConversationState) -> str:
    """
    Возвращает следующий вопрос для шага с ротацией.

    Args:
        step: текущий шаг
        state: состояние диалога

    Returns:
        текст вопроса
    """
    questions = QUESTION_BANK.get(step, ["Уточните детали."])

    # Получаем индекс для этого шага
    idx = state.question_index.get(step, 0)

    # Циклически перебираем вопросы
    question = questions[idx % len(questions)]

    # Обновляем индекс для следующего раза
    state.question_index[step] = (idx + 1) % len(questions)

    return question


def get_rephrase(step: str) -> str:
    """
    Возвращает упрощённую перефразировку вопроса.

    Args:
        step: текущий шаг

    Returns:
        текст перефразировки
    """
    rephrases = SIMPLE_REPHRASE.get(step, ["Уточните этот момент."])
    return rephrases[0]


def get_ack(step: str) -> str:
    """
    Возвращает короткое подтверждение для шага.

    Args:
        step: текущий шаг

    Returns:
        текст подтверждения
    """
    return ACK_BY_STEP.get(step, "Понял.")


def apply_facts_and_advance_step(
    state: AIConversationState,
    facts: dict[str, Any],
) -> AIConversationState:
    """
    Применяет извлечённые факты и продвигает машину состояний.

    Args:
        state: текущее состояние
        facts: новые факты от Function Calling

    Returns:
        новое состояние
    """
    new_state = AIConversationState(
        current_step=state.current_step,
        scenario=state.scenario,
        last_assistant_question=state.last_assistant_question,
        facts=AIConversationFacts.from_dict({
            **state.facts.to_dict(),
            **facts,
        }),
        question_index=state.question_index.copy(),
    )

    # Определяем следующий шаг на основе фактов
    next_step = _determine_next_step(new_state)
    new_state.current_step = next_step

    # Если шаг изменился — генерируем новый вопрос
    if next_step != state.current_step and not is_terminal_step(next_step):
        new_state.last_assistant_question = get_next_question(next_step, new_state)

    return new_state


def _determine_next_step(state: AIConversationState) -> str:
    """
    Определяет следующий шаг на основе собранных фактов.

    Логика:
    1. Если есть пострадавшие → сразу police_required
    2. Если участников > 2 → police_required
    3. Если нет ОСАГО у всех → police_required
    4. Иначе идём по шагам до photo_fixation → ready_europrotocol
    """
    facts = state.facts
    current = state.current_step

    # Проверяем условия для police_required
    if facts.has_injured is True:
        return STEP_POLICE_REQUIRED

    if facts.participants_count is not None and facts.participants_count > 2:
        return STEP_POLICE_REQUIRED

    if facts.all_have_osago is False:
        return STEP_POLICE_REQUIRED

    # Стандартный переход по шагам
    step_order = [
        STEP_ASK_INJURED,
        STEP_ASK_PARTICIPANTS,
        STEP_ASK_OTHER_DAMAGE,
        STEP_ASK_OSAGO,
        STEP_ASK_DISAGREEMENTS,
        STEP_ASK_PHOTO_FIXATION,
    ]

    try:
        current_idx = step_order.index(current)
    except ValueError:
        # Уже в терминальном шаге
        return current

    # Если это последний шаг — переходим к терминальному
    if current_idx == len(step_order) - 1:
        if facts.has_disagreements is True:
            return STEP_SPECIAL_CASE  # Разногласия — особый случай
        return STEP_READY_EUROPROTOCOL

    # Переходим к следующему шагу
    return step_order[current_idx + 1]


def build_known_facts_summary(state: AIConversationState) -> str:
    """
    Строит краткую сводку известных фактов для передачи в промпт.

    Args:
        state: текущее состояние

    Returns:
        текстовая сводка фактов
    """
    facts = state.facts
    lines = []

    if facts.has_injured is not None:
        lines.append(f"Пострадавшие: {'есть' if facts.has_injured else 'нет'}")

    if facts.participants_count is not None:
        lines.append(f"Участников: {facts.participants_count}")

    if facts.has_other_property_damage is not None:
        lines.append(f"Повреждение другого имущества: {'есть' if facts.has_other_property_damage else 'нет'}")

    if facts.all_have_osago is not None:
        lines.append(f"ОСАГО у всех: {'да' if facts.all_have_osago else 'нет'}")

    if facts.has_disagreements is not None:
        lines.append(f"Разногласия: {'есть' if facts.has_disagreements else 'нет'}")

    if facts.can_use_photo_fixation is not None:
        lines.append(f"Фотофиксация: {'возможна' if facts.can_use_photo_fixation else 'невозможна'}")

    if not lines:
        return "(факты ещё не собраны)"

    return "\n".join(lines)


def create_initial_state() -> AIConversationState:
    """Создаёт начальное состояние диалога."""
    return AIConversationState(
        current_step=STEP_ASK_INJURED,
        scenario="standard",
        last_assistant_question="",
        facts=AIConversationFacts(),
        question_index={},
    )