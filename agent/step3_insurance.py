"""
Step 3: Взаимодействие со страховой компанией.

Две фазы:
  Фаза 1 (phase1) — подача документов сразу после ДТП:
    персонализированный план с дедлайнами → ответы на вопросы →
    после 3+ ходов агент спрашивает о статусе выплаты

  Фаза 2 (phase2) — работа с выплатой и спорами:
    активируется когда пользователь явно сообщает о получении выплаты →
    сбор данных по мере диалога (сумма выплаты, стоимость ремонта, экспертиза) →
    составление обращения об увеличении выплаты (шаблон + LLM ситуационная часть) →
    объяснение цепочки эскалации по мере необходимости

Состояние хранится в collected_fields (передаётся бэкендом):
  step3_phase: "phase1" | "phase2"
  step3_entered: bool
  step3_turns: int
  step3_payment_asked: bool
  appeal_payment_amount: str
  appeal_repair_cost: str
  appeal_has_expertise: bool
  appeal_generated: bool
"""

from __future__ import annotations

import json
import re
from datetime import date

from gigachat.models import Chat, Messages, MessagesRole

from agent.step_types import Step, StepResponse
from agent.history import build_history
from agent.retriever import get_context_for_category

# ---------------------------------------------------------------------------
# Ключи из протокола (prefilled бэкендом)
# ---------------------------------------------------------------------------

_KEY_DATE       = "date"
_KEY_LOCATION   = "location"
_KEY_INSURER_A  = "vehicle_a_insurer"
_KEY_INSURER_B  = "vehicle_b_insurer"
_KEY_OWNER_A    = "vehicle_a_owner_name"
_KEY_VEHICLE_A  = "vehicle_a_make_model"
_KEY_REG_A      = "vehicle_a_reg_number"
_KEY_POLICY_A   = "vehicle_a_policy_number"
_KEY_DAMAGE_A   = "vehicle_a_damage"
_KEY_FAULT_A    = "vehicle_a_fault"

# ---------------------------------------------------------------------------
# Детектор завершения step3
# ---------------------------------------------------------------------------

_EXIT_TRIGGERS: frozenset[str] = frozenset({
    "спасибо", "всё понятно", "все понятно", "понятно", "ясно",
    "больше вопросов нет", "вопросов нет", "достаточно",
    "разобрался", "разобралась", "разберусь", "всё", "все",
})

# ---------------------------------------------------------------------------
# Триггеры перехода в фазу 2
# ---------------------------------------------------------------------------

_PHASE2_TRIGGERS: frozenset[str] = frozenset({
    "выплатила", "выплатил", "выплатили", "выплата пришла",
    "получил выплату", "получила выплату", "перечислили", "перевели",
    "занижена", "занизили", "мало", "не согласен с выплатой",
    "отказали", "отказала", "отказ в выплате", "не платят",
    "хочу оспорить", "хочу обжаловать", "буду оспаривать",
})

_PHASE2_CHECK_PROMPT = """\
Пользователь взаимодействует со страховой после ДТП.
Агент ожидает информации о том, что страховая произвела выплату или отказала.

История диалога:
{history}

Последнее сообщение: "{message}"

Пользователь сообщает о том, что:
a) страховая выплатила деньги (устраивает или нет), ИЛИ
b) страховая отказала в выплате, ИЛИ
c) пользователь хочет оспорить выплату?

Верни ТОЛЬКО JSON:
{{"phase2": true/false, "reason": "краткое пояснение"}}
"""

# ---------------------------------------------------------------------------
# Триггеры запроса обращения
# ---------------------------------------------------------------------------

_APPEAL_REQUEST_TRIGGERS: frozenset[str] = frozenset({
    "составь обращение", "напиши обращение", "составить обращение",
    "написать обращение", "помоги написать", "напиши письмо",
    "составь жалобу", "написать жалобу", "нужно обращение",
    "оспорить выплату", "как оспорить", "хочу оспорить",
})

# ---------------------------------------------------------------------------
# Дедлайны
# ---------------------------------------------------------------------------

