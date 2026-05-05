"""
Локальный CLI для тестирования агента.
Запуск: python main_AI.py

История хранится в памяти на время сессии — имитирует то,
что в продакшне делает бэкенд.

Режимы тестирования:
  1. Основной агент (run_agent) — полный цикл по алгоритму
  2. Step 1 (stateless fact collection) — сбор фактов для Европротокола
  3. Step 2 (europrotocol filling) — пошаговое заполнение протокола
"""

from typing import Optional

from agent.core import run_agent, rate_answer
from agent.step1_stateless import process_step1_query, Step1Result
from agent.step2_europrotocol import process_step2_fill, Step2Result


def test_step1_mode() -> None:
    """Интерактивное тестирование Step 1 — сбор фактов о ДТП."""
    print("\n=== ТЕСТ STEP 1: Сбор фактов для Европротокола ===")
    print("Вводите данные о ДТП. Бот будет задавать уточняющие вопросы.")
    print("Команды: 'выход' — завершить, 'сброс' — начать заново\n")

    context: dict = {"step1_data": {}, "step1_filled_slots": []}

    while True:
        query = input("Ты: ").strip()

        if not query:
            continue
        if query.lower() == "выход":
            break
        if query.lower() == "сброс":
            context = {"step1_data": {}, "step1_filled_slots": []}
            print("Контекст сброшен. Начинаем заново.\n")
            continue

        result: Step1Result = process_step1_query(query, context)

        # Обновляем контекст для следующей итерации
        context["step1_data"] = result.extracted_data
        context["step1_filled_slots"] = [
            k for k, v in result.extracted_data.items() if v is not None
        ]

        print(f"\nБот: {result.instruction}")
        if result.question and not result.finished:
            print(f"Вопрос: {result.question}")
        if result.finished:
            print(f"\n✅ Этап завершён. Следующий шаг: {result.next_step}")
            if result.stop_factor:
                print(f"⚠️ Стоп-фактор: {result.stop_factor}")
            print(f"Собранные данные: {result.extracted_data}")
            print("\nНачинаем новый сценарий...\n")
            context = {"step1_data": {}, "step1_filled_slots": []}
        else:
            print(f"Заполнено слотов: {len(context['step1_filled_slots'])}/5")
            print(f"Осталось: {result.missing_slots}\n")


def test_step2_mode() -> None:
    """Интерактивное тестирование Step 2 — заполнение Европротокола."""
    print("\n=== ТЕСТ STEP 2: Заполнение Европротокола ===")
    print("Вводите данные для каждого поля протокола.")
    print("Команды: 'выход' — завершить, 'сброс' — начать заново\n")

    # Можно предварительно заполнить данные из Step 1
    context: dict = {
        "step2_data": {},
        "step1_data": {},  # Сюда можно передать данные из Step 1 при необходимости
    }

    while True:
        query = input("Ты: ").strip()

        if not query:
            continue
        if query.lower() == "выход":
            break
        if query.lower() == "сброс":
            context = {"step2_data": {}, "step1_data": {}}
            print("Контекст сброшен. Начинаем заново.\n")
            continue

        result: Step2Result = process_step2_fill(query, context)

        # Обновляем контекст
        context["step2_data"] = result.collected_data

        print(f"\nБот: {result.instruction}")
        if result.question and not result.finished:
            print(f"Запрос: {result.question}")
        if result.finished:
            print(f"\n✅ Протокол готов! Данные: {result.final_json}")
            print("\nНачинаем новый сценарий...\n")
            context = {"step2_data": {}, "step1_data": {}}
        else:
            print(f"Текущее поле: {result.current_field}")
            filled_count = len([k for k, v in result.collected_data.items() if v])
            print(f"Заполнено полей: {filled_count}/{len(FIELDS_ORDER_FOR_DISPLAY)}\n")


# Поля для отображения прогресса в Step 2
FIELDS_ORDER_FOR_DISPLAY = [
    "datetime", "location", "participant_a", "participant_b",
    "circumstances", "damage_description", "scheme", "signatures"
]


def select_mode() -> str:
    """Предлагает пользователю выбрать режим тестирования."""
    print("\n" + "=" * 50)
    print("ВЫБЕРИТЕ РЕЖИМ ТЕСТИРОВАНИЯ:")
    print("=" * 50)
    print("1. Полный агент (основной сценарий)")
    print("2. Step 1 — Сбор фактов (Европротокол)")
    print("3. Step 2 — Заполнение Европротокола")
    print("0. Выход")
    print("=" * 50)

    while True:
        choice = input("Ваш выбор (0-3): ").strip()
        if choice in ("0", "1", "2", "3"):
            return choice
        print("Неверный ввод. Введите число от 0 до 3.")


def main() -> None:
    """Главный цикл CLI с выбором режима."""
    print("\n🚗 ДТП-ассистент — CLI для тестирования")

    while True:
        mode = select_mode()

        if mode == "0":
            print("Завершение работы. До свидания!")
            break
        elif mode == "1":
            run_full_agent_mode()
        elif mode == "2":
            test_step1_mode()
        elif mode == "3":
            test_step2_mode()


def run_full_agent_mode() -> None:
    """Режим полного агента с историей диалога."""
    history: list[dict[str, str]] = []

    print("\n--- ПОЛНЫЙ АГЕНТ ---")
    print("Введите 'выход' для возврата в меню.\n")

    while True:
        query = input("Ты: ").strip()

        if not query:
            continue
        if query.lower() == "выход":
            break

        response = run_agent(query=query, history=history)
        answer = response["answer"]

        print(f"\nБот [{response['source']}]: {answer}\n")

        # Сохраняем в локальную историю — имитация бэкенда
        history.append({"query": query, "answer": answer})

        # Оценка ответа
        rating_input = input("Оцени ответ (0-5 или Enter): ").strip()
        if rating_input.isdigit():
            rating = int(rating_input)
            if 0 <= rating <= 5:
                result = rate_answer(query=query, answer=answer, rating=rating)
                print(f"Критик: {result['critic_score']}/5 — {result['critic_comment']}\n")


if __name__ == "__main__":
    main()