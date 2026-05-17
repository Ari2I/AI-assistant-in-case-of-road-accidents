"""
Step 2: Пошаговое заполнение Европротокола.

Изменения vs предыдущей версии:
  - _FLAT_KEYS_DESCRIPTION: добавлена явная разметка vehicle_a = пользователь,
    vehicle_b = второй участник — устраняет крос-контаминацию полей
  - _FIELD_EXTRACTION_PROMPT: добавлены few-shot примеры разделения участников
    и правило не обрывать circumstances/scheme на полуслове
  - _build_final_data: возвращает плоский dict вместо вложенного —
    структура совпадает с collected_fields, бэкенд сам группирует для PDF
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
# Служебный ключ для хранения ожидающей подтверждения реформулировки
# ---------------------------------------------------------------------------

_PENDING_KEY = "_pending_reformulation"

# ---------------------------------------------------------------------------
# Поля, требующие реформулировки перед сохранением
# ---------------------------------------------------------------------------

_FIELDS_NEEDING_REFORMULATION: frozenset[str] = frozenset({
    "circumstances",
    "scheme",
    "vehicle_a_damage",
    "vehicle_b_damage",
})

_FIELD_DESCRIPTIONS_FOR_REFORMULATION: dict[str, str] = {
    "circumstances": "Обстоятельства ДТП (пункт 11 / оборотная сторона, пункт 15)",
    "scheme": "Описание схемы ДТП (пункт 12)",
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

_APPROVAL_PHRASES: frozenset[str] = frozenset({
    "да", "ок", "ok", "хорошо", "верно", "правильно", "согласен", "согласна",
    "подтверждаю", "подтверждаю.", "да.", "ок.", "ладно", "отлично", "супер",
    "принято", "принять", "сохранить", "сохрани",
})

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
        "key_prompts": {
            "date": "Укажите дату ДТП.\nПример: 15.01.2024",
            "time": "Укажите точное время ДТП.\nПример: 14:30",
        },
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
        "required_keys": ["location", "witnesses"],
        "key_prompts": {
            "location": "Укажите точное место ДТП (город, улица, дом или км трассы).\nПример: Москва, ул. Ленина, д. 1",
            "witnesses": "Есть ли свидетели? Если да — укажите ФИО и номер телефона. Если нет — напишите «нет».\nПример: нет",
        },
    },
    "vehicle_a_base": {
        "prompt": "Данные вашего автомобиля: марка/модель и государственный номер.",
        "instruction": "Пример: Toyota Camry, госномер А123БВ777",
        "keys": ["vehicle_a_make_model", "vehicle_a_reg_number"],
        "key_prompts": {
            "vehicle_a_make_model": "Укажите марку и модель вашего автомобиля.\nПример: Toyota Camry",
            "vehicle_a_reg_number": "Укажите государственный номер вашего автомобиля.\nПример: А123БВ777",
        },
    },
    "vehicle_a_persons": {
        "prompt": (
            "Владелец вашего авто: ФИО. "
            "Водитель (если отличается от владельца): ФИО и номер водительского удостоверения."
        ),
        "instruction": "Если водитель = владелец — укажите одни данные.",
        "keys": ["vehicle_a_owner_name", "vehicle_a_driver_name", "vehicle_a_driver_license"],
        "required_keys": ["vehicle_a_owner_name", "vehicle_a_driver_name", "vehicle_a_driver_license"],
        "key_prompts": {
            "vehicle_a_owner_name": "Укажите ФИО владельца вашего автомобиля.\nПример: Иванов Иван Иванович",
            "vehicle_a_driver_name": "Укажите ФИО водителя вашего автомобиля.\nПример: Иванов Иван Иванович",
            "vehicle_a_driver_license": "Укажите номер вашего водительского удостоверения.\nПример: 77 77 123456",
        },

    },
    "vehicle_a_insurance": {
        "prompt": "Ваша страховая компания, серия и номер полиса ОСАГО, дата окончания.",
        "instruction": "Пример: Росгосстрах, ХХХ 1234567890, действует до 31.12.2025",
        "keys": ["vehicle_a_insurer", "vehicle_a_policy_number", "vehicle_a_policy_expiry"],
        "key_prompts": {
            "vehicle_a_insurer": "Укажите вашу страховую компанию.\nПример: Росгосстрах, СберСтрахование",
            "vehicle_a_policy_number": "Укажите серию и номер вашего полиса ОСАГО.\nПример: ХХХ 1234567890",
            "vehicle_a_policy_expiry": "Укажите срок действия вашего полиса ОСАГО.\nПример: действует до 31.12.2025",
        },
    },
    "vehicle_a_damage": {
        "prompt": "Место первоначального удара на вашем авто и перечень видимых повреждений.",
        "instruction": (
            "Место удара — конкретная деталь: бампер, дверь, крыло. "
            "Повреждения: вмятина / царапина / трещина. Только видимые."
        ),
        "keys": ["vehicle_a_impact_point", "vehicle_a_damage"],
        "key_prompts": {
            "vehicle_a_impact_point": "Укажите место первоначального удара на вашем авто.\nПример: левое переднее крыло",
            "vehicle_a_damage": "Перечислите видимые повреждения вашего авто.\nПример: левое переднее крыло — вмятина, бампер — царапина",
        },
    },
    "vehicle_b_base": {
        "prompt": "Данные автомобиля второго участника: марка/модель и государственный номер.",
        "instruction": "Пример: Honda Civic, госномер В456ГД777",
        "keys": ["vehicle_b_make_model", "vehicle_b_reg_number"],
        "key_prompts": {
            "vehicle_b_make_model": "Укажите марку и модель автомобиля второго участника.\nПример: Honda Civic",
            "vehicle_b_reg_number": "Укажите государственный номер автомобиля второго участника.\nПример: В456ГД777",
        },
    },
    "vehicle_b_persons": {
        "prompt": (
            "Владелец авто второго участника: ФИО. "
            "Водитель (если отличается от владельца): ФИО и номер водительского удостоверения."
        ),
        "instruction": "Если водитель = владелец — укажите одни данные.",
        "keys": ["vehicle_b_owner_name", "vehicle_b_driver_name", "vehicle_b_driver_license"],
        "required_keys": ["vehicle_b_owner_name", "vehicle_b_driver_name", "vehicle_b_driver_license"],
        "key_prompts": {
            "vehicle_b_owner_name": "Укажите ФИО владельца автомобиля второго участника.\nПример: Петров Пётр Петрович",
            "vehicle_b_driver_name": "Укажите ФИО водителя автомобиля второго участника.\nПример: Петров Пётр Петрович",
            "vehicle_b_driver_license": "Укажите номер водительского удостоверения водителя второго участника.\nПример: 77 77 654321",
        },
    },
    "vehicle_b_insurance": {
        "prompt": "Страховая компания второго участника, серия и номер полиса ОСАГО, дата окончания.",
        "instruction": "Пример: СОГАЗ, ЕЕЕ 0987654321, действует до 30.06.2025",
        "keys": ["vehicle_b_insurer", "vehicle_b_policy_number", "vehicle_b_policy_expiry"],
        "key_prompts": {
            "vehicle_b_insurer": "Укажите страховую второго участника .\nПример: СОГАЗ, СберСтрахование",
            "vehicle_b_policy_number": "Укажите серию и номер полиса ОСАГО второго участника.\nПример: ЕЕЕ 0987654321",
            "vehicle_b_policy_expiry": "Укажите сроки действия полиса ОСАГО второго участника.\nПример: действует до 30.06.2025",

        },
    },
    "vehicle_b_damage": {
        "prompt": "Место первоначального удара на авто второго участника и перечень видимых повреждений.",
        "instruction": "Место удара — деталь. Повреждения: вмятина / царапина / трещина.",
        "keys": ["vehicle_b_impact_point", "vehicle_b_damage"],
        "key_prompts": {
            "vehicle_b_impact_point": "Укажите место первоначального удара на авто второго участника.\nПример: задний бампер",
            "vehicle_b_damage": "Перечислите видимые повреждения авто второго участника.\nПример: задний бампер — трещина",
        },
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
        "key_prompts": {
            "circumstances": "Опишите обстоятельства ДТП: кто и как двигался, какие манёвры выполнял.\nПример: я ехал прямо по главной дороге, второй участник выезжал с второстепенной и не уступил",
            "vehicle_a_fault": "Признаёт ли водитель автомобиля А свою вину? (виноват / не виноват)\nПример: не виноват",
            "vehicle_b_fault": "Признаёт ли водитель автомобиля Б свою вину? (виноват / не виноват)\nПример: виноват",
        },
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

# ---------------------------------------------------------------------------
# Описание полей для промпта извлечения
# ИСПРАВЛЕНО: добавлена явная разметка участников A и B
# ---------------------------------------------------------------------------

_FLAT_KEYS_DESCRIPTION = """
⚠️ КРИТИЧЕСКИ ВАЖНО — РАЗЛИЧАЙ УЧАСТНИКОВ ДТП:

  vehicle_a_* = автомобиль и данные ПОЛЬЗОВАТЕЛЯ (того, кто заполняет форму)
    Признаки в тексте: «я», «мой», «моя машина», «мой автомобиль», «мне», «у меня»

  vehicle_b_* = автомобиль и данные ВТОРОГО участника
    Признаки в тексте: «второй», «другой водитель», «его машина», «её машина»,
                       «второй участник», «другой автомобиль»

  ЗАПРЕЩЕНО переносить данные участника А в поля vehicle_b и наоборот!
  Если принадлежность данных неясна — НЕ извлекай их.