def _calc_deadlines(dtp_date_str: str | None) -> dict[str, str]:
    if not dtp_date_str:
        return {
            "notify":      "в течение 5 рабочих дней с даты ДТП",
            "repair":      "в течение 15 календарных дней с даты ДТП",
            "inspection":  "в течение 5 рабочих дней с момента получения требования",
        }
    try:
        day, month, year = map(int, dtp_date_str.strip().split("."))
        dtp = date(year, month, day)
        from datetime import timedelta
        notify = dtp
        working = 0
        while working < 5:
            notify += timedelta(days=1)
            if notify.weekday() < 5:
                working += 1
        repair = dtp + timedelta(days=15)
        fmt = "%d.%m.%Y"
        return {
            "notify":      f"до {notify.strftime(fmt)} (5 рабочих дней)",
            "repair":      f"до {repair.strftime(fmt)} (15 календарных дней)",
            "inspection":  "в течение 5 рабочих дней с момента получения требования",
        }
    except (ValueError, AttributeError):
        return {
            "notify":      "в течение 5 рабочих дней с даты ДТП",
            "repair":      "в течение 15 календарных дней с даты ДТП",
            "inspection":  "в течение 5 рабочих дней с момента получения требования",
        }


def _build_entry_message(collected_fields: dict) -> str:
    dtp_date   = collected_fields.get(_KEY_DATE)
    insurer_a  = collected_fields.get(_KEY_INSURER_A)
    deadlines  = _calc_deadlines(dtp_date)

    date_line = f"ДТП: **{dtp_date}**" if dtp_date else "Дата ДТП не указана."
    insurer_line = (
        f"Ваша страховая: **{insurer_a}** — туда подаёте заявление о прямом возмещении."
        if insurer_a
        else "Уточните название вашей страховой компании."
    )

    return (
        f"Протокол оформлен. Вот ваш план действий.\n\n"
        f"📅 {date_line}\n"
        f"🏢 {insurer_line}\n\n"
        f"**Ключевые дедлайны:**\n"
        f"1. Направить извещение в страховую — {deadlines['notify']}\n"
        f"2. Не ремонтировать без согласия страховщика — {deadlines['repair']}\n"
        f"3. Предоставить ТС на осмотр по требованию — {deadlines['inspection']}\n\n"
        f"**Что подавать:**\n"
        f"— Извещение о ДТП\n"
        f"— Заявление о прямом возмещении убытков (ПВУ)\n"
        f"— Копия паспорта\n\n"
        f"Задавайте вопросы — помогу разобраться с подачей документов."
    )


# ---------------------------------------------------------------------------
# Обнаружение фазы 2
# ---------------------------------------------------------------------------

def _has_phase2_trigger(query: str) -> bool:
    q = query.lower()
    return any(t in q for t in _PHASE2_TRIGGERS)


def _confirm_phase2_with_llm(giga, query: str, history_text: str) -> bool:
    prompt = _PHASE2_CHECK_PROMPT.format(
        history=history_text or "(начало диалога)",
        message=query,
    )
    try:
        payload = Chat(
            messages=[
                Messages(role=MessagesRole.SYSTEM,
                         content="Ты — классификатор намерений. Отвечай только JSON."),
                Messages(role=MessagesRole.USER, content=prompt),
            ],
            temperature=0.0,
        )
        resp = giga.chat(payload)
        content = resp.choices[0].message.content.strip()
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return False
        data = json.loads(match.group(0))
        return bool(data.get("phase2", False))
    except Exception as e:
        print(f"[step3] phase2 confirm error: {e}")
        return False


# ---------------------------------------------------------------------------
# Извлечение данных для обращения
# ---------------------------------------------------------------------------

_APPEAL_DATA_PROMPT = """\
Извлеки данные для обращения в страховую из сообщения пользователя.

Поля:
- appeal_payment_amount: сумма выплаты страховой (строка, например "45000")
- appeal_repair_cost: реальная стоимость ремонта (строка, например "87000")
- appeal_has_expertise: есть ли заключение независимой экспертизы (true/false)

Если данных нет — не включай поле. Верни ТОЛЬКО валидный JSON без пояснений.

Сообщение: "{message}"
"""


def _extract_appeal_data(giga, query: str, collected_fields: dict) -> None:
    """Извлекает данные для обращения из сообщения, обновляет collected_fields."""
    try:
        prompt = _APPEAL_DATA_PROMPT.format(message=query)
        payload = Chat(
            messages=[
                Messages(role=MessagesRole.SYSTEM,
                         content="Ты — экстрактор данных. Отвечай только JSON."),
                Messages(role=MessagesRole.USER, content=prompt),
            ],
            temperature=0.0,
        )
        resp = giga.chat(payload)
        content = resp.choices[0].message.content.strip()
        if "```" in content:
            for part in content.split("```"):
                if part.strip().startswith("{"):
                    content = part.strip()
                    break
        data = json.loads(content)
        for key in ("appeal_payment_amount", "appeal_repair_cost", "appeal_has_expertise"):
            if key in data and data[key] is not None:
                collected_fields[key] = data[key]
    except Exception as e:
        print(f"[step3] appeal data extraction error: {e}")


