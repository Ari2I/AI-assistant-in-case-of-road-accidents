"""
Step 2: Пошаговое заполнение Европротокола.

Архитектура хранения данных:
  - collected_fields: плоский dict с ключами вида vehicle_a_make_model.
    Используется внутри агента для трекинга заполнения.
  - final_json.data: вложенная структура (accident / vehicle_a / vehicle_b / ...).
    Передаётся бэкенду для генерации PDF.

Реформулировка текстовых полей:
  Поля с произвольным описанием (обстоятельства, повреждения, схема) не сохраняются
  напрямую из слов пользователя. LLM предлагает официальную формулировку,
  пользователь подтверждает / редактирует / отклоняет.

  Ожидающая подтверждения формулировка хранится в collected_fields под
  ключом _PENDING_KEY и передаётся Django между запросами как часть словаря.

Структура вопросов:
  FIELDS_CONFIG описывает 13 групп вопросов. Каждая группа заполняет
  один или несколько плоских ключей. Группа считается завершённой,
  когда заполнены все её required_keys.
"""

from __future__ import annotations

import json

from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

from agent.step_types import Step, StepResponse

# ---------------------------------------------------------------------------
# Константы лимитов выплат
# ---------------------------------------------------------------------------

LIMIT_BASE = 100_000
LIMIT_WITH_APP_NO_DISAGREEMENT = 400_000
LIMIT_WITH_APP_DISAGREEMENT = 200_000

# ---------------------------------------------------------------------------
# Ключ для хранения ожидающей подтверждения реформулировки
# ---------------------------------------------------------------------------

_PENDING_KEY = "_pending_reformulation"

# ---------------------------------------------------------------------------
# Поля, требующие реформулировки перед сохранением.
# Числовые, именные и идентификационные поля реформулировки не требуют.
# ---------------------------------------------------------------------------

_FIELDS_NEEDING_REFORMULATION: frozenset[str] = frozenset({
    "circumstances",
    "scheme",
    "vehicle_a_damage",
    "vehicle_b_damage",
})

_FIELD_DESCRIPTIONS_FOR_REFORMULATION: dict[str, str] = {
    "circumstances": "Обстоятельства ДТП (пункт 11 / оборотная сторона, пункт 15)",
    "scheme":        "Описание схемы ДТП (пункт 12)",
    "vehicle_a_damage": "Характер и перечень видимых повреждений ТС А (пункт 9)",
    "vehicle_b_damage": "Характер и перечень видимых повреждений ТС Б (пункт 9)",
}

_REFORMULATION_PROMPT = """\
Ты — помощник по оформлению Европротокола о ДТП.

Пользователь описал произошедшее в произвольной форме. Переформулируй его описание \
для официального извещения о дорожно-транспортном происшествии.

Требования:
1. Официально-деловой стиль, без разговорных выражений.
2. Для обстоятельств: указывай направление движения, манёвры, взаимное положение ТС \
   (например: «ТС А двигалось по ул. Ленина в направлении севера, выполняло поворот налево...»).
3. Для повреждений: используй только термины "вмятина", "царапина", "трещина", "скол", \
   "разрыв", "разрушение" с указанием конкретной детали \
   (например: «передний бампер — трещина, левое переднее крыло — вмятина»).
4. Для схемы: описывай взаимное положение ТС, дороги, знаки, направление движения \
   (например: «ТС А стояло у правой обочины, ТС Б въехало в заднюю часть ТС А»).
5. Текст должен быть готов для вставки в соответствующую графу Европротокола без изменений.

Поле: {field_description}
Исходный текст пользователя: {original_text}

Верни ТОЛЬКО переформулированный текст — без пояснений, кавычек и markdown.
"""

# Фразы, которые означают одобрение реформулировки
_APPROVAL_PHRASES: frozenset[str] = frozenset({
    "да", "ок", "ok", "хорошо", "верно", "правильно", "согласен", "согласна",
    "подтверждаю", "подтверждаю.", "да.", "ок.", "ладно", "отлично", "супер",
    "принято", "принять", "сохранить", "сохрани",
})

