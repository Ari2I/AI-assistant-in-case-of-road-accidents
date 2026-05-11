"""
Step 2: Пошаговое заполнение Европротокола.

Архитектура хранения данных:
  - collected_fields: плоский dict с ключами вида vehicle_a_make_model.
    Используется внутри агента для трекинга заполнения.
  - final_json.data: вложенная структура (accident / vehicle_a / vehicle_b / ...).
    Передаётся бэкенду для генерации PDF.

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
# Конфигурация вопросов
#
# keys         — все плоские ключи, которые заполняет эта группа
# required_keys — ключи, обязательные для закрытия группы
#                (если не указано — все keys считаются обязательными)
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
        "required_keys": ["location"],  # witnesses опциональны
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

# Порядок обхода групп вопросов
FIELDS_ORDER: list[str] = list(FIELDS_CONFIG.keys())

# Все плоские ключи с описаниями для промпта извлечения
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
# Проверка возможности Европротокола (используется из core.py)
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
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _get_current_group(collected: dict) -> str | None:
    """
    Возвращает id первой незавершённой группы вопросов.
    Группа завершена, если все её required_keys заполнены.
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
    """
    filled_str = (
        "\n".join(f"  {k}: {v}" for k, v in existing.items())
        if existing else "  (нет заполненных полей)"
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
            print(f"[step2] prefilled {len(prefilled)} fields from history: {list(prefilled.keys())}")
        return prefilled
    except Exception as e:
        print(f"[step2] prefill from history error: {e}")
        return {}


def _build_final_data(fields: dict) -> dict:
    """
    Конвертирует плоский dict collected_fields в вложенную структуру для бэкенда.
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
        "circumstances":       fields.get("circumstances"),
        "scheme":              fields.get("scheme"),
        "has_disagreement":    fields.get("has_disagreement", False),
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

    При первом входе (collected_fields пустой) пытается prefill из истории step1.
    Затем извлекает данные из текущего сообщения, обновляет collected_fields
    и возвращает вопрос по следующей незавершённой группе или финальный JSON.
    """
    # Prefill из истории step1 — только при первом входе
    if not collected_fields:
        collected_fields = _map_slots_to_fields(giga, slots, history)

    # Определяем текущую группу ДО извлечения (нужна как подсказка LLM)
    current_group = _get_current_group(collected_fields)

    # Извлекаем данные из сообщения пользователя
    try:
        new_data = _extract_fields_llm(giga, query, collected_fields, current_group or "")
        for k, v in new_data.items():
            if v is not None:
                collected_fields[k] = v
    except Exception as e:
        print(f"[step2] extraction error: {e}")

    # Пересчитываем текущую группу после обновления
    current_group = _get_current_group(collected_fields)

    # Все группы закрыты → формируем final_json
    if current_group is None:
        final_json = {
            "type": "europrotocol",
            "status": "ready_for_pdf",
            "data": _build_final_data(collected_fields),
        }
        return StepResponse(
            answer=(
                "✅ Все данные собраны! Направьте извещение в страховую компанию "
                "в течение 5 рабочих дней. Данные переданы для формирования PDF."
            ),
            step_completed=True,
            next_step=Step.DONE,
            collected_fields=collected_fields,
            final_json=final_json,
        )

    # Задаём вопрос по текущей группе
    config = FIELDS_CONFIG[current_group]
    answer = f"{config['instruction']}\n\n{config['prompt']}"

    return StepResponse(
        answer=answer,
        step_completed=False,
        next_step=Step.STEP2,
        collected_fields=collected_fields,
    )