"""
Пошаговый мастер создания схемы ДТП.

6 этапов:
1. Схема перекрёстка
2. Подписание улиц
3. Знаки приоритета и разметка
4. Автомобиль А (пользователь)
5. Автомобиль Б (второй участник)
6. Место контакта и траектории
"""

from __future__ import annotations

import logging
from typing import Any

from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

logger = logging.getLogger(__name__)

# === Этапы создания схемы ===
STAGE_DRAW_INTERSECTION = "draw_intersection"
STAGE_LABEL_STREETS = "label_streets"
STAGE_ADD_SIGNS = "add_signs"
STAGE_DRAW_CAR_A = "draw_car_a"
STAGE_DRAW_CAR_B = "draw_car_b"
STAGE_MARK_CONTACT = "mark_contact"

# Порядок этапов
_STAGE_ORDER = [
    STAGE_DRAW_INTERSECTION,
    STAGE_LABEL_STREETS,
    STAGE_ADD_SIGNS,
    STAGE_DRAW_CAR_A,
    STAGE_DRAW_CAR_B,
    STAGE_MARK_CONTACT,
]

# Инструкции для каждого этапа
_STAGE_INSTRUCTIONS: dict[str, str] = {
    STAGE_DRAW_INTERSECTION: (
        "Нарисуйте схему перекрёстка или участка дороги, где произошло ДТП.\n"
        "Покажите форму пересечения (Т-образное, четырёхстороннее, круг), количество полос."
    ),
    STAGE_LABEL_STREETS: (
        "Подпишите названия улиц или дорог на схеме.\n"
        "Укажите направление движения по каждой улице (стрелками)."
    ),
    STAGE_ADD_SIGNS: (
        "Отметьте знаки приоритета и дорожную разметку.\n"
        "Светофоры, пешеходные переходы, остановочные карманы."
    ),
    STAGE_DRAW_CAR_A: (
        "Нарисуйте автомобиль А (ваш) на схеме.\n"
        "Покажите его положение ДО столкновения и направление движения."
    ),
    STAGE_DRAW_CAR_B: (
        "Нарисуйте автомобиль Б (второго участника).\n"
        "Покажите его положение ДО столкновения и направление движения."
    ),
    STAGE_MARK_CONTACT: (
        "Отметьте место первого контакта между автомобилями.\n"
        "Покажите траектории движения после удара (если были)."
    ),
}

# Триггерные фразы завершения этапа
_ADVANCE_MARKERS: dict[str, list[str]] = {
    STAGE_DRAW_INTERSECTION: [
        "готово", "нарисовал", "схема готова", "перекресток готов",
        "закончил", "всё", "дальше", "следующий этап",
    ],
    STAGE_LABEL_STREETS: [
        "подписал", "названия готово", "улицы подписал", "готово",
        "дальше", "следующий этап", "закончил",
    ],
    STAGE_ADD_SIGNS: [
        "знаки добавил", "разметку нанёс", "готово", "всё отметил",
        "дальше", "следующий этап", "закончил",
    ],
    STAGE_DRAW_CAR_A: [
        "машина а готова", "себя нарисовал", "автомобиль а", "готово",
        "дальше", "следующий этап", "закончил",
    ],
    STAGE_DRAW_CAR_B: [
        "машина б готова", "второго нарисовал", "автомобиль б", "готово",
        "дальше", "следующий этап", "закончил",
    ],
    STAGE_MARK_CONTACT: [
        "контакт отметил", "траектории готово", "схема завершена", "готово",
        "всё закончил", "финал", "завершил",
    ],
}