def _missing_appeal_data(collected_fields: dict) -> list[str]:
    """Возвращает список недостающих данных для составления обращения."""
    missing = []
    if not collected_fields.get("appeal_payment_amount"):
        missing.append("сумма выплаты страховой")
    if not collected_fields.get("appeal_repair_cost"):
        missing.append("реальная стоимость ремонта")
    return missing


# ---------------------------------------------------------------------------
# Генерация обращения
# ---------------------------------------------------------------------------

_APPEAL_SITUATIONAL_PROMPT = """\
Напиши один абзац — описание обстоятельств ДТП и повреждений для официального \
обращения в страховую компанию. Официально-деловой стиль. Только факты.

Данные о ДТП:
{data}

Верни ТОЛЬКО текст абзаца, без пояснений и кавычек.
"""

_APPEAL_TEMPLATE = """\
Страховой компании «{insurer}»

От: {owner}
Транспортное средство: {vehicle}, г/н {reg_number}
Номер полиса ОСАГО: {policy}

ОБРАЩЕНИЕ об увеличении страхового возмещения

{situational}

Страховая компания произвела выплату в размере {payment} руб., тогда как реальная \
стоимость восстановительного ремонта составляет {repair} руб. \
Разница составляет {difference} руб.

На основании статьи 14.1 Федерального закона от 25.04.2002 № 40-ФЗ прошу \
произвести доплату страхового возмещения в размере {difference} руб. \
в течение 10 рабочих дней с даты получения настоящего обращения.

Приложения:
— Копия извещения о ДТП{expertise_line}

{owner}
{today}
"""


def _generate_appeal(giga, collected_fields: dict) -> tuple[str, dict]:
    """
    Генерирует текст обращения и JSON для бэкенда.
    Возвращает (appeal_text, appeal_json).
    """
    # Данные из протокола
    insurer  = collected_fields.get(_KEY_INSURER_A, "страховую компанию")
    owner    = collected_fields.get(_KEY_OWNER_A, "Заявитель")
    vehicle  = collected_fields.get(_KEY_VEHICLE_A, "ТС")
    reg      = collected_fields.get(_KEY_REG_A, "—")
    policy   = collected_fields.get(_KEY_POLICY_A, "—")
    damage   = collected_fields.get(_KEY_DAMAGE_A, "")
    circumst = collected_fields.get("circumstances", "")

    payment  = collected_fields.get("appeal_payment_amount", "0")
    repair   = collected_fields.get("appeal_repair_cost", "0")
    has_exp  = collected_fields.get("appeal_has_expertise", False)

    try:
        difference = str(int(repair) - int(payment))
    except (ValueError, TypeError):
        difference = "—"

    expertise_line = "\n— Заключение независимой экспертизы" if has_exp else ""
    today = date.today().strftime("%d.%m.%Y")

    # LLM генерирует ситуационный абзац
    data_str = (
        f"Дата ДТП: {collected_fields.get(_KEY_DATE, '—')}\n"
        f"Место: {collected_fields.get(_KEY_LOCATION, '—')}\n"
        f"ТС пользователя: {vehicle} {reg}\n"
        f"Повреждения: {damage}\n"
        f"Обстоятельства: {circumst}"
    )
    situational = _generate_situational(giga, data_str)

    appeal_text = _APPEAL_TEMPLATE.format(
        insurer=insurer,
        owner=owner,
        vehicle=vehicle,
        reg_number=reg,
        policy=policy,
        situational=situational,
        payment=payment,
        repair=repair,
        difference=difference,
        expertise_line=expertise_line,
        today=today,
    )

    appeal_json = {
        "type": "appeal",
        "insurer": insurer,
        "owner": owner,
        "vehicle": vehicle,
        "reg_number": reg,
        "policy": policy,
        "payment_amount": payment,
        "repair_cost": repair,
        "difference": difference,
        "has_expertise": has_exp,
        "situational": situational,
        "full_text": appeal_text,
        "generated_date": today,
    }

    return appeal_text, appeal_json


def _generate_situational(giga, data_str: str) -> str:
    """Генерирует ситуационный абзац через LLM."""
    try:
        prompt = _APPEAL_SITUATIONAL_PROMPT.format(data=data_str)
        payload = Chat(
            messages=[
                Messages(role=MessagesRole.SYSTEM,
                         content="Ты — юридический редактор. Пиши официально и кратко."),
                Messages(role=MessagesRole.USER, content=prompt),
            ],
            temperature=0.1,
        )
        resp = giga.chat(payload)
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[step3] situational generation error: {e}")
        return f"В результате ДТП транспортному средству {data_str[:100]} причинены повреждения."