date: дата ДТП (формат: ДД.ММ.ГГГГ)
time: время ДТП (формат: ЧЧ:ММ)
location: точное место ДТП — город, улица, дом или км трассы
witnesses: данные свидетелей (ФИО, телефон) или "нет"

vehicle_a_make_model: марка и модель автомобиля ПОЛЬЗОВАТЕЛЯ
vehicle_a_reg_number: государственный номер автомобиля ПОЛЬЗОВАТЕЛЯ
vehicle_a_owner_name: ФИО владельца автомобиля ПОЛЬЗОВАТЕЛЯ
vehicle_a_driver_name: ФИО водителя автомобиля ПОЛЬЗОВАТЕЛЯ
vehicle_a_driver_license: номер ВУ водителя автомобиля ПОЛЬЗОВАТЕЛЯ. Формат: XX XX YYYYYY, где XX — цифры, YY — цифры или буквы. Пример: 77 АА 123456 или 77 77 123456
vehicle_a_insurer: страховая компания автомобиля ПОЛЬЗОВАТЕЛЯ
vehicle_a_policy_number: серия и номер полиса ОСАГО автомобиля ПОЛЬЗОВАТЕЛЯ. Формат: ХХХ 0012345678
vehicle_a_policy_expiry: срок действия полиса ОСАГО автомобиля ПОЛЬЗОВАТЕЛЯ. Формат: С 15.05.2026 по 14.05.2027 включительно
vehicle_a_impact_point: деталь первоначального удара на автомобиле ПОЛЬЗОВАТЕЛЯ
vehicle_a_damage: повреждения автомобиля ПОЛЬЗОВАТЕЛЯ
vehicle_a_fault: вина водителя ПОЛЬЗОВАТЕЛЯ ("виноват" / "не виноват")