# Уточняющие вопросы по темам этапов
_CLARIFICATION_PROMPTS: dict[str, str] = {
    STAGE_DRAW_INTERSECTION: (
        "Если пользователь спрашивает что-то по теме этапа (форма перекрёстка, полосы),\n"
        "дай краткий ответ (1-3 предложения). Если вопрос не по теме — OFFTOPIC."
    ),
    STAGE_LABEL_STREETS: (
        "Если вопрос про названия улиц, направления — отвечай кратко.\n"
        "Не по теме — OFFTOPIC."
    ),
    STAGE_ADD_SIGNS: (
        "Если вопрос про знаки, разметку, светофоры — отвечай.\n"
        "Не по теме — OFFTOPIC."
    ),
    STAGE_DRAW_CAR_A: (
        "Если вопрос про положение автомобиля А, направление — отвечай.\n"
        "Не по теме — OFFTOPIC."
    ),
    STAGE_DRAW_CAR_B: (
        "Если вопрос про автомобиль Б — отвечай.\n"
        "Не по теме — OFFTOPIC."
    ),
    STAGE_MARK_CONTACT: (
        "Если вопрос про место удара, траектории — отвечай.\n"
        "Не по теме — OFFTOPIC."
    ),
}


def create_scheme_step(
    message: str,
    current_step: str,
    history: list[dict[str, str]] | None = None,
    giga: GigaChat | None = None,
) -> dict[str, Any]:
    """
    Обрабатывает шаг мастера создания схемы.

    Args:
        message: сообщение пользователя
        current_step: текущий этап
        history: история диалога (опционально)
        giga: клиент GigaChat для уточняющих вопросов (опционально)

    Returns:
        {
            "bot_response": str,
            "next_step": str,
            "stage_complete": bool,
            "completion_percentage": float,
        }
    """
    history = history or []

    # Проверяем, завершил ли пользователь этап
    stage_complete = _check_stage_completion(message, current_step)

    if stage_complete:
        # Переходим к следующему этапу
        next_step = _get_next_step(current_step)
        completion_pct = _calculate_completion(next_step)

        if next_step == current_step:
            # Уже последний этап
            bot_response = (
                "✅ Схема ДТП завершена!\n\n"
                "Теперь вы можете:\n"
                "- Сохранить изображение\n"
                "- Добавить пояснения в бланк Европротокола\n"
                "- Сфотографировать схему для приложения"
            )
        else:
            instruction = _STAGE_INSTRUCTIONS.get(next_step, "")
            bot_response = f"✅ Принято!\n\n📍 Следующий этап:\n{instruction}"

        return {
            "bot_response": bot_response,
            "next_step": next_step,
            "stage_complete": True,
            "completion_percentage": completion_pct,
        }

    # Проверяем, задаёт ли пользователь уточняющий вопрос по теме этапа
    if giga:
        clarification = _handle_clarification(message, current_step, history, giga)
        if clarification:
            return {
                "bot_response": clarification,
                "next_step": current_step,
                "stage_complete": False,
                "completion_percentage": _calculate_completion(current_step),
            }

    # Стандартный ответ — напоминаем инструкцию
    instruction = _STAGE_INSTRUCTIONS.get(current_step, "")
    bot_response = (
        f"📍 Текущий этап:\n{instruction}\n\n"
        "Когда закончите, напишите «готово» или «дальше»."
    )

    return {
        "bot_response": bot_response,
        "next_step": current_step,
        "stage_complete": False,
        "completion_percentage": _calculate_completion(current_step),
    }


def _check_stage_completion(message: str, current_step: str) -> bool:
    """
    Проверяет, содержит ли сообщение триггер завершения этапа.

    Args:
        message: сообщение пользователя
        current_step: текущий этап

    Returns:
        True если этап завершён
    """
    markers = _ADVANCE_MARKERS.get(current_step, [])
    message_lower = message.lower()

    return any(marker in message_lower for marker in markers)


def _get_next_step(current_step: str) -> str:
    """
    Возвращает следующий этап.

    Args:
        current_step: текущий этап

    Returns:
        следующий этап или текущий если последний
    """
    try:
        idx = _STAGE_ORDER.index(current_step)
    except ValueError:
        return STAGE_DRAW_INTERSECTION

    if idx >= len(_STAGE_ORDER) - 1:
        return current_step  # Последний этап

    return _STAGE_ORDER[idx + 1]