# Фразы, которые означают отклонение реформулировки (сохраняем оригинал)
_REJECTION_PHRASES: frozenset[str] = frozenset({
    "нет", "нет.", "отклонить", "отклоняю", "не подходит", "не то",
    "неверно", "неправильно", "оставь оригинал", "оставить оригинал",
})

# ---------------------------------------------------------------------------
# Конфигурация вопросов
# ---------------------------------------------------------------------------

FIELDS_CONFIG: dict[str, dict] = {
    "datetime": {
        "prompt": "Когда произошло ДТП? Укажите дату и точное время.",
        "instruction": "Формат: ДД.ММ.ГГГГ ЧЧ:ММ — например, 15.01.2024 14:30",
        "keys": ["date", "time"],
    },
    "location_witnesses": {
        "prompt": (
            "Где точно произошло ДТП? "
            "И есть ли свидетели — если да, ФИО и номер телефона."
        ),
        "instruction": (
            "Адрес: город, улица, дом. Для трасс — название и километр. "
            "Свидетелей нет — так и напишите."
        ),
        "keys": ["location", "witnesses"],
        "required_keys": ["location"],
    },
    "vehicle_a_base": {
        "prompt": "Данные автомобиля А: марка/модель и государственный номер.",
        "instruction": "Пример: Toyota Camry, госномер А123БВ777",
        "keys": ["vehicle_a_make_model", "vehicle_a_reg_number"],
    },
    "vehicle_a_persons": {
        "prompt": (
            "Владелец авто А: ФИО. "
            "Водитель (если отличается от владельца): ФИО и номер водительского удостоверения."
        ),
        "instruction": "Если водитель = владелец — укажите одни данные.",
        "keys": ["vehicle_a_owner_name", "vehicle_a_driver_name", "vehicle_a_driver_license"],
        "required_keys": ["vehicle_a_owner_name", "vehicle_a_driver_name"],
    },
    "vehicle_a_insurance": {
        "prompt": "Страховая компания авто А, серия и номер полиса ОСАГО, дата окончания.",
        "instruction": "Пример: Росгосстрах, ХХХ 1234567890, действует до 31.12.2025",
        "keys": ["vehicle_a_insurer", "vehicle_a_policy_number", "vehicle_a_policy_expiry"],
    },
    "vehicle_a_damage": {
        "prompt": "Место первоначального удара на авто А и перечень видимых повреждений.",
        "instruction": (
            "Место удара — конкретная деталь: бампер, дверь, крыло. "
            "Повреждения: вмятина / царапина / трещина. Только видимые."
        ),
        "keys": ["vehicle_a_impact_point", "vehicle_a_damage"],
    },
    "vehicle_b_base": {
        "prompt": "Данные автомобиля Б: марка/модель и государственный номер.",
        "instruction": "Пример: Honda Civic, госномер В456ГД777",
        "keys": ["vehicle_b_make_model", "vehicle_b_reg_number"],
    },
    "vehicle_b_persons": {
        "prompt": (
            "Владелец авто Б: ФИО. "
            "Водитель (если отличается от владельца): ФИО и номер водительского удостоверения."
        ),
        "instruction": "Если водитель = владелец — укажите одни данные.",
        "keys": ["vehicle_b_owner_name", "vehicle_b_driver_name", "vehicle_b_driver_license"],
        "required_keys": ["vehicle_b_owner_name", "vehicle_b_driver_name"],
    },
    "vehicle_b_insurance": {
        "prompt": "Страховая компания авто Б, серия и номер полиса ОСАГО, дата окончания.",
        "instruction": "Пример: СОГАЗ, ЕЕЕ 0987654321, действует до 30.06.2025",
        "keys": ["vehicle_b_insurer", "vehicle_b_policy_number", "vehicle_b_policy_expiry"],
    },
    "vehicle_b_damage": {
        "prompt": "Место первоначального удара на авто Б и перечень видимых повреждений.",
        "instruction": "Место удара — деталь. Повреждения: вмятина / царапина / трещина.",
        "keys": ["vehicle_b_impact_point", "vehicle_b_damage"],
    },
    "fault_circumstances": {
        "prompt": (
            "Опишите обстоятельства ДТП: кто и как двигался, какие манёвры выполнял. "
            "Укажите, кто из водителей признаёт вину."
        ),
        "instruction": (
            "Обстоятельства: свободный текст. "
            "Вина: 'виноват А', 'виноват Б', 'оба оспаривают' — выберите подходящее."
        ),
        "keys": ["circumstances", "vehicle_a_fault", "vehicle_b_fault"],
        "required_keys": ["circumstances"],
    },
    "scheme": {
        "prompt": (
            "Опишите схему ДТП: расположение автомобилей в момент удара "
            "и направление движения."
        ),
        "instruction": (
            "Пример: Авто А двигалось по ул. Ленина с севера на юг, "
            "авто Б выезжало из двора справа и ударило в левый бок авто А."
        ),
        "keys": ["scheme"],
    },
    "signatures": {
        "prompt": "Подтвердите, что оба водителя готовы подписать извещение.",
        "instruction": (
            "Напомните второму участнику: подписи нужны на лицевой стороне "
            "в обеих колонках (А и Б) и на обороте каждый своей рукой."
        ),
        "keys": ["signatures_confirmed"],
    },
}