# ---------------------------------------------------------------------------
# Основной LLM-генератор ответов
# ---------------------------------------------------------------------------

_SYSTEM_PHASE1 = """\
Ты — консультант по взаимодействию со страховой компанией после ДТП.
Пользователь только что оформил Европротокол и готовится подавать документы.

Контекст из базы знаний:
{context}

История диалога:
{history}

Данные по ДТП:
{protocol_data}

ПРАВИЛА:
- Называй конкретные сроки: 5 рабочих дней на подачу, 15 дней запрет ремонта.
- Для ПВУ: обращаться в СВОЮ страховую. Исключение: лицензия отозвана → страховая виновника.
- Перечень документов: извещение о ДТП, заявление о ПВУ, копия паспорта. Больше не требуй.
- Не выдумывай статьи и суммы которых нет в контексте.
- Отвечай кратко — только на заданный вопрос.
"""

_SYSTEM_PHASE2 = """\
Ты — консультант по спорам со страховой компанией после ДТП.
Пользователь получил выплату и хочет её оспорить или узнать что делать дальше.

Контекст из базы знаний:
{context}

История диалога:
{history}

Данные по ДТП и выплате:
{protocol_data}

ПРАВИЛА:
- Объясняй цепочку эскалации пошагово, только когда пользователь к ней подходит:
  1. Письменное обращение в страховую (10 рабочих дней)
  2. Финансовый уполномоченный finombudsman.ru (15–30 дней) — обязателен до суда
  3. Банк России cbr.ru / РСА autoins.ru — параллельно с уполномоченным
  4. Суд — только после решения уполномоченного
- Не выдавай всю цепочку сразу — только текущий шаг.
- Для составления обращения скажи пользователю что поможешь составить его.
- Не выдумывай суммы и статьи которых нет в контексте.
"""


def _format_protocol_data(collected_fields: dict) -> str:
    parts = []
    if collected_fields.get(_KEY_DATE):
        parts.append(f"Дата ДТП: {collected_fields[_KEY_DATE]}")
    if collected_fields.get(_KEY_LOCATION):
        parts.append(f"Место: {collected_fields[_KEY_LOCATION]}")
    if collected_fields.get(_KEY_INSURER_A):
        parts.append(f"Страховая пользователя: {collected_fields[_KEY_INSURER_A]}")
    if collected_fields.get(_KEY_DAMAGE_A):
        parts.append(f"Повреждения: {collected_fields[_KEY_DAMAGE_A]}")
    if collected_fields.get("appeal_payment_amount"):
        parts.append(f"Выплата страховой: {collected_fields['appeal_payment_amount']} руб.")
    if collected_fields.get("appeal_repair_cost"):
        parts.append(f"Стоимость ремонта: {collected_fields['appeal_repair_cost']} руб.")
    return "\n".join(parts) if parts else "(данные не переданы)"


