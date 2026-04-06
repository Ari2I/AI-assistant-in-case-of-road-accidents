from agent.core import run_agent, rate_answer

user_id = "test_user"

while True:
    query = input("Ты: ")

    response = run_agent(query, db=None, feedback_db=None, user_id=user_id)

    print("\nБот:", response.get("answer"), "\n")

    # ОЦЕНКА ПОЛЬЗОВАТЕЛЯ
    rating_input = input("Оцени ответ (0-5 или Enter): ").strip()

    if rating_input.isdigit():
        rating = int(rating_input)

        if 0 <= rating <= 5:
            rate_answer(
                user_id,
                response.get("message_id"),
                rating,
                db=None,
                feedback_db=None
            )