FIELDS_ORDER: list[str] = list(FIELDS_CONFIG.keys())

_FLAT_KEYS_DESCRIPTION = """
date: дата ДТП (формат: ДД.ММ.ГГГГ)
time: время ДТП (формат: ЧЧ:ММ)
location: точное место ДТП — город, улица, дом или км трассы
witnesses: данные свидетелей (ФИО, телефон) или null

vehicle_a_make_model: марка и модель авто А
vehicle_a_reg_number: государственный номер авто А
vehicle_a_owner_name: ФИО владельца авто А
vehicle_a_driver_name: ФИО водителя авто А
vehicle_a_driver_license: номер водительского удостоверения водителя А
vehicle_a_insurer: название страховой компании авто А
vehicle_a_policy_number: серия и номер полиса ОСАГО авто А
vehicle_a_policy_expiry: дата окончания полиса ОСАГО авто А
vehicle_a_impact_point: деталь первоначального удара на авто А
vehicle_a_damage: перечень видимых повреждений авто А
vehicle_a_fault: признание вины водителя А ("виноват" / "не виноват")

vehicle_b_make_model: марка и модель авто Б
vehicle_b_reg_number: государственный номер авто Б
vehicle_b_owner_name: ФИО владельца авто Б
vehicle_b_driver_name: ФИО водителя авто Б
vehicle_b_driver_license: номер водительского удостоверения водителя Б
vehicle_b_insurer: название страховой компании авто Б
vehicle_b_policy_number: серия и номер полиса ОСАГО авто Б
vehicle_b_policy_expiry: дата окончания полиса ОСАГО авто Б
vehicle_b_impact_point: деталь первоначального удара на авто Б
vehicle_b_damage: перечень видимых повреждений авто Б
vehicle_b_fault: признание вины водителя Б ("виноват" / "не виноват")

circumstances: обстоятельства ДТП (свободный текст)
scheme: схема ДТП (свободный текст)
has_disagreement: есть ли разногласия между участниками (true / false)
signatures_confirmed: оба водителя готовы подписать извещение (true / false)
"""

