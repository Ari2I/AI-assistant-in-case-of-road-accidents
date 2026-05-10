"""
Step 3: Помощь в взаимодействии со страховой компанией.
Активируется после успешного заполнения Европротокола (Step 2).
"""

from gigachat.models import Chat, Messages, MessagesRole

from agent.step_types import Step, StepResponse
from agent.history import build_history

_SYSTEM_PROMPT = """\
Ты — консультант по взаимодействию со страховой компанией после ДТП.

Пользователь уже оформил Европротокол. Твоя задача — помочь ему:
1. Правильно подать заявление о прямом возмещении убытков (ПВУ)
2. Отстоять справедливую выплату при спорах со страховой
3. Подготовить жалобу финансовому уполномоченному (finombudsman.ru) при необходимости

Контекст из базы знаний:
{context}

История диалога:
{history}

Данные оформленного протокола:
{protocol_summary}

ПРАВИЛА:
- Называй конкретные сроки: 5 рабочих дней на подачу, 15 дней запрет ремонта
- При вопросе о занижении выплат объясняй порядок: страховая → уполномоченный → суд
- Не выдумывай статьи законов и суммы, которых нет в контексте
- Если вопрос выходит за рамки ДТП/ОСАГО — вежливо возврати к теме
"""


def process_step3(
    giga,
    query: str,
    history: list,
    final_json: dict | None,
    db,
    feedback_db,
) -> StepResponse:
    from agent.retriever import get_context_for_category

    context = get_context_for_category(
        db, feedback_db, query, "insurance_communication"
    )
    history_text = build_history(
        history, component="generator", category="insurance_communication"
    )
    protocol_summary = _format_protocol_summary(final_json)

    payload = Chat(
        messages=[
            Messages(
                role=MessagesRole.SYSTEM,
                content=_SYSTEM_PROMPT.format(
                    context=context,
                    history=history_text or "(начало диалога)",
                    protocol_summary=protocol_summary,
                ),
            ),
            Messages(role=MessagesRole.USER, content=query),
        ],
        temperature=0.1,
    )

    response = giga.chat(payload)
    answer = response.choices[0].message.content

    return StepResponse(
        answer=answer,
        step_completed=False,
        next_step=Step.STEP3,
        slots={},
    )


def _format_protocol_summary(final_json: dict | None) -> str:
    if not final_json or "data" not in final_json:
        return "(данные протокола недоступны)"
    data = final_json["data"]
    parts = []
    if data.get("datetime"):
        parts.append(f"Дата ДТП: {data['datetime']}")
    if data.get("location"):
        parts.append(f"Место: {data['location']}")
    if data.get("damage_description"):
        parts.append(f"Повреждения: {data['damage_description']}")
    return "\n".join(parts) if parts else "(протокол оформлен)"