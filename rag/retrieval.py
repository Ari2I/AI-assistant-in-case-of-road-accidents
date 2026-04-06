def get_context(db, feedback_db, query):
    """
    Получает контекст из RAG баз.

    Если базы не переданы — возвращает пустой контекст.
    """
    try:
        docs = []

        if feedback_db:
            docs += feedback_db.similarity_search(query, k=3)

        if db:
            docs += db.similarity_search(query, k=5)

        if not docs:
            return "Нет данных"

        return "\n\n".join([d.page_content for d in docs])

    except Exception as e:
        print("RAG ERROR:", e)
        return "Нет данных"