_FIELD_EXTRACTION_PROMPT = """\
Извлеки данные для Европротокола из сообщения пользователя.

Описание всех возможных полей:
{keys_description}

Уже заполненные поля (не перезаписывай):
{filled_fields}

Текущая группа вопросов (что ожидается в первую очередь): {current_group}
Ключи этой группы: {current_keys}

Правила:
- Если сообщение содержит данные для ключей текущей группы — обязательно извлеки.
- Если сообщение содержит данные и для других незаполненных полей — тоже извлеки.
- Не перезаписывай уже заполненные поля.
- Если данных для поля нет — не включай ключ в ответ.
- Для signatures_confirmed: "да", "ок", "подпишем" и подобные → true.
- Для witnesses: "нет", "свидетелей нет" → сохрани строку "нет".
- Верни ТОЛЬКО валидный JSON без пояснений и markdown.

Сообщение пользователя: "{message}"
"""


# ---------------------------------------------------------------------------
# Проверка возможности Европротокола
# ---------------------------------------------------------------------------

class StopFactor:
    def __init__(self, code: str, message: str, severity: str):
        self.code = code
        self.message = message
        self.severity = severity

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "severity": self.severity}


class EuroprotocolCheckResult:
    def __init__(
        self,
        is_possible: bool | str,
        stop_factors: list,
        recommendation: str,
        next_step: str,
        limits: dict,
    ):
        self.is_possible = is_possible
        self.stop_factors = stop_factors
        self.recommendation = recommendation
        self.next_step = next_step
        self.limits = limits

    def to_dict(self) -> dict:
        return {
            "is_possible": self.is_possible,
            "stop_factors": [
                sf.to_dict() if hasattr(sf, "to_dict") else sf
                for sf in self.stop_factors
            ],
            "recommendation": self.recommendation,
            "next_step": self.next_step,
            "limits": self.limits,
        }


def validate_slots_for_step2(slots: dict) -> tuple[bool, list[str]]:
    required_keys = ["victims", "participants_count", "osago_both", "disagreement"]
    errors: list[str] = []

    for key in required_keys:
        if key not in slots:
            errors.append(f"Missing required slot: {key}")

    if errors:
        return (False, errors)

    if slots["victims"] is not None and not isinstance(slots["victims"], bool):
        errors.append(f"victims must be bool or None, got {type(slots['victims']).__name__}")

    if slots["participants_count"] is not None and not isinstance(slots["participants_count"], int):
        errors.append(
            f"participants_count must be int or None, got {type(slots['participants_count']).__name__}"
        )

    if slots["osago_both"] is not None and not isinstance(slots["osago_both"], bool):
        errors.append(f"osago_both must be bool or None, got {type(slots['osago_both']).__name__}")

    if slots["disagreement"] is not None and not isinstance(slots["disagreement"], bool):
        errors.append(f"disagreement must be bool or None, got {type(slots['disagreement']).__name__}")

    return (not bool(errors), errors)


