def is_dtp_related(giga, query, history_text):
    """
    Проверяет, относится ли сообщение к теме ДТП или текущему диалогу.

    Args:
        giga: клиент GigaChat
        query (str): сообщение пользователя
        history_text (str): последние сообщения диалога

    Returns:
        bool: True если сообщение релевантно теме ДТП
    """
    try:
        response = giga.chat(f"""
        Ты определяешь, относится ли сообщение к теме ДТП.
        
        ВАЖНО:
        - приветствия = ДА
        - ответы на вопросы ассистента = ДА
        - уточнения = ДА
        - полностью посторонние темы = НЕТ
        
        История:
        {history_text}
        
        Сообщение:
        {query}
        
        Ответь строго:
        ДА или НЕТ
        """)

        content = response.choices[0].message.content.strip().upper()
        return content == "ДА"

    except Exception:
        return True  # fallback — не ломаем UX