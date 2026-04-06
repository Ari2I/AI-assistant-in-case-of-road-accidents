def generate_answer(giga, query, context, plan):
    response = giga.chat({
        "messages": [
            {
                "role": "system",
                "content": f"""
                Ты эксперт по ДТП.
                
                Тип ответа:
                {plan.get("answer_type")}
                
                Этап:
                {plan.get("stage")}
                
                Если не знаешь — ответь "Не знаю".
                
                Контекст:
                {context}
                """
            },
            {"role": "user", "content": query}
        ],
        "temperature": 0.2
    })

    return response.choices[0].message.content