def _generate_answer(
    giga,
    query: str,
    context: str,
    history_text: str,
    collected_fields: dict,
    phase: str,
) -> str:
    system_template = _SYSTEM_PHASE1 if phase == "phase1" else _SYSTEM_PHASE2
    system_content = system_template.format(
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
        resp = giga.chat(payload)
        return resp.choices[0].message.content
    except Exception as e:
        print(f"[step3] generate error: {e}")
        return "Не удалось получить ответ. Обратитесь напрямую в страховую компанию."


# ---------------------------------------------------------------------------
# Обработчики фаз
# ---------------------------------------------------------------------------

def _handle_phase1(
    giga,
    query: str,
    history: list,
    collected_fields: dict,
    db,
    feedback_db,
) -> StepResponse:
    # Первый вход
    if not collected_fields.get("step3_entered"):
        collected_fields["step3_entered"] = True
        collected_fields["step3_turns"] = 0
        entry_text = _build_entry_message(collected_fields)
        return StepResponse(
            answer=entry_text,
            step_completed=False,
            next_step=Step.STEP3,
            slots={},
            collected_fields=collected_fields,
        )

    # Проверка перехода в фазу 2
    if _has_phase2_trigger(query):
        history_text = build_history(history, component="classifier")
        if _confirm_phase2_with_llm(giga, query, history_text):
            collected_fields["step3_phase"] = "phase2"
            return _handle_phase2(giga, query, history, collected_fields, db, feedback_db)

    # Обычный ответ
    context = get_context_for_category(db, feedback_db, query, "insurance_communication")
    history_text = build_history(history, component="generator", category="insurance_communication")
    answer = _generate_answer(giga, query, context, history_text, collected_fields, "phase1")

    # После 3 ходов спрашиваем о статусе выплаты
    turns = collected_fields.get("step3_turns", 0) + 1
    collected_fields["step3_turns"] = turns
    if turns >= 3 and not collected_fields.get("step3_payment_asked"):
        answer += (
            "\n\nКстати, вы уже подали документы в страховую? "
            "Если да — получили ли выплату и устраивает ли она вас?"
        )
        collected_fields["step3_payment_asked"] = True

    return StepResponse(
        answer=answer,
        step_completed=False,
        next_step=Step.STEP3,
        slots={},
        collected_fields=collected_fields,
    )


def _handle_phase2(
    giga,
    query: str,
    history: list,
    collected_fields: dict,
    db,
    feedback_db,
) -> StepResponse:
    # Первый вход в фазу 2
    if not collected_fields.get("step3_phase2_entered"):
        collected_fields["step3_phase2_entered"] = True
        intro = (
            "Понял. Давайте разберёмся с выплатой.\n\n"
            "Сколько выплатила страховая компания и какова реальная стоимость ремонта "
            "по оценке сервиса или независимой экспертизы?"
        )
        return StepResponse(
            answer=intro,
            step_completed=False,
            next_step=Step.STEP3,
            slots={},
            collected_fields=collected_fields,
        )

    # Извлекаем данные для обращения из сообщения
    _extract_appeal_data(giga, query, collected_fields)

    # Проверяем запрос на составление обращения
    q = query.strip().lower()
    wants_appeal = any(t in q for t in _APPEAL_REQUEST_TRIGGERS)

    if wants_appeal or (
        collected_fields.get("appeal_payment_amount")
        and collected_fields.get("appeal_repair_cost")
        and not collected_fields.get("appeal_generated")
    ):
        missing = _missing_appeal_data(collected_fields)
        if missing:
            return StepResponse(
                answer=(
                    f"Для составления обращения мне нужно уточнить:\n"
                    + "\n".join(f"— {m}" for m in missing)
                ),
                step_completed=False,
                next_step=Step.STEP3,
                slots={},
                collected_fields=collected_fields,
            )

        # Данных достаточно — генерируем обращение
        appeal_text, appeal_json = _generate_appeal(giga, collected_fields)
        collected_fields["appeal_generated"] = True

        return StepResponse(
            answer=(
                f"Вот текст обращения в страховую компанию:\n\n"
                f"```\n{appeal_text}\n```\n\n"
                f"Направьте его в страховую в письменном виде (почта с уведомлением "
                f"или лично под подпись). Срок ответа — 10 рабочих дней.\n\n"
                f"Если страховая не ответит или откажет — следующий шаг: "
                f"финансовый уполномоченный (finombudsman.ru). Это обязательный "
                f"досудебный этап."
            ),
            step_completed=False,
            next_step=Step.STEP3,
            slots={},
            collected_fields=collected_fields,
            final_json={"type": "appeal", "data": appeal_json},
        )

    # Обычный ответ о спорах
    context = get_context_for_category(db, feedback_db, query, "insurance_communication")
    history_text = build_history(history, component="generator", category="insurance_communication")
    answer = _generate_answer(giga, query, context, history_text, collected_fields, "phase2")

    return StepResponse(
        answer=answer,
        step_completed=False,
        next_step=Step.STEP3,
        slots={},
        collected_fields=collected_fields,
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
    Обрабатывает один шаг взаимодействия со страховой.

    collected_fields должен содержать (prefilled бэкендом):
      date, vehicle_a_insurer, vehicle_a_owner_name, vehicle_a_make_model,
      vehicle_a_reg_number, vehicle_a_policy_number, vehicle_a_damage, circumstances
    """
    # Детектор выхода
    q_lower = query.strip().lower().rstrip("!.,?")
    if q_lower in _EXIT_TRIGGERS and len(history) > 1:
        return StepResponse(
            answer="Удачи с оформлением! Если появятся вопросы — обращайтесь.",
            step_completed=True,
            next_step=Step.CONSULTANT_ONLY,
            slots={},
            collected_fields=collected_fields,
        )

    phase = collected_fields.get("step3_phase", "phase1")

    if phase == "phase2":
        return _handle_phase2(giga, query, history, collected_fields, db, feedback_db)

    return _handle_phase1(giga, query, history, collected_fields, db, feedback_db)