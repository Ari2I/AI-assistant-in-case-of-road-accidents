"""
Stateless-эндпоинт для Шага 1 — Первоначальный сбор фактов ДТП.

Этот модуль реализует гибридный Stateless-подход:
- Бэкенд хранит состояние (слоты) и присылает их с каждым запросом
- Агент обновляет слоты на основе нового сообщения пользователя
- При заполненных слотах — сигнализирует о переходе на следующий шаг
- При незаполненных — генерирует уточняющий вопрос

Слоты Шага 1 (Блоки 0-5 алгоритма):
  - safety_confirmed: подтверждена ли безопасность (bool)
  - emergency_sign: выставлен ли аварийный знак (bool)
  - victims: есть ли пострадавшие (bool | None)
  - participants_count: количество участников ДТП (int | None)
  - osago_both: есть ли ОСАГО у обоих водителей (bool | None)
  - disagreement: есть ли разногласия между участниками (bool | None)
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from gigachat import GigaChat

from config import GIGA_AUTH
from agent.history import build_history
from agent.generator import generate_answer
from agent.algorithm import get_algorithm_slice

# =============================================================================
# КОНФИГУРАЦИЯ СЛОТОВ
# =============================================================================

# Определение слотов для Шага 1
SLOT_NAMES = Literal[
    "safety_confirmed",
    "emergency_sign",
    "victims",
    "participants_count",
    "osago_both",
    "disagreement",
]

# Описание слотов для промпта
SLOT_DESCRIPTIONS: dict[SLOT_NAMES, str] = {
    "safety_confirmed": "Подтверждена ли безопасность (нет пожара, дыма, запаха бензина)",
    "emergency_sign": "Включена ли аварийка и выставлен ли знак аварийной остановки",
    "victims": "Есть ли пострадавшие (любой вред здоровью)",
    "participants_count": "Количество транспортных средств в ДТП (2, 3+, 1)",
    "osago_both": "Есть ли действующий полис ОСАГО у обоих водителей",
    "disagreement": "Есть ли разногласия между участниками о виновности или обстоятельствах",
}

# Порядок заполнения слотов (соответствует алгоритму)
SLOT_ORDER: list[SLOT_NAMES] = [
    "safety_confirmed",
    "emergency_sign",
    "victims",
    "participants_count",
    "osago_both",
    "disagreement",
]

# Промпт для извлечения фактов из сообщения пользователя
_FACT_EXTRACTION_PROMPT = """\
Ты — модуль извлечения фактов ДТП из диалога.

История диалога:
{history}

Текущие известные факты (слоты):
{current_slots_json}

Новое сообщение пользователя: "{query}"

Твоя задача:
1. Проанализируй новое сообщение в контексте истории
2. Извлеки факты для каждого слота, если они стали известны
3. Верни обновлённые значения ТОЛЬКО для тех слотов, которые изменились

Слоты и их возможные значения:
{slot_descriptions}

Правила:
- Если пользователь дал новую информацию — обнови слот
- Если информация противоречива — приоритет у последнего сообщения
- Если информации нет — оставь слот без изменений (null)
- Для victims: true = есть пострадавшие, false = никто не пострадал
- Для participants_count: число участников (2, 3, 4...)
- Для bool-слотов: true/false/null

