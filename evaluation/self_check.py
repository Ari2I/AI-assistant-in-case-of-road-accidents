def improve_answer(giga, query, answer, context):
    """
    Выполняет самооценку и при необходимости улучшает ответ.

    Модель обязана вернуть полноценный ответ пользователю,
    а не описание действий или заглушку.

    Args:
        giga: клиент GigaChat
        query (str): вопрос пользователя
        answer (str): исходный ответ
        context (str): контекст из RAG

    Returns:
        tuple: (verdict, confidence, issues, final_answer)
    """
    review = giga.chat(f"""
    Ты эксперт по ДТП.
    
    Вопрос:
    {query}
    
    Исходный ответ:
    {answer}
    
    Контекст:
    {context}
    
    ЗАДАЧА:
    1. Оцени ответ на полноту и полезность
    2. Если ответ хороший — оставь его БЕЗ изменений
    3. Если плохой — перепиши его полностью
    
    ВАЖНО:
    - Финальный ответ должен быть готовым ответом пользователю
    - Он должен содержать конкретные действия / объяснения
    - НЕЛЬЗЯ писать описание вроде "вот улучшенный ответ"
    - НЕЛЬЗЯ описывать процесс улучшения
    - НЕЛЬЗЯ писать мета-комментарии
    
    ПРОВЕРКА:
    Если финальный ответ не содержит конкретной информации по вопросу —
    считай его плохим
    
    Верни JSON:
    
    {{
      "verdict": "GOOD" или "BAD",
      "confidence": число от 0 до 1,
      "issues": "что не так",
      "final": "готовый ответ пользователю"
    }}
    """)

    text = review.choices[0].message.content

    import json
    import re

    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        text = match.group(0)

    try:
        data = json.loads(text)

        final = data.get("final", "").strip()

        # 🔴 ЛОГИЧЕСКАЯ проверка (не хардкод строк)
        # если ответ слишком короткий или неинформативный — fallback
        if len(final) < 20:  # 🔴 CHANGED
            final = answer

        return (
            data.get("verdict", "BAD"),
            float(data.get("confidence", 0.5)),
            data.get("issues", ""),
            final
        )

    except Exception:
        return "BAD", 0.0, "parse error", answer