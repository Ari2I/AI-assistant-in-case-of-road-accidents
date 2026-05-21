"""
Режим FILL_EXTERNAL: пользователь заполняет Европротокол самостоятельно
(через стороннее приложение или на бумажном носителе).

Поведение:
  1. При первом входе — шаблонная сводка с ключевыми пунктами.
  2. Далее — RAG-консультант, отвечает на вопросы по заполнению.
  3. Детектирует завершение: триггер-слово → LLM-проверка контекста → STEP3.

Исправления:
  - Флаг первого входа хранится в collected_fields["fill_external_entered"],
    а не определяется по сканированию истории (хрупкий подход).
"""

from __future__ import annotations

import json
import re

from gigachat.models import Chat, Messages, MessagesRole

from agent.step_types import Step, StepResponse
from agent.history import build_history
from agent.retriever import get_context_for_category

# ---------------------------------------------------------------------------
# Шаблонные сводки при входе
# ---------------------------------------------------------------------------

_ENTRY_MESSAGE_APP = """\
Хорошо, заполняйте через приложение. Вот что важно не пропустить:

📋 **Ключевые пункты:**
1. Место и время ДТП
2. Данные участников — ФИО водителей и владельцев, водительские удостоверения
3. Страховые полисы — компания, серия/номер, срок действия (у обоих)
4. Место первоначального удара — конкретная деталь (бампер, крыло, дверь)
5. Повреждения — только видимые: вмятина / царапина / трещина / скол
6. Обстоятельства — кто куда ехал, какие манёвры, кто виноват
7. Схема — взаимное положение ТС, стрелки движения, ориентиры
8. Подписи обоих водителей

⚠️ Пустые графы заполняйте прочерком или Z. \
Исправления заверяйте подписями обоих водителей.

Если возникнут вопросы по конкретному пункту — спрашивайте. \
Когда закончите — напишите мне, и я помогу с дальнейшими шагами по страховой.
"""

_ENTRY_MESSAGE_PAPER = """\
Хорошо, заполняйте на бумажном бланке. Вот что важно не пропустить:

📋 **Ключевые пункты:**
1. (п. 1–2) Место и время ДТП
2. (п. 3) Свидетели — ФИО и телефон, если есть
3. (п. 4–6) Данные ТС — марка/модель, владелец, водитель
4. (п. 7) Страховые полисы — компания, серия/номер, срок действия (у обоих)
5. (п. 8) Место удара — отметьте на схеме автомобиля
6. (п. 9) Повреждения — только видимые: вмятина / царапина / трещина / скол
7. (п. 10) Замечания о вине — виновный: «Виноват», потерпевший: «Не виноват»
8. (п. 11) Обстоятельства — отметьте все подходящие подпункты
9. (п. 12) Схема — улицы, стрелки движения, положение ТС, знаки
10. (п. 13) Подписи обоих водителей + отметка о наличии/отсутствии разногласий
11. (п. 15–18) Оборотная сторона — каждый заполняет свою половину самостоятельно

⚠️ Пустые графы заполняйте прочерком или Z. \
Исправления заверяйте подписями обоих водителей.

Если возникнут вопросы по конкретному пункту — спрашивайте. \
Когда закончите — напишите мне, и я помогу с дальнейшими шагами по страховой.
"""

# ---------------------------------------------------------------------------
# Детектор завершения — уровень 1: триггер-слова
# ---------------------------------------------------------------------------

_DONE_TRIGGERS: frozenset[str] = frozenset({
    "заполнил", "заполнила", "заполнили",
    "оформил", "оформила", "оформили",
    "закончил", "закончила", "закончили",
    "завершил", "завершила", "завершили",
    "подписали", "подписал", "подписала",
    "сделал", "сделала", "сделали",
    "готово", "всё готово", "все готово",
    "протокол готов", "протокол заполнен",
    "сдали", "отправили",
})

# ---------------------------------------------------------------------------
# Детектор завершения — уровень 2: LLM-проверка контекста
# ---------------------------------------------------------------------------

_COMPLETION_CHECK_PROMPT = """\
Пользователь заполняет Европротокол о ДТП самостоятельно.
Агент ожидает, когда пользователь сообщит о завершении заполнения протокола.

История диалога:
{history}

Последнее сообщение пользователя: "{message}"

Определи одно из двух:
- Пользователь сообщает о том, что ЗАВЕРШИЛ заполнение протокола → completed: true
- Пользователь использует похожее слово в другом контексте \
  (вопрос, описание прошлых событий, упоминание чужих действий и т.д.) → completed: false

Верни ТОЛЬКО валидный JSON без пояснений и markdown:
{{"completed": true/false, "reason": "краткое пояснение"}}
"""


def _has_done_trigger(message: str) -> bool:
    """Быстрая проверка наличия триггер-слова без вызова LLM."""
    text = message.lower()
    return any(trigger in text for trigger in _DONE_TRIGGERS)