Верни ТОЛЬКО валидный JSON формата:
{{"safety_confirmed": true|false|null, "emergency_sign": true|false|null, ...}}
Указывай только слоты, которые нужно обновить. Не включай неизменённые слоты.
"""


# =============================================================================
# ТИПЫ ДАННЫХ
# =============================================================================

class SlotUpdateResult(dict):
    """Результат обновления слотов."""

    @property
    def updated_slots(self) -> dict[str, Any]:
        """Слоты, которые были обновлены."""
        return {k: v for k, v in self.items() if v is not None or k in self}

    @property
    def empty_slots(self) -> list[str]:
        """Список ещё не заполненных слотов."""
        # Вычисляется внешним кодом на основе полного состояния
        return []


class Step1Response(dict):
    """Ответ эндпоинта Шаг 1."""

    @property
    def slots(self) -> dict[str, Any]:
        """Обновлённые слоты."""
        return self.get("slots", {})

    @property
    def answer(self) -> str | None:
        """Текст ответа пользователю (если есть)."""
        return self.get("answer")

    @property
    def step_completed(self) -> bool:
        """Завершён ли Шаг 1."""
        return self.get("step_completed", False)

    @property
    def next_step(self) -> str | None:
        """Следующий шаг (если завершён текущий)."""
        return self.get("next_step")


# =============================================================================
# ОСНОВНАЯ ФУНКЦИЯ
# =============================================================================

def process_step1_query(
    query: str,
    current_slots: dict[str, Any],
    history: list[dict] | None = None,
) -> Step1Response:
    """
    Обрабатывает сообщение пользователя в рамках Шага 1 (сбор фактов ДТП).

    Stateless-подход: бэкенд присылает текущее состояние слотов,
    функция обновляет их и возвращает новое состояние.

    Args:
        query:         новое сообщение пользователя
        current_slots: текущие значения слотов от бэкенда
        history:       история диалога [{"query": ..., "answer": ...}, ...]

    Returns:
        Step1Response со структурой:
        {
            "slots": {...},           # обновлённые слоты
            "answer": "...",          # текст ответа (если нужен вопрос)
            "step_completed": false,  # флаг завершения шага
            "next_step": null         # имя следующего шага (если завершён)
        }
    """
    history = history or []

    # Инициализируем слоты значениями по умолчанию
    slots = _init_slots(current_slots)

    with _make_giga() as giga:
        # ШАГ 1: Извлекаем факты из нового сообщения
        slot_updates = _extract_facts(giga, query, slots, history)

        # Обновляем слоты
        slots.update(slot_updates)

        # ШАГ 2: Проверяем, все ли слоты заполнены
        empty_slots = _get_empty_slots(slots)

        if not empty_slots:
            # Все слоты заполнены — завершаем Шаг 1
            return Step1Response(
                slots=slots,
                answer=None,
                step_completed=True,
                next_step="step2_europrotocol_check",
            )

        # ШАГ 3: Генерируем уточняющий вопрос для первого пустого слота
        next_slot = empty_slots[0]
        answer = _generate_followup_question(
            giga, query, slots, next_slot, history
        )

        return Step1Response(
            slots=slots,
            answer=answer,
            step_completed=False,
            next_step=None,
        )


# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================

def _init_slots(current_slots: dict[str, Any]) -> dict[str, Any]:
    """Инициализирует слоты значениями по умолчанию."""
    slots = {
        "safety_confirmed": None,
        "emergency_sign": None,
        "victims": None,
        "participants_count": None,
        "osago_both": None,
        "disagreement": None,
    }
    # Применяем переданные значения
    for key, value in current_slots.items():
        if key in slots:
            slots[key] = value
    return slots


def _make_giga() -> GigaChat:
    """Создаёт клиент GigaChat."""
    return GigaChat(
        credentials=GIGA_AUTH,
        verify_ssl_certs=False,
        scope="GIGACHAT_API_B2B",
    )


def _extract_facts(
    giga: GigaChat,
    query: str,
    current_slots: dict[str, Any],
    history: list[dict],
) -> dict[str, Any]:
    """
    Извлекает факты ДТП из сообщения пользователя через LLM.

    Использует Function Calling-подобный подход: просит модель
    вернуть JSON с обновлёнными значениями слотов.
    """
    history_text = build_history(history, component="classifier")

    slot_descriptions_text = "\n".join(
        f"  - {key}: {desc}" for key, desc in SLOT_DESCRIPTIONS.items()
    )

    prompt = _FACT_EXTRACTION_PROMPT.format(
        history=history_text or "(начало диалога)",
        current_slots_json=json.dumps(current_slots, ensure_ascii=False),
        query=query,
        slot_descriptions=slot_descriptions_text,
    )

    try:
        response = giga.chat(prompt)
        text = response.choices[0].message.content.strip()

        # Парсим JSON из ответа
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            updates = json.loads(match.group(0))
            # Валидируем ключи
            return {
                k: v for k, v in updates.items()
                if k in SLOT_ORDER
            }
    except Exception as e:
        print(f"[step1] fact extraction error: {e}")

    return {}


def _get_empty_slots(slots: dict[str, Any]) -> list[str]:
    """Возвращает список ещё не заполненных слотов в порядке очередности."""
    empty = []
    for slot_name in SLOT_ORDER:
        value = slots.get(slot_name)
        # None означает «не заполнено»
        if value is None:
            empty.append(slot_name)
    return empty


def _generate_followup_question(
    giga: GigaChat,
    query: str,
    slots: dict[str, Any],
    target_slot: str,
    history: list[dict],
) -> str:
    """
    Генерирует уточняющий вопрос для заполнения указанного слота.

    Учитывает уже известные факты, чтобы не задавать лишних вопросов.
    """
    # Получаем блок алгоритма для текущего слота
    block = _slot_to_block(target_slot)
    algorithm_slice = get_algorithm_slice(block, window=0)

    # Формируем контекст известных фактов
    known_facts = _format_known_facts(slots)

    # История для генератора
    history_text = build_history(
        history, component="generator", category="first_steps"
    )

    # Системный промпт для вопроса
    system_prompt = f"""\