def process_step2_check(slots: dict, has_app: bool) -> EuroprotocolCheckResult:
    stop_factors: list[StopFactor] = []

    if slots.get("victims") is True:
        stop_factors.append(StopFactor("victims", "Есть пострадавшие", "critical"))

    p_count = slots.get("participants_count")
    if p_count is not None:
        if p_count > 2:
            stop_factors.append(StopFactor("participants_3plus", "Участников больше двух", "critical"))
        elif p_count == 1:
            stop_factors.append(StopFactor("participants_1", "ДТП с одним участником", "critical"))

    if slots.get("osago_both") is False:
        stop_factors.append(StopFactor("no_osago", "Нет ОСАГО у одного из участников", "critical"))

    if stop_factors:
        parts = []
        for sf in stop_factors:
            if sf.code == "victims":
                parts.append("Немедленно вызовите скорую (103) и ГИБДД (102).")
            else:
                parts.append("Вызовите ГИБДД (102).")
        return EuroprotocolCheckResult(
            is_possible=False,
            stop_factors=stop_factors,
            recommendation=" ".join(parts),
            next_step="call_gibdd",
            limits={},
        )

    disagreement = slots.get("disagreement")

    if disagreement is True and not has_app:
        return EuroprotocolCheckResult(
            is_possible="conditional",
            stop_factors=[StopFactor("disagreement_no_app", "Разногласия без приложения", "warning")],
            recommendation=(
                "При разногласиях рекомендуется использовать приложение "
                "«Помощник ОСАГО» или «Госуслуги Авто» для фиксации ДТП."
            ),
            next_step="step3_fixation_with_disagreement",
            limits={"base": 0, "with_app": LIMIT_WITH_APP_DISAGREEMENT},
        )

    if disagreement is True and has_app:
        return EuroprotocolCheckResult(
            is_possible=True,
            stop_factors=[],
            recommendation="Европротокол возможен с приложением. Максимальная выплата до 200 000 руб.",
            next_step="step3_fixation",
            limits={"base": LIMIT_WITH_APP_DISAGREEMENT},
        )

    if has_app:
        limit = LIMIT_WITH_APP_NO_DISAGREEMENT
        recommendation = (
            f"Европротокол возможен. С приложением максимальная выплата до {limit // 1000} 000 руб."
        )
    else:
        limit = LIMIT_BASE
        recommendation = (
            f"Европротокол возможен. Максимальная выплата до {limit // 1000} 000 руб. "
            "Рекомендуется использовать приложение для увеличения лимита до 400 000 руб."
        )

    return EuroprotocolCheckResult(
        is_possible=True,
        stop_factors=[],
        recommendation=recommendation,
        next_step="step3_fixation",
        limits={"base": limit},
    )


# ---------------------------------------------------------------------------
# Реформулировка текстовых полей
# ---------------------------------------------------------------------------

def _reformulate_field(giga: GigaChat, field: str, original_text: str) -> str:
    """
    Вызывает LLM для реформулировки произвольного описания в официальный стиль
    Европротокола.

    При ошибке возвращает оригинальный текст без изменений.
    """
    field_description = _FIELD_DESCRIPTIONS_FOR_REFORMULATION.get(field, field)
    prompt = _REFORMULATION_PROMPT.format(
        field_description=field_description,
        original_text=original_text,
    )
    try:
        payload = Chat(
            messages=[
                Messages(
                    role=MessagesRole.SYSTEM,
                    content=(
                        "Ты — юридический редактор. Переформулируй текст для "
                        "официального протокола о ДТП. Отвечай только готовым текстом."
                    ),
                ),
                Messages(role=MessagesRole.USER, content=prompt),
            ],
            temperature=0.1,
        )
        response = giga.chat(payload)
        result = response.choices[0].message.content.strip().strip('"').strip("'")
        return result if result else original_text
    except Exception as e:
        print(f"[step2] reformulation error for '{field}': {e}")
        return original_text


def _build_pending_proposal(
    giga: GigaChat,
    field: str,
    original: str,
    remaining: dict[str, str],
) -> tuple[dict, str]:
    """
    Реформулирует первое поле из очереди и формирует структуру pending + текст ответа.

    Returns:
        pending_state: dict для сохранения в collected_fields[_PENDING_KEY]
        answer_text: текст для пользователя
    """
    reformulated = _reformulate_field(giga, field, original)
    field_desc = _FIELD_DESCRIPTIONS_FOR_REFORMULATION.get(field, field)

    pending_state = {
        "field": field,
        "original": original,
        "reformulated": reformulated,
        "remaining": remaining,
    }

    answer_text = (
        f"На основе вашего описания я подготовил формулировку "
        f"для поля «{field_desc}»:\n\n"
        f"«{reformulated}»\n\n"
        f"Подтвердите вариант («да»), напишите свою версию или отклоните («нет», "
        f"тогда сохранится ваш исходный текст без изменений)."
    )

    return pending_state, answer_text