vehicle_b_make_model: марка и модель автомобиля ВТОРОГО участника
vehicle_b_reg_number: государственный номер автомобиля ВТОРОГО участника
vehicle_b_owner_name: ФИО владельца автомобиля ВТОРОГО участника
vehicle_b_driver_name: ФИО водителя автомобиля ВТОРОГО участника
vehicle_b_driver_license: номер ВУ водителя ВТОРОГО участника. Формат: XX XX YYYYYY, где XX — цифры, YY — цифры или буквы. Пример: 77 АА 123456 или 77 77 123456
vehicle_b_insurer: страховая компания ВТОРОГО участника
vehicle_b_policy_number: серия и номер полиса ОСАГО ВТОРОГО участника. Формат: ХХХ 0012345678
vehicle_b_policy_expiry: срок действия полиса ОСАГО ВТОРОГО участника. Формат: С 15.05.2026 по 14.05.2027 включительно
vehicle_b_impact_point: деталь первоначального удара на автомобиле ВТОРОГО участника
vehicle_b_damage: повреждения автомобиля ВТОРОГО участника
vehicle_b_fault: вина водителя ВТОРОГО участника ("виноват" / "не виноват")

circumstances: обстоятельства ДТП — ПОЛНЫЙ текст (кто куда ехал, манёвры, столкновение)
scheme: схема ДТП — ПОЛНЫЙ текст (взаимное положение ТС, направления движения)
has_disagreement: есть ли разногласия между участниками (true / false)
signatures_confirmed: оба водителя готовы подписать (true / false)
"""

# ---------------------------------------------------------------------------
# Промпт извлечения полей
# ИСПРАВЛЕНО: few-shot примеры разделения участников + правило не обрывать текст
# ---------------------------------------------------------------------------

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
- Для circumstances и scheme: извлекай ПОЛНЫЙ текст, не обрывай на полуслове.
- Для signatures_confirmed: «да», «ок», «подпишем», «подписали» → true.
- Для witnesses: «нет», «свидетелей нет» → сохрани строку "нет".
- Верни ТОЛЬКО валидный JSON без пояснений и markdown.

--- ПРИМЕРЫ ---

ПРИМЕР 1 — разделение участников (самое важное):
Сообщение: «Я на Toyota Camry А111БВ77, страховая Росгосстрах, полис ХХХ 0001
            до 31.12.2025. Второй — Kia Rio В222ГД77, страховая СОГАЗ,
            полис ЕЕЕ 0002 до 30.06.2025. Я не виноват, виноват второй.»
Ответ: {{
  "vehicle_a_make_model": "Toyota Camry",
  "vehicle_a_reg_number": "А111БВ77",
  "vehicle_a_insurer": "Росгосстрах",
  "vehicle_a_policy_number": "ХХХ 0001",
  "vehicle_a_policy_expiry": "31.12.2025",
  "vehicle_a_fault": "не виноват",
  "vehicle_b_make_model": "Kia Rio",
  "vehicle_b_reg_number": "В222ГД77",
  "vehicle_b_insurer": "СОГАЗ",
  "vehicle_b_policy_number": "ЕЕЕ 0002",
  "vehicle_b_policy_expiry": "30.06.2025",
  "vehicle_b_fault": "виноват"
}}

ПРИМЕР 2 — полный текст обстоятельств (не обрывать):
Сообщение: «Обстоятельства: я ехал прямо по правой полосе,
            второй выезжал задним ходом и въехал в мой бампер.»
Ответ: {{
  "circumstances": "я ехал прямо по правой полосе, второй выезжал задним ходом и въехал в мой бампер."
}}

ПРИМЕР 3 — данные одного человека (водитель = владелец):
Сообщение: «Водитель и владелец — один человек»
Ответ: {{
  "vehicle_a_driver_name": "<значение vehicle_a_owner_name из уже заполненных полей>"
}}
Пояснение: если vehicle_a_owner_name уже заполнен, vehicle_a_driver_name = то же значение.

ПРИМЕР 4 — водитель второго участника:
Сообщение: «Второй участник: владелец Иванов И.И., водитель Петров П.П., права 12 34 567890»
Ответ: {{
  "vehicle_b_owner_name": "Иванов И.И.",
  "vehicle_b_driver_name": "Петров П.П.",
  "vehicle_b_driver_license": "12 34 567890"
}}
Пояснение: для vehicle_b_* используй маркеры «второй», «другой», «его/её машина».

--- КОНЕЦ ПРИМЕРОВ ---

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
        if not result or len(result) < 10:
            return original_text
        return result
    except Exception as e:
        print(f"[step2] reformulation error for '{field}': {e}")
        return original_text


def _build_pending_proposal(
        giga: GigaChat,
        field: str,
        original: str,
        remaining: dict[str, str],
) -> tuple[dict, str] | None:
    reformulated = _reformulate_field(giga, field, original)

    if reformulated == original:
        return None

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
    elif not q:
        # Пустой ввод — просим повторить, не сохраняем
        field_desc = _FIELD_DESCRIPTIONS_FOR_REFORMULATION.get(field, field)
        return StepResponse(
            answer=(
                f"Пожалуйста, подтвердите формулировку для «{field_desc}»:\n\n"
                f"«{pending['reformulated']}»\n\n"
                f"Напишите «да» для подтверждения, «нет» для сохранения вашего варианта, "
                f"или введите собственный текст."
            ),
            step_completed=False,
            next_step=Step.STEP2,
            collected_fields=collected_fields,
        )
    else:
        saved_value = query.strip()
        save_note = ""

    collected_fields[field] = saved_value
    collected_fields.pop(_PENDING_KEY, None)

    remaining: dict[str, str] = pending.get("remaining", {})
    if remaining:
        remaining_items = list(remaining.items())
        while remaining_items:
            next_field, next_original = remaining_items.pop(0)
            next_remaining = dict(remaining_items)

            proposal = _build_pending_proposal(giga, next_field, next_original, next_remaining)

            if proposal is None:
                collected_fields[next_field] = next_original
                continue

            next_pending, next_answer = proposal
            collected_fields[_PENDING_KEY] = next_pending

            prefix = "Записано." + save_note + "\n\n"
            return StepResponse(
                answer=prefix + next_answer,
                step_completed=False,
                next_step=Step.STEP2,
                collected_fields=collected_fields,
            )

    if save_note:
        prefix = "Записан ваш вариант." + save_note + "\n\n"
    else:
        prefix = "Записано.\n\n"

    return _continue_after_save(collected_fields, prefix)


def _continue_after_save(collected_fields: dict, prefix: str = "") -> StepResponse:
    current_group = _get_current_group(collected_fields)

    if current_group is None:
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
    # Получаем первый незаполненный ключ в текущей группе
    missing_key = _get_missing_key_in_group(collected_fields, current_group)

    key_prompts = config.get("key_prompts", {})
    if missing_key and missing_key in key_prompts:
        question = key_prompts[missing_key]
    else:
        question = f"{config['instruction']}\n\n{config['prompt']}"

    return StepResponse(
        answer=prefix + question,
        step_completed=False,
        next_step=Step.STEP2,
        collected_fields=collected_fields,
    )


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _get_current_group(collected: dict) -> str | None:
    """
    Возвращает первую незаполненную группу.
    Группа считается незаполненной, если не заполнен ХОТЯ БЫ ОДИН её ключ.
    """
    for group_id, config in FIELDS_CONFIG.items():
        keys = config["keys"]
        if not all(collected.get(k) for k in keys):
            return group_id
    return None

def _get_missing_key_in_group(collected: dict, group_id: str) -> str | None:
    """
    Возвращает первый незаполненный ключ в указанной группе.
    Порядок определяется порядком ключей в конфиге.
    """
    config = FIELDS_CONFIG.get(group_id)
    if not config:
        return None
    keys = config["keys"]
    for key in keys:
        if not collected.get(key):
            return key
    return None

def _extract_fields_llm(
        giga: GigaChat,
        message: str,
        existing: dict,
        current_group: str = "",
) -> dict:
    existing_clean = {k: v for k, v in existing.items() if k != _PENDING_KEY}

    # Если владелец уже заполнен, а водитель нет — добавляем подсказку в filled
    # чтобы LLM мог применить правило «водитель = владелец» из примера 3
    display_existing = dict(existing_clean)

    filled_str = (
        "\n".join(f"  {k}: {v}" for k, v in display_existing.items())
        if display_existing else "  (нет заполненных полей)"
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

    had_any_success = False
    last_exception: Exception | None = None

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
            had_any_success = True
            if result:
                return result

        except Exception as e:
            print(f"[step2] field extraction error (attempt {attempt + 1}): {e}")
            last_exception = e

    if not had_any_success and last_exception:
        raise last_exception

    return {}


def _map_slots_to_fields(giga: GigaChat, slots: dict, history: list) -> dict:
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
    Возвращает плоский dict collected_fields без служебных ключей.
    Структура совпадает с тем, что накапливалось в collected_fields —
    бэкенд сам решает как сгруппировать поля для PDF-генератора.
    """
    skip = {_PENDING_KEY}
    return {k: v for k, v in fields.items() if k not in skip}


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
    # ШАГ 1: ожидаем ответа на реформулировку
    pending = collected_fields.get(_PENDING_KEY)
    if pending:
        return _handle_reformulation_response(giga, query, collected_fields, pending)

    # ШАГ 2: prefill из истории step1 при первом входе
    if not collected_fields:
        collected_fields = _map_slots_to_fields(giga, slots, history)

    current_group = _get_current_group(collected_fields)

    # ШАГ 3: извлечение данных
    had_error = False
    try:
        new_data = _extract_fields_llm(giga, query, collected_fields, current_group or "")
    except Exception as e:
        print(f"[step2] extraction error: {e}")
        new_data = {}
        had_error = True

    if not new_data:
        if current_group is None:
            return _continue_after_save(collected_fields)

        if had_error:
            config = FIELDS_CONFIG[current_group]
            # Получаем первый незаполненный ключ в текущей группе
            missing_key = _get_missing_key_in_group(collected_fields, current_group)
            key_prompts = config.get("key_prompts", {})

            if missing_key and missing_key in key_prompts:
                example = key_prompts[missing_key]
            else:
                example = config["instruction"]

            return StepResponse(
                answer=(
                    f"Не удалось обработать ваше сообщение — попробуйте ещё раз.\n\n"
                    f"{example}"
                ),
                step_completed=False,
                next_step=Step.STEP2,
                collected_fields=collected_fields,
            )

        return _continue_after_save(collected_fields)

    # ШАГ 4: разделяем поля
    to_save_directly: dict[str, object] = {}
    to_reformulate: dict[str, str] = {}

    for k, v in new_data.items():
        if v is None:
            continue
        if k in _FIELDS_NEEDING_REFORMULATION and isinstance(v, str) and v.strip():
            if not collected_fields.get(k):
                to_reformulate[k] = v
        else:
            to_save_directly[k] = v

    for k, v in to_save_directly.items():
        collected_fields[k] = v

    # ШАГ 5: реформулировка текстовых полей
    if to_reformulate:
        remaining_items = list(to_reformulate.items())
        while remaining_items:
            first_field, first_original = remaining_items.pop(0)
            remaining = dict(remaining_items)

            proposal = _build_pending_proposal(giga, first_field, first_original, remaining)

            if proposal is None:
                collected_fields[first_field] = first_original
                continue

            pending_state, answer_text = proposal
            collected_fields[_PENDING_KEY] = pending_state

            return StepResponse(
                answer=answer_text,
                step_completed=False,
                next_step=Step.STEP2,
                collected_fields=collected_fields,
            )

    # ШАГ 6: только структурные поля — продолжаем сбор
    return _continue_after_save(collected_fields)