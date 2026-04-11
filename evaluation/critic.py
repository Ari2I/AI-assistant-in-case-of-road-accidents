import re
from typing import Tuple

from gigachat import GigaChat

_DEFAULT_SCORE = 3

_PROMPT_TEMPLATE = """\
Оцени качество ответа по шкале от 1 до 5.

Вопрос: {query}
Ответ: {answer}

Критерии:
5 — точный, полный, конкретный ответ
4 — хороший ответ с незначительными недостатками
3 — частичный ответ, не раскрывает вопрос полностью
2 — ответ поверхностный или содержит ошибки
1 — ответ не по теме или вводит в заблуждение

Верни ответ строго в формате:
ОЦЕНКА: <число от 1 до 5>
КОММЕНТАРИЙ: <краткое обоснование>
"""


def critic_rate_answer(giga: GigaChat, query: str, answer: str) -> Tuple[int, str]:
    """
    Оценивает качество ответа с помощью LLM.

    Args:
        giga: клиент GigaChat
        query: вопрос пользователя
        answer: ответ агента

    Returns:
        Кортеж (score, comment). score от 1 до 5.
        При ошибке возвращает (_DEFAULT_SCORE, "").
    """
    prompt = _PROMPT_TEMPLATE.format(query=query, answer=answer)

    try:
        review = giga.chat(prompt)
        text = review.choices[0].message.content

        score_match = re.search(r"ОЦЕНКА:\s*([1-5])", text)
        comment_match = re.search(r"КОММЕНТАРИЙ:\s*(.+)", text, re.DOTALL)

        score = int(score_match.group(1)) if score_match else _DEFAULT_SCORE
        comment = comment_match.group(1).strip() if comment_match else text.strip()

        return score, comment

    except (AttributeError, IndexError, ValueError):
        return _DEFAULT_SCORE, ""