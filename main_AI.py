"""
Локальный CLI для тестирования агента.
Запуск: python main_AI.py

История хранится в памяти на время сессии — имитирует то,
что в продакшне делает бэкенд.
"""

from agent.core import run_agent, rate_answer


def main() -> None:
    history = []  # история диалога — в продакшне хранит бэкенд

    print("ДТП-ассистент запущен. Введите 'выход' для завершения.\n")

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