def _calculate_completion(current_step: str) -> float:
    """
    Вычисляет процент завершения.

    Args:
        current_step: текущий этап

    Returns:
        процент (0-100)
    """
    try:
        idx = _STAGE_ORDER.index(current_step)
    except ValueError:
        return 0.0

    # completion_percentage = round((next_step / 6) * 100, 2)
    # next_step = idx + 1 (следующий после текущего)
    next_step_num = idx + 1
    percentage = round((next_step_num / 6) * 100, 2)

    return min(percentage, 100.0)


def _handle_clarification(
    message: str,
    current_step: str,
    history: list[dict[str, str]],
    giga: GigaChat,
) -> str | None:
    """
    Обрабатывает уточняющий вопрос по теме этапа через LLM.

    Args:
        message: сообщение пользователя
        current_step: текущий этап
        history: история диалога
        giga: клиент GigaChat

    Returns:
        ответ или None если вопрос не по теме
    """
    topic_instruction = _CLARIFICATION_PROMPTS.get(current_step, "")

    system_prompt = (
        "Ты — помощник в создании схемы ДТП.\n"
        "Пользователь рисует схему поэтапно.\n\n"
        f"Текущий этап: {current_step}\n"
        f"{_STAGE_INSTRUCTIONS.get(current_step, '')}\n\n"
        f"{topic_instruction}\n\n"
        "Формат ответа:\n"
        "- Если вопрос ПО ТЕМЕ этапа: ANSWER: <1-3 предложения>\n"
        "- Если вопрос НЕ ПО ТЕМЕ: OFFTOPIC\n\n"
        "Будь краток, отвечай только по существу этапа."
    )

    history_text = "\n".join(
        f"[{i+1}] {h.get('query', '')} → {h.get('answer', '')}"
        for i, h in enumerate(history[-5:])  # Последние 5 сообщений
    )

    try:
        response = giga.chat(Chat(
            messages=[
                Messages(role=MessagesRole.SYSTEM, content=system_prompt),
                Messages(role=MessagesRole.USER, content=f"История:\n{history_text}\n\nВопрос: {message}"),
            ],
            temperature=0.0,
        ))

        answer = response.choices[0].message.content.strip()

        if answer.upper().startswith("OFFTOPIC"):
            return None

        if answer.upper().startswith("ANSWER:"):
            return answer[7:].strip()

        # Если модель не соблюла формат, но ответ похож на полезный
        if len(answer) < 200 and not any(kw in answer.lower() for kw in ["не знаю", "не могу"]):
            return answer

        return None

    except Exception as e:
        logger.error(f"Ошибка обработки уточнения: {e}")
        return None


def get_initial_instruction() -> str:
    """
    Возвращает начальную инструкцию для запуска мастера.

    Returns:
        текст инструкции
    """
    return (
        "🗺️ **Мастер создания схемы ДТП**\n\n"
        "Я помогу вам правильно нарисовать схему происшествия.\n"
        "Мы пройдём 6 этапов:\n\n"
        "1️⃣ Схема перекрёстка\n"
        "2️⃣ Подписание улиц\n"
        "3️⃣ Знаки и разметка\n"
        "4️⃣ Ваш автомобиль (А)\n"
        "5️⃣ Автомобиль второго участника (Б)\n"
        "6️⃣ Место контакта и траектории\n\n"
        "На каждом этапе я буду давать инструкцию.\n"
        "Когда закончите рисовать — напишите «готово» или «дальше».\n\n"
        "Начинаем?\n\n"
        f"📍 **Этап 1:** {_STAGE_INSTRUCTIONS[STAGE_DRAW_INTERSECTION]}"
    )


def get_scheme_steps_info() -> list[dict[str, Any]]:
    """
    Возвращает информацию обо всех этапах.

    Returns:
        список этапов с инструкциями
    """
    return [
        {
            "step": step,
            "order": i + 1,
            "instruction": _STAGE_INSTRUCTIONS[step],
            "markers": _ADVANCE_MARKERS[step],
        }
        for i, step in enumerate(_STAGE_ORDER)
    ]