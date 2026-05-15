"""
Step 3: Помощь во взаимодействии со страховой компанией.

Активируется после:
  - Успешного заполнения Европротокола через наше приложение (Step 2 → DONE)
  - Подтверждения пользователем заполнения через стороннее приложение/бумагу (FILL_EXTERNAL)

Поведение:
  1. При первом входе — персонализированный план с дедлайнами.
     Дата ДТП и страховые компании берутся из collected_fields (prefilled бэкендом).
     Если ключевых данных нет — агент запрашивает их у пользователя.
  2. Далее — навигация по действиям:
     - Подача заявления о прямом возмещении убытков (ПВУ)
     - Помощь в составлении обращения
     - Дедлайны (5 рабочих дней, 15 календарных дней, 5 дней на осмотр)
     - Эскалация при споре: страховая → финансовый уполномоченный → суд
  3. Выход: пользователь явно завершает → CONSULTANT_ONLY
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from gigachat.models import Chat, Messages, MessagesRole

from agent.step_types import Step, StepResponse
from agent.history import build_history
from agent.retriever import get_context_for_category

# ---------------------------------------------------------------------------
# Ключи, которые бэкенд prefill-ит в collected_fields до входа в step3
# ---------------------------------------------------------------------------

_KEY_DATE       = "date"           # дата ДТП: "ДД.ММ.ГГГГ"
_KEY_INSURER_A  = "vehicle_a_insurer"  # страховая компания участника А
_KEY_INSURER_B  = "vehicle_b_insurer"  # страховая компания участника Б

# ---------------------------------------------------------------------------
# Детектор завершения step3
# ---------------------------------------------------------------------------

_EXIT_TRIGGERS: frozenset[str] = frozenset({
    "спасибо", "всё понятно", "все понятно", "понятно", "ясно",
    "больше вопросов нет", "вопросов нет", "достаточно",
    "всё", "все", "окей", "ок", "ok", "хорошо", "отлично",
    "разобрался", "разобралась", "разберусь",
})

# ---------------------------------------------------------------------------
# Дедлайны
# ---------------------------------------------------------------------------

def _calc_deadlines(dtp_date_str: str | None) -> dict[str, str]:
    """
    Вычисляет конкретные даты дедлайнов на основе даты ДТП.
    Возвращает dict с ключами deadline_notify, deadline_repair, deadline_inspection.
    Если дата не распознана — возвращает строки с общими сроками.
    """
    if not dtp_date_str:
        return {
            "deadline_notify":      "в течение 5 рабочих дней с даты ДТП",
            "deadline_repair":      "в течение 15 календарных дней с даты ДТП",
            "deadline_inspection":  "в течение 5 рабочих дней с момента получения требования",
        }

    try:
        day, month, year = map(int, dtp_date_str.strip().split("."))
        dtp = date(year, month, day)

        # 5 рабочих дней — пропускаем выходные
        notify = dtp
        working = 0
        while working < 5:
            notify += timedelta(days=1)
            if notify.weekday() < 5:  # пн–пт
                working += 1

        # 15 календарных дней
        repair = dtp + timedelta(days=15)

        fmt = "%d.%m.%Y"
        return {
            "deadline_notify":      f"до {notify.strftime(fmt)} (5 рабочих дней)",
            "deadline_repair":      f"до {repair.strftime(fmt)} (15 календарных дней)",
            "deadline_inspection":  "в течение 5 рабочих дней с момента получения требования",
        }
    except (ValueError, AttributeError):
        return {
            "deadline_notify":      "в течение 5 рабочих дней с даты ДТП",
            "deadline_repair":      "в течение 15 календарных дней с даты ДТП",
            "deadline_inspection":  "в течение 5 рабочих дней с момента получения требования",
        }


def _build_entry_message(collected_fields: dict) -> tuple[str, bool]:
    """
    Формирует приветственное сообщение step3 с персонализированным планом.

    Возвращает:
        (текст сообщения, needs_clarification: bool)
        needs_clarification=True если нужно уточнить дату или страховую у пользователя.
    """
    dtp_date    = collected_fields.get(_KEY_DATE)
    insurer_a   = collected_fields.get(_KEY_INSURER_A)
    insurer_b   = collected_fields.get(_KEY_INSURER_B)

    deadlines = _calc_deadlines(dtp_date)
    needs_clarification = False

    # Формируем строку про страховую
    if insurer_a:
        insurer_line = (
            f"Ваша страховая: **{insurer_a}**. "
            f"Именно туда подаёте заявление о прямом возмещении убытков."
        )
    else:
        insurer_line = (
            "Чтобы я мог указать конкретную страховую компанию — "
            "напишите, как называется ваша страховая."
        )
        needs_clarification = True

    # Формируем строку с датой
    if dtp_date:
        date_line = f"ДТП: **{dtp_date}**"
    else:
        date_line = "Дата ДТП не указана — сроки приведены в относительных значениях."
        needs_clarification = True

    entry = (
        f"Протокол оформлен. Вот ваш план действий.\n\n"
        f"📅 {date_line}\n"
        f"🏢 {insurer_line}\n\n"
        f"**Ключевые дедлайны:**\n"
        f"1. Направить извещение в страховую — {deadlines['deadline_notify']}\n"
        f"2. Не ремонтировать автомобиль без согласия страховщика — "
        f"{deadlines['deadline_repair']}\n"
        f"3. Предоставить ТС на осмотр по требованию страховщика — "
        f"{deadlines['deadline_inspection']}\n\n"
        f"**Что нужно подать:**\n"
        f"— Извещение о ДТП (ваш экземпляр)\n"
        f"— Заявление о прямом возмещении убытков (ПВУ)\n"
        f"— Копия паспорта\n\n"
        f"Задавайте вопросы: помогу составить заявление, разберём ситуацию "
        f"с выплатой или объясню, что делать при занижении суммы."
    )

    return entry, needs_clarification


# ---------------------------------------------------------------------------
# Системный промпт для основного диалога step3
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
Ты — консультант по взаимодействию со страховой компанией после ДТП.
Пользователь уже оформил Европротокол и сейчас занимается подачей документов.

Контекст из базы знаний:
{context}

История диалога:
{history}

Данные по ДТП:
{protocol_data}

ПРАВИЛА:
- Называй конкретные сроки: 5 рабочих дней на подачу извещения, \
15 календарных дней — запрет ремонта, 5 рабочих дней на осмотр по требованию.
- При вопросе о занижении выплат: страховая → финансовый уполномоченный \
(finombudsman.ru, 15–30 дней) → суд. Досудебный порядок через уполномоченного обязателен.
- Для подачи жалобы на страховую: Банк России (cbr.ru) или РСА (autoins.ru).
- Конкретный список документов для ПВУ: извещение о ДТП, заявление о прямом \
возмещении убытков, копия паспорта. Страховщик не вправе требовать документы \
сверх установленного перечня.
- Не выдумывай статьи и суммы, которых нет в контексте.
- Если вопрос выходит за рамки ДТП/ОСАГО — вежливо верни к теме.
"""