Ты — ДТП-ассистент на этапе сбора первоначальных фактов.

Известные факты на данный момент:
{known_facts}

Твоя текущая задача: узнать значение слота "{target_slot}".
Описание слота: {SLOT_DESCRIPTIONS.get(target_slot, "")}

=== АЛГОРИТМ (блок {block}) ===
{algorithm_slice}
=== КОНЕЦ АЛГОРИТМА ===

Правила:
1. Задай ОДИН чёткий вопрос пользователю, чтобы получить нужную информацию
2. Используй естественный, поддерживающий тон
3. Если вопрос может быть чувствительным (пострадавшие, вина) — будь тактичен
4. Не переспрашивай то, что уже известно (см. «Известные факты»)
5. Вопрос должен соответствовать текущему блоку алгоритма

Примеры хороших вопросов:
- Для safety_confirmed: «Вы сейчас в безопасности? Нет ли дыма, запаха бензина, огня?»
- Для victims: «Кто-нибудь пострадал в аварии? Вы, пассажиры, второй водитель?»
- Для participants_count: «Сколько машин участвовало в столкновении?»
- Для osago_both: «У вас есть полис ОСАГО? У второго водителя есть?»
- Для disagreement: «Вы с другим водителем согласны, кто виноват в ДТП?»

Сообщение пользователя: "{query}"
"""

    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ],
        "temperature": 0.3,
    }

    try:
        # Используем тот же интерфейс что и generator.py
        from gigachat.models import Chat, Messages, MessagesRole

        chat_payload = Chat(
            messages=[
                Messages(role=MessagesRole.SYSTEM, content=system_prompt),
                Messages(role=MessagesRole.USER, content=query),
            ],
            temperature=0.3,
        )

        response = giga.chat(chat_payload)
        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"[step1] question generation error: {e}")
        # Fallback: простой вопрос на основе слота
        return _fallback_question(target_slot)


def _fallback_question(slot_name: str) -> str:
    """Запасной вариант вопроса, если LLM недоступна."""
    fallbacks: dict[str, str] = {
        "safety_confirmed": (
            "Вы сейчас в безопасности? Нет ли угрозы пожара, дыма, "
            "запаха бензина? Если да — немедленно покиньте автомобиль."
        ),
        "emergency_sign": (
            "Вы включили аварийную сигнализацию и выставили знак "
            "аварийной остановки? Это обязательно по ПДД."
        ),
        "victims": (
            "Есть ли пострадавшие? Проверьте себя, пассажиров, "
            "второго водителя. Любая боль или травма — это пострадавший."
        ),
        "participants_count": (
            "Сколько транспортных средств участвовало в столкновении? "
            "Машины, мотоциклы, прицепы — всё считается."
        ),
        "osago_both": (
            "У вас есть действующий полис ОСАГО? У второго водителя "
            "тоже есть полис?"
        ),
        "disagreement": (
            "Вы с другим водителем согласны о том, кто виноват в ДТП, "
            "или есть разногласия?"
        ),
    }
    return fallbacks.get(slot_name, "Расскажите подробнее о ситуации.")


def _slot_to_block(slot_name: str) -> int:
    """Сопоставляет слот номеру блока алгоритма."""
    mapping: dict[str, int] = {
        "safety_confirmed": 0,      # Блок 0: Безопасность
        "emergency_sign": 1,        # Блок 1: Аварийка/знак
        "victims": 2,               # Блок 2: Пострадавшие
        "participants_count": 3,    # Блок 3: Участники
        "osago_both": 4,            # Блок 4: ОСАГО
        "disagreement": 5,          # Блок 5: Разногласия
    }
    return mapping.get(slot_name, 0)


def _format_known_facts(slots: dict[str, Any]) -> str:
    """Форматирует известные факты для промпта."""
    lines = []
    for slot_name in SLOT_ORDER:
        value = slots.get(slot_name)
        if value is not None:
            lines.append(f"  • {slot_name}: {value}")

    if not lines:
        return "  (пока ничего не известно)"

    return "\n".join(lines)


# =============================================================================
# УТИЛИТЫ ДЛЯ ТЕСТИРОВАНИЯ
# =============================================================================

def validate_slots(slots: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Валидирует структуру слотов.

    Returns:
        (is_valid, list_of_errors)
    """
    errors = []

    # Проверка наличия всех обязательных слотов
    for required_slot in SLOT_ORDER:
        if required_slot not in slots:
            errors.append(f"Missing required slot: {required_slot}")

    # Проверка типов значений
    if slots.get("safety_confirmed") is not None and \
       not isinstance(slots["safety_confirmed"], bool):
        errors.append("safety_confirmed must be bool or null")

    if slots.get("emergency_sign") is not None and \
       not isinstance(slots["emergency_sign"], bool):
        errors.append("emergency_sign must be bool or null")

    if slots.get("victims") is not None and \
       not isinstance(slots["victims"], bool):
        errors.append("victims must be bool or null")

    if slots.get("participants_count") is not None and \
       not isinstance(slots["participants_count"], int):
        errors.append("participants_count must be int or null")

    if slots.get("osago_both") is not None and \
       not isinstance(slots["osago_both"], bool):
        errors.append("osago_both must be bool or null")

    if slots.get("disagreement") is not None and \
       not isinstance(slots["disagreement"], bool):
        errors.append("disagreement must be bool or null")

    return len(errors) == 0, errors


