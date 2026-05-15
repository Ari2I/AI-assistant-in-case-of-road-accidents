"""
CLI для локального тестирования ДТП-ассистента.
Симулирует поведение Django-бэкенда: хранит состояние локально
и передаёт его в run_agent() при каждом запросе.
"""

import json

from agent.core import run_agent, rate_answer
from agent.step_types import Step


def _map_slots_to_fields(slots: dict) -> dict:
    """Переносит данные из step1 в начальный контекст step2."""
    return {}


def _print_state(current_step: str, slots: dict, collected_fields: dict) -> None:
    print(f"\n{'─' * 40}")
    print(f"  Шаг: {current_step}")
    if current_step == Step.STEP1:
        filled = {k: v for k, v in slots.items()
                  if v is not None and not k.startswith("_")}
        print(f"  Слоты ({len(filled)}/6): {filled or '(пусто)'}")
    elif current_step == Step.STEP2:
        filled = {k: v for k, v in collected_fields.items()
                  if v and not k.startswith("_")}
        print(f"  Поля ({len(filled)}): {list(filled.keys()) or '(пусто)'}")
    elif current_step == Step.FILL_EXTERNAL:
        method = slots.get("fill_method", "paper")
        label = "стороннее приложение" if method == "app_external" else "бумажный бланк"
        print(f"  Метод: {label}")
    print(f"{'─' * 40}\n")


def run_step_flow() -> None:
    """Шаговый режим: step1 → выбор метода → step2/fill_external → step3."""
    history: list[dict]    = []
    current_step: str      = Step.STEP1
    slots: dict            = {}
    collected_fields: dict = {}

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

        response = run_agent(
            query=query,
            current_step=current_step,
            history=history,
            slots=slots,
            collected_fields=collected_fields,
        )

        # Пропускаем None-ответы (не должны возникать после v4.4, но на всякий случай)
        if response.get("answer") is not None:
            print(f"\nАссистент: {response['answer']}\n")
        else:
            print("[системный переход, ответ отсутствует]\n")

        history.append({"query": query, "answer": response.get("answer") or ""})

        # Обновляем состояние
        if response.get("slots") is not None:
            slots = response["slots"]
        if response.get("collected_fields") is not None:
            collected_fields = response["collected_fields"]

        # Маршрутизация
        if not response.get("step_completed"):
            continue

        next_s = response.get("next_step")
        if next_s is None:
            continue

        # --- STEP1 ---
        if next_s == Step.STEP1:
            current_step = Step.STEP1

        # --- Предложение Европротокола ---
        elif next_s == Step.OFFER_EUROPROTOCOL:
            current_step = Step.OFFER_EUROPROTOCOL
            print("[Переход → Предложение Европротокола]\n")

        # --- Выбор метода (маппится в offer_europrotocol) ---
        elif next_s == Step.OFFER_METHOD:
            current_step = Step.OFFER_EUROPROTOCOL
            print("[Переход → Выбор метода]\n")

        # --- Заполнение через наше приложение ---
        elif next_s == Step.STEP2:
            current_step = Step.STEP2
            # collected_fields уже обновлены из response выше
            print("[Переход → Шаг 2: заполнение через приложение]\n")

        # --- Самостоятельное заполнение ---
        elif next_s == Step.FILL_EXTERNAL:
            current_step = Step.FILL_EXTERNAL
            method = slots.get("fill_method", "paper")
            label = "стороннее приложение" if method == "app_external" else "бумажный бланк"
            print(f"[Переход → Самостоятельное заполнение ({label})]\n")

        # --- Помощь со страховой ---
        elif next_s == Step.STEP3:
            current_step = Step.STEP3
            print("[Переход → Шаг 3: взаимодействие со страховой]\n")

        # --- Режим консультанта ---
        elif next_s == Step.CONSULTANT_ONLY:
            current_step = Step.CONSULTANT_ONLY
            slots = {}
            collected_fields = {}
            print("[Переход → Режим консультанта]\n")

        # --- Протокол готов → шаг 3 ---
        elif next_s == Step.DONE:
            if response.get("final_json"):
                print("\n[✅ Протокол готов!]")
                print(json.dumps(response["final_json"], ensure_ascii=False, indent=2))
            current_step = Step.STEP3
            print("[Переход → Шаг 3: взаимодействие со страховой]\n")

        # --- Вызвать ГИБДД ---
        elif next_s == Step.CALL_GIBDD:
            print("[⚠️  Вызовите ГИБДД. Сессия завершена.]\n")
            break

        # Оценка
        rating_str = input("Оценить ответ (0-5 или Enter): ").strip()
        if rating_str.isdigit():
            rating = int(rating_str)
            if 0 <= rating <= 5:
                r = rate_answer(query=query, answer=response.get("answer", ""), rating=rating)
                print(f"Критик: {r['critic_score']}/5 — {r['critic_comment']}")


def main() -> None:
    run_step_flow()


if __name__ == "__main__":
    main()