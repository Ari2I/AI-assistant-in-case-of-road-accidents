from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

_SYSTEM_PROMPT = """\
Ты — ДТП-ассистент. Отвечай строго по алгоритму ниже.

=== АЛГОРИТМ ДЕЙСТВИЙ ===
{algorithm}
=== КОНЕЦ АЛГОРИТМА ===

Тип ответа: {answer_type}
Этап: {stage}

Контекст из базы знаний:
{context}

Правила:
- Всегда следуй алгоритму — определи текущий блок и задай нужный вопрос
- Не пропускай блоки алгоритма
- Если пользователь ответил не по вариантам — уточни
- Не выдумывай факты и суммы
"""

def generate_answer(giga, query, context, plan, algorithm: str = "") -> str:
    system_content = _SYSTEM_PROMPT.format(
        algorithm=algorithm,
        answer_type=plan.get("answer_type", "steps"),
        stage=plan.get("stage", "accident"),
        context=context,
    )

    payload = Chat(
        messages=[
            Messages(role=MessagesRole.SYSTEM, content=system_content),
            Messages(role=MessagesRole.USER, content=query),
        ],
        temperature=0.1,  # ниже температура — точнее следование алгоритму
    )

    response = giga.chat(payload)
    return response.choices[0].message.content