# =============================================================================
# ПРИМЕР ИСПОЛЬЗОВАНИЯ (для локального тестирования)
# =============================================================================

if __name__ == "__main__":
    # Пример использования
    print("=== Тестирование Stateless Step 1 ===\n")

    # Начальное состояние
    current_slots = {}
    history = []

    # Симуляция диалога
    queries = [
        "Я попал в ДТП, что делать?",
        "Я в безопасности, машина стоит на обочине",
        "Аварийку включил, знак выставил",
        "Пострадавших нет, все целы",
        "Две машины столкнулись",
        "ОСАГО у меня есть, у второго нет",
        "Мы не согласны, кто виноват",
    ]

    for i, query in enumerate(queries, 1):
        print(f"\n--- Шаг {i} ---")
        print(f"Пользователь: {query}")

        result = process_step1_query(
            query=query,
            current_slots=current_slots,
            history=history,
        )

        current_slots = result.slots

        if result.step_completed:
            print(f"✓ Шаг 1 завершён! Переход на: {result.next_step}")
            print(f"Итоговые слоты: {json.dumps(current_slots, ensure_ascii=False, indent=2)}")
            break
        else:
            print(f"Бот: {result.answer}")
            history.append({"query": query, "answer": result.answer})

    print("\n=== Конец теста ===")