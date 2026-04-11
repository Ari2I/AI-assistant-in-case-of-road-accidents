from agent.core import run_agent, rate_answer

USER_ID = "test_user"


def main() -> None:
    while True:
        query = input("Ты: ").strip()
        if not query:
            continue

        response = run_agent(query, db=None, feedback_db=None, user_id=USER_ID)
        print(f"\nБот: {response['answer']}\n")

        rating_input = input("Оцени ответ (0-5 или Enter): ").strip()
        if rating_input.isdigit():
            rating = int(rating_input)
            if 0 <= rating <= 5:
                rate_answer(
                    user_id=USER_ID,
                    message_id=response.get("message_id"),
                    rating=rating,
                    db=None,
                    feedback_db=None,
                )


if __name__ == "__main__":
    main()