def _handle_reformulation_response(
    giga: GigaChat,
    query: str,
    collected_fields: dict,
    pending: dict,
) -> StepResponse:
    """
    Обрабатывает ответ пользователя на предложение реформулировки.

    Логика:
      - "да" / одобрение → сохраняем reformulated
      - "нет" / отклонение → сохраняем original (предупреждаем)
      - любой другой текст → считаем правкой пользователя, сохраняем его вариант
    """
    q = query.strip().lower().rstrip("!.,?")
    field = pending["field"]

    if q in _APPROVAL_PHRASES:
        saved_value = pending["reformulated"]
        save_note = ""
    elif q in _REJECTION_PHRASES:
        saved_value = pending["original"]
        save_note = (
            "\n\n⚠️ Сохранена ваша исходная формулировка без изменений. "
            "Это может затруднить обработку страховой компанией."
        )
    else:
        # Пользователь предоставил собственный вариант
        saved_value = query.strip()
        save_note = ""

    collected_fields[field] = saved_value

    # Убираем pending
    collected_fields.pop(_PENDING_KEY, None)

    # Есть ещё поля в очереди на реформулировку?
    remaining: dict[str, str] = pending.get("remaining", {})
    if remaining:
        next_field, next_original = next(iter(remaining.items()))
        next_remaining = {k: v for k, v in remaining.items() if k != next_field}
        next_pending, next_answer = _build_pending_proposal(
            giga, next_field, next_original, next_remaining
        )
        collected_fields[_PENDING_KEY] = next_pending

        prefix = "Записано." + save_note + "\n\n"
        return StepResponse(
            answer=prefix + next_answer,
            step_completed=False,
            next_step=Step.STEP2,
            collected_fields=collected_fields,
        )

    # Все реформулировки обработаны — переходим к следующей группе
    if save_note:
        prefix = "Записан ваш вариант." + save_note + "\n\n"
    else:
        prefix = "Записано.\n\n"

    return _continue_after_save(collected_fields, prefix)


def _continue_after_save(collected_fields: dict, prefix: str = "") -> StepResponse:
    """
    Определяет следующее действие после сохранения полей:
    либо задаёт следующий вопрос, либо формирует final_json.
    """
    current_group = _get_current_group(collected_fields)

    if current_group is None:
        # Все группы закрыты
        final_json = {
            "type": "europrotocol",
            "status": "ready_for_pdf",
            "data": _build_final_data(collected_fields),
        }
        return StepResponse(
            answer=(
                prefix
                + "✅ Все данные собраны! Направьте извещение в страховую компанию "
                "в течение 5 рабочих дней. Данные переданы для формирования PDF."
            ),
            step_completed=True,
            next_step=Step.DONE,
            collected_fields=collected_fields,
            final_json=final_json,
        )

    config = FIELDS_CONFIG[current_group]
    return StepResponse(
        answer=prefix + f"{config['instruction']}\n\n{config['prompt']}",
        step_completed=False,
        next_step=Step.STEP2,
        collected_fields=collected_fields,
    )


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _get_current_group(collected: dict) -> str | None:
    """
    Возвращает id первой незавершённой группы вопросов.
    Группа завершена, если все её required_keys заполнены.
    Ключ _PENDING_KEY не учитывается при проверке.
    """
    for group_id, config in FIELDS_CONFIG.items():
        required = config.get("required_keys", config["keys"])
        if not all(collected.get(k) for k in required):
            return group_id
    return None


