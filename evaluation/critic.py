def critic_rate_answer(giga, query, answer):
    review = giga.chat(f"""
    Оцени ответ от 1 до 5.
    
    Вопрос: {query}
    Ответ: {answer}
    """)

    text = review.choices[0].message.content

    import re
    match = re.search(r'(\d)', text)
    score = int(match.group(1)) if match else 3

    return score, text