def _check_completion_with_llm(giga, message: str, history_text: str) -> bool:
    """
    LLM-проверка: пользователь действительно завершил заполнение
    или триггер-слово использовано в другом контексте.

    При любой ошибке возвращает False — не переходим в step3 случайно.
    """
    prompt = _COMPLETION_CHECK_PROMPT.format(
        history=history_text or "(начало диалога)",
        message=message,
    )
    try:
        payload = Chat(
            messages=[
                Messages(
                    role=MessagesRole.SYSTEM,
                    content="Ты — классификатор намерений. Отвечай только JSON.",
                ),
                Messages(role=MessagesRole.USER, content=prompt),
            ],
            temperature=0.0,
        )
        response = giga.chat(payload)
        content = response.choices[0].message.content.strip()

        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return False

        data = json.loads(match.group(0))
        return bool(data.get("completed", False))

    except Exception as e:
        print(f"[fill_external] completion check error: {e}")
        return False


# ---------------------------------------------------------------------------
# Генерация ответа на вопрос по заполнению
# ---------------------------------------------------------------------------

_CONSULTANT_SYSTEM = """\
Ты — консультант по заполнению Европротокола о ДТП.
Пользователь заполняет бланк самостоятельно и задаёт уточняющие вопросы.

Контекст из базы знаний:
{context}

История диалога:
{history}

ПРАВИЛА:
- Отвечай конкретно на заданный вопрос, ссылайся на номер пункта бланка.
- Не выдумывай формулировки — опирайся только на контекст из базы знаний.
- Если вопрос о конкретной детали повреждений — используй термины: \
  вмятина / царапина / трещина / скол / разрыв / разрушение.
- Напоминай: пустые графы заполнять прочерком или Z.
- Напоминай: исправления заверяются подписями обоих водителей.
- Не задавай уточняющих вопросов, если можешь ответить на основе контекста.
"""


def _generate_filling_advice(
    giga,
    query: str,
    context: str,
    history_text: str,
) -> str:
    """Генерирует ответ на вопрос по заполнению протокола."""
    system_content = _CONSULTANT_SYSTEM.format(
        context=context,
        history=history_text or "(начало диалога)",
    )
    payload = Chat(
        messages=[
            Messages(role=MessagesRole.SYSTEM, content=system_content),
            Messages(role=MessagesRole.USER, content=query),
        ],
        temperature=0.1,
    )
    try:
        response = giga.chat(payload)
        return response.choices[0].message.content
    except Exception as e:
        print(f"[fill_external] generate error: {e}")
        return (
            "Не удалось получить ответ. Попробуйте переформулировать вопрос."
        )


# ---------------------------------------------------------------------------
# Главная функция
# ---------------------------------------------------------------------------

def process_fill_external(
    giga,
    query: str,
    history: list,
    slots: dict,
    collected_fields: dict,
    db,
    feedback_db,
) -> StepResponse:
    """
    Обрабатывает один шаг в режиме самостоятельного заполнения.

    Способ заполнения хранится бэкендом в slots["fill_method"]:
      "app_external" — стороннее приложение
      "paper"        — бумажный бланк (по умолчанию)

    Флаг первого входа хранится в collected_fields["fill_external_entered"].
    """
    method = slots.get("fill_method", "paper")

    # Первый вход определяется по флагу в collected_fields, а не по истории.
    # История может быть длинной или изменить формат — флаг надёжнее.
    is_first_entry = not collected_fields.get("fill_external_entered")

    if is_first_entry:
        collected_fields["fill_external_entered"] = True
        entry_text = (
            _ENTRY_MESSAGE_APP if method == "app_external"
            else _ENTRY_MESSAGE_PAPER
        )
        return StepResponse(
            answer=entry_text,
            step_completed=False,
            next_step=Step.FILL_EXTERNAL,
            slots=slots,
            collected_fields=collected_fields,
        )

    # Двухуровневый детектор завершения
    if _has_done_trigger(query):
        history_text = build_history(history, component="classifier")
        if _check_completion_with_llm(giga, query, history_text):
            return StepResponse(
                answer=(
                    "Отлично! Разберёмся с дальнейшими шагами: куда направить "
                    "документы, в какие сроки и что делать, если страховая "
                    "занизит выплату."
                ),
                step_completed=True,
                next_step=Step.STEP3,
                slots=slots,
                collected_fields=collected_fields,
            )

    # Обычный вопрос — RAG-консультант
    context = get_context_for_category(
        db, feedback_db, query, "filling_europrotocol"
    )
    history_text = build_history(
        history, component="generator", category="filling_europrotocol"
    )
    answer = _generate_filling_advice(giga, query, context, history_text)

    return StepResponse(
        answer=answer,
        step_completed=False,
        next_step=Step.FILL_EXTERNAL,
        slots=slots,
        collected_fields=collected_fields,
    )