def _extract_fields_llm(
    giga: GigaChat,
    message: str,
    existing: dict,
    current_group: str = "",
) -> dict:
    """
    Вызывает LLM для извлечения плоских ключей из сообщения пользователя.
    Делает до 2 попыток при пустом результате.

    Ключ _PENDING_KEY исключён из existing при передаче в промпт.
    """
    # Исключаем служебный ключ из вывода "уже заполненных полей"
    existing_clean = {k: v for k, v in existing.items() if k != _PENDING_KEY}

    filled_str = (
        "\n".join(f"  {k}: {v}" for k, v in existing_clean.items())
        if existing_clean else "  (нет заполненных полей)"
    )

    current_keys = ""
    if current_group and current_group in FIELDS_CONFIG:
        current_keys = ", ".join(FIELDS_CONFIG[current_group]["keys"])

    prompt = _FIELD_EXTRACTION_PROMPT.format(
        keys_description=_FLAT_KEYS_DESCRIPTION,
        filled_fields=filled_str,
        current_group=current_group or "не определена",
        current_keys=current_keys or "—",
        message=message,
    )

    for attempt in range(2):
        try:
            payload = Chat(
                messages=[
                    Messages(
                        role="system",
                        content=(
                            "Ты — структурированный экстрактор данных для Европротокола. "
                            "Отвечай только JSON. Никаких пояснений."
                        ),
                    ),
                    Messages(role="user", content=prompt),
                ],
                temperature=0.0,
            )
            response = giga.chat(payload)
            content = response.choices[0].message.content.strip()

            if "```" in content:
                for part in content.split("```"):
                    stripped = part.strip()
                    if stripped.startswith("{"):
                        content = stripped
                        break

            extracted = json.loads(content)
            result = {k: v for k, v in extracted.items() if v is not None}
            if result:
                return result

        except json.JSONDecodeError as e:
            print(f"[step2] JSON parse error (attempt {attempt + 1}): {e}")
        except Exception as e:
            print(f"[step2] field extraction error (attempt {attempt + 1}): {e}")

    return {}


def _map_slots_to_fields(giga: GigaChat, slots: dict, history: list) -> dict:
    """
    Извлекает данные для step2 из всей истории диалога (step1).
    Вызывается ОДИН РАЗ при первом входе в step2.

    Текстовые поля, требующие реформулировки, НЕ сохраняются сразу — они будут
    предложены пользователю для подтверждения в первом же шаге step2.
    """
    if not history:
        return {}

    full_context = "\n".join(
        f"Пользователь: {h['query']}\nАссистент: {h['answer']}"
        for h in history
    )

    try:
        prefilled = _extract_fields_llm(
            giga,
            message=full_context,
            existing={},
            current_group="",
        )
        if prefilled:
            print(
                f"[step2] prefilled {len(prefilled)} fields from history: "
                f"{list(prefilled.keys())}"
            )
        return prefilled
    except Exception as e:
        print(f"[step2] prefill from history error: {e}")
        return {}


def _build_final_data(fields: dict) -> dict:
    """
    Конвертирует плоский dict collected_fields в вложенную структуру для бэкенда.
    Служебный ключ _PENDING_KEY при этом отбрасывается.
    """
    return {
        "accident": {
            "date":      fields.get("date"),
            "time":      fields.get("time"),
            "location":  fields.get("location"),
            "witnesses": fields.get("witnesses"),
        },
        "vehicle_a": {
            "make_model":     fields.get("vehicle_a_make_model"),
            "reg_number":     fields.get("vehicle_a_reg_number"),
            "owner_name":     fields.get("vehicle_a_owner_name"),
            "driver_name":    fields.get("vehicle_a_driver_name"),
            "driver_license": fields.get("vehicle_a_driver_license"),
            "insurer":        fields.get("vehicle_a_insurer"),
            "policy_number":  fields.get("vehicle_a_policy_number"),
            "policy_expiry":  fields.get("vehicle_a_policy_expiry"),
            "impact_point":   fields.get("vehicle_a_impact_point"),
            "damage":         fields.get("vehicle_a_damage"),
            "fault":          fields.get("vehicle_a_fault"),
        },
        "vehicle_b": {
            "make_model":     fields.get("vehicle_b_make_model"),
            "reg_number":     fields.get("vehicle_b_reg_number"),
            "owner_name":     fields.get("vehicle_b_owner_name"),
            "driver_name":    fields.get("vehicle_b_driver_name"),
            "driver_license": fields.get("vehicle_b_driver_license"),
            "insurer":        fields.get("vehicle_b_insurer"),
            "policy_number":  fields.get("vehicle_b_policy_number"),
            "policy_expiry":  fields.get("vehicle_b_policy_expiry"),
            "impact_point":   fields.get("vehicle_b_impact_point"),
            "damage":         fields.get("vehicle_b_damage"),
            "fault":          fields.get("vehicle_b_fault"),
        },
        "circumstances":        fields.get("circumstances"),
        "scheme":               fields.get("scheme"),
        "has_disagreement":     fields.get("has_disagreement", False),
        "signatures_confirmed": fields.get("signatures_confirmed"),
    }