def _format_protocol_data(collected_fields: dict) -> str:
    """Форматирует ключевые данные протокола для промпта."""
    parts = []
    if collected_fields.get(_KEY_DATE):
        parts.append(f"Дата ДТП: {collected_fields[_KEY_DATE]}")
    if collected_fields.get("location"):
        parts.append(f"Место: {collected_fields['location']}")
    if collected_fields.get(_KEY_INSURER_A):
        parts.append(f"Страховая участника А: {collected_fields[_KEY_INSURER_A]}")
    if collected_fields.get(_KEY_INSURER_B):
        parts.append(f"Страховая участника Б: {collected_fields[_KEY_INSURER_B]}")
    if collected_fields.get("vehicle_a_damage"):
        parts.append(f"Повреждения А: {collected_fields['vehicle_a_damage']}")
    if collected_fields.get("vehicle_b_damage"):
        parts.append(f"Повреждения Б: {collected_fields['vehicle_b_damage']}")
    return "\n".join(parts) if parts else "(данные протокола не переданы)"


def _generate_answer(
    giga,
    query: str,
    context: str,
    history_text: str,
    collected_fields: dict,
) -> str:
    """Генерирует ответ через LLM."""
    system_content = _SYSTEM_PROMPT.format(
        context=context,
        history=history_text or "(начало диалога)",
        protocol_data=_format_protocol_data(collected_fields),
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
        print(f"[step3] generate error: {e}")
        return (
            "Не удалось получить ответ. "
            "Если нужна срочная информация — обратитесь напрямую в страховую компанию."
        )


# ---------------------------------------------------------------------------
# Главная функция
# ---------------------------------------------------------------------------

def process_step3(
    giga,
    query: str,
    history: list,
    collected_fields: dict,
    db,
    feedback_db,
) -> StepResponse:
    """
    Обрабатывает один шаг взаимодействия со страховой компанией.

    collected_fields должен содержать (prefilled бэкендом):
      - date: дата ДТП
      - vehicle_a_insurer: страховая компания пользователя
      - vehicle_b_insurer: страховая компания второго участника
    Если поля пустые — агент уточняет у пользователя.
    """
    # Детектор выхода из step3
    q_lower = query.strip().lower().rstrip("!.,?")
    if q_lower in _EXIT_TRIGGERS and len(history) > 1:
        return StepResponse(
            answer=(
                "Удачи с оформлением! Если появятся вопросы — обращайтесь."
            ),
            step_completed=True,
            next_step=Step.CONSULTANT_ONLY,
            slots={},
            collected_fields=collected_fields,
        )

    # Первый вход в step3 — персонализированный план с дедлайнами
    is_first_entry = not any(
        "план действий" in h.get("answer", "").lower()
        for h in history[-5:]
    )

    if is_first_entry:
        entry_text, _ = _build_entry_message(collected_fields)
        return StepResponse(
            answer=entry_text,
            step_completed=False,
            next_step=Step.STEP3,
            slots={},
            collected_fields=collected_fields,
        )

    # Пользователь уточняет данные (страховая / дата) после запроса агента
    collected_fields = _try_extract_clarification(query, collected_fields)

    # Обычный вопрос — LLM с RAG
    context = get_context_for_category(
        db, feedback_db, query, "insurance_communication"
    )
    history_text = build_history(
        history, component="generator", category="insurance_communication"
    )
    answer = _generate_answer(giga, query, context, history_text, collected_fields)

    return StepResponse(
        answer=answer,
        step_completed=False,
        next_step=Step.STEP3,
        slots={},
        collected_fields=collected_fields,
    )


def _try_extract_clarification(query: str, collected_fields: dict) -> dict:
    """
    Простое детерминированное извлечение даты и названия страховой
    из уточняющего ответа пользователя. Без LLM.

    Обновляет collected_fields на месте и возвращает его.
    """
    # Дата вида ДД.ММ.ГГГГ
    if not collected_fields.get(_KEY_DATE):
        date_match = re.search(r"\b(\d{2}\.\d{2}\.\d{4})\b", query)
        if date_match:
            collected_fields[_KEY_DATE] = date_match.group(1)

    # Страховая — если не заполнена, сохраняем весь текст как название
    # (пользователь написал, например, "Росгосстрах" или "СОГАЗ")
    if not collected_fields.get(_KEY_INSURER_A):
        q = query.strip()
        # Короткий ответ без знаков препинания — скорее всего название компании
        if len(q.split()) <= 5 and not q.endswith("?"):
            collected_fields[_KEY_INSURER_A] = q

    return collected_fields