"""
CLI для локального тестирования ДТП-ассистента.
Симулирует поведение Django-бэкенда: хранит состояние локально
и передаёт его в run_agent() при каждом запросе.

Режимы:
  1. Шаговый flow (step1 -> step2) — основной режим тестирования
  2. General-пайплайн — вопросы по ДТП/ОСАГО без шагового режима
"""

from agent.core import run_agent, rate_answer
from agent.step_types import Step


def _map_slots_to_fields(slots: dict) -> dict:
    """
    Переносит данные из step1 в начальный контекст step2.
    Базовая реализация: пустой перенос.
    """
    return {}


def _print_state(current_step: str, slots: dict,
                 collected_fields: dict) -> None:
    """Выводит текущее состояние диалога."""
    print(f"\n{'─' * 40}")
    print(f"  Шаг: {current_step}")
    if current_step == "step1":
        filled = {k: v for k, v in slots.items() if v is not None}
        print(f"  Слоты ({len(filled)}/6): {filled or '(пусто)'}")
    elif current_step == "step2":
        filled = {k: v for k, v in collected_fields.items() if v}
        print(f"  Поля ({len(filled)}/8): {list(filled.keys()) or '(пусто)'}")
    print(f"{'─' * 40}\n")


def run_step_flow() -> None:
    """
    Шаговый режим: step1 -> step2 -> done / call_gibdd.
    Симулирует работу бэкенда.
    """
    # --- Состояние бэкенда ---
    history: list[dict]        = []
    current_step: str          = Step.STEP1
    slots: dict                = {}
    collected_fields: dict     = {}

    print("\n=== Шаговый режим: Оформление Европротокола ===")
    print("Команды: 'выход' — завершить, 'состояние' — показать данные\n")

    while True:
        _print_state(current_step, slots, collected_fields)
        query = input("Вы: ").strip()

        if not query:
            continue
        if query.lower() == "выход":
            break
        if query.lower() == "состояние":
            continue

        # --- Вызов агента (как это делает Django-view) ---
        response = run_agent(
            query=query,
            current_step=current_step,
            history=history,
            slots=slots,
            collected_fields=collected_fields,
        )

        print(f"\nАссистент: {response['answer']}\n")

        # --- Обновление состояния (как это делает Django) ---
        history.append({"query": query, "answer": response["answer"]})

        if response.get("slots"):
            slots = response["slots"]
        if response.get("collected_fields"):
            collected_fields = response["collected_fields"]

        # --- Маршрутизация ---
        if response.get("step_completed"):
            next_s = response.get("next_step", "")

            if next_s == Step.OFFER_EUROPROTOCOL:
                current_step = Step.OFFER_EUROPROTOCOL
                print("[Переход → Предложение заполнить Европротокол]\n")

            elif next_s == Step.STEP2:
                current_step = Step.STEP2
                collected_fields = _map_slots_to_fields(slots)
                print("[Переход → Шаг 2: заполнение Европротокола]\n")


            elif next_s == Step.CONSULTANT_ONLY:
                current_step = Step.CONSULTANT_ONLY
                print("[Переход → Режим консультанта]\n")
                # Сбрасываем slots — шаговый сценарий завершён
                slots = {}
                collected_fields = {}

            elif next_s == Step.DONE:
                print("\n[✅ Протокол готов!]")
                if response.get("final_json"):
                    import json
                    print(json.dumps(
                        response["final_json"],
                        ensure_ascii=False, indent=2
                    ))
                print("[Переход → Шаг 3: помощь со страховой]\n")
                current_step = Step.STEP3

            elif next_s == Step.CALL_GIBDD:
                print("[⚠️ Вызовите ГИБДД. Сессия завершена.]\n")
                break

        # --- Оценка ---
        rating_str = input("Оценить ответ (0-5 или Enter): ").strip()
        if rating_str.isdigit():
            rating = int(rating_str)
            if 0 <= rating <= 5:
                r = rate_answer(query=query,
                                answer=response["answer"],
                                rating=rating)
                print(f"Критик: {r['critic_score']}/5 — {r['critic_comment']}")


def run_general_mode() -> None:
    """General-пайплайн: вопросы по ДТП/ОСАГО (старый режим)."""
    history: list[dict] = []
    print("\n=== General-режим: вопросы по ДТП и ОСАГО ===")
    print("Введите 'выход' для возврата в меню.\n")

    while True:
        query = input("Вы: ").strip()
        if not query:
            continue
        if query.lower() == "выход":
            break

        response = run_agent(query=query, history=history)
        print(f"\nАссистент [{response['source']}]: {response['answer']}\n")
        history.append({"query": query, "answer": response["answer"]})

        rating_str = input("Оценить (0-5 или Enter): ").strip()
        if rating_str.isdigit():
            rating = int(rating_str)
            if 0 <= rating <= 5:
                r = rate_answer(query=query,
                                answer=response["answer"],
                                rating=rating)
                print(f"Критик: {r['critic_score']}/5 — {r['critic_comment']}")


def main() -> None:
    while True:
        print("\n" + "=" * 45)
        print("  ДТП-ассистент — локальное тестирование")
        print("=" * 45)
        print("  1. Шаговый режим (step1 → step2)")
        print("  2. General-режим (вопросы по ДТП/ОСАГО)")
        print("  0. Выход")
        print("=" * 45)
        choice = input("Выбор: ").strip()
        if choice == "1":
            run_step_flow()
        elif choice == "2":
            run_general_mode()
        elif choice == "0":
            print("До свидания!")
            break
        else:
            print("Неверный ввод.")


if __name__ == "__main__":
    main()