# ---------------------------------------------------------------------------
# Главная функция шагового режима
# ---------------------------------------------------------------------------

def process_step2_with_llm(
    giga: GigaChat,
    query: str,
    history: list,
    slots: dict,
    collected_fields: dict,
) -> StepResponse:
    """
    Обрабатывает один шаг заполнения Европротокола.

    Алгоритм:
    1. Если в collected_fields есть _PENDING_KEY — пользователь отвечает на
       предложение реформулировки. Передаём управление _handle_reformulation_response.
    2. При первом входе (collected_fields пустой) prefill из истории step1.
    3. Извлекаем данные из текущего сообщения пользователя.
    4. Структурные поля (даты, имена, номера) сохраняем сразу.
    5. Текстовые поля (_FIELDS_NEEDING_REFORMULATION) — реформулируем и предлагаем
       пользователю для подтверждения через _PENDING_KEY.
    6. Если все группы закрыты — формируем final_json.
    """

    # ШАГ 1: ожидаем ответа на реформулировку
    pending = collected_fields.get(_PENDING_KEY)
    if pending:
        return _handle_reformulation_response(giga, query, collected_fields, pending)

    # ШАГ 2: prefill из истории step1 при первом входе
    if not collected_fields:
        collected_fields = _map_slots_to_fields(giga, slots, history)

    # Определяем текущую группу ДО извлечения (нужна как подсказка LLM)
    current_group = _get_current_group(collected_fields)

    # ШАГ 3: извлечение данных из сообщения пользователя
    try:
        new_data = _extract_fields_llm(giga, query, collected_fields, current_group or "")
    except Exception as e:
        print(f"[step2] extraction error: {e}")
        new_data = {}

    if not new_data:
        # Ничего не извлекли — просто повторяем вопрос текущей группы
        if current_group is None:
            return _continue_after_save(collected_fields)
        config = FIELDS_CONFIG[current_group]
        return StepResponse(
            answer=f"{config['instruction']}\n\n{config['prompt']}",
            step_completed=False,
            next_step=Step.STEP2,
            collected_fields=collected_fields,
        )

    # ШАГ 4: разделяем поля на «сохранить сразу» и «требуют реформулировки»
    to_save_directly: dict[str, object] = {}
    to_reformulate: dict[str, str] = {}

    for k, v in new_data.items():
        if v is None:
            continue
        if k in _FIELDS_NEEDING_REFORMULATION and isinstance(v, str) and v.strip():
            # Поле уже заполнено → не перезаписываем
            if not collected_fields.get(k):
                to_reformulate[k] = v
        else:
            to_save_directly[k] = v

    # Сохраняем структурные поля немедленно
    for k, v in to_save_directly.items():
        collected_fields[k] = v

    # ШАГ 5: если есть текстовые поля — запускаем цикл реформулировки
    if to_reformulate:
        first_field, first_original = next(iter(to_reformulate.items()))
        remaining = {k: v for k, v in to_reformulate.items() if k != first_field}

        pending_state, answer_text = _build_pending_proposal(
            giga, first_field, first_original, remaining
        )
        collected_fields[_PENDING_KEY] = pending_state

        return StepResponse(
            answer=answer_text,
            step_completed=False,
            next_step=Step.STEP2,
            collected_fields=collected_fields,
        )

    # ШАГ 6: только структурные поля → продолжаем сбор
    return _continue_after_save(collected_fields)