"""
Константы и вспомогательные функции для структурированного
анализа разногласий при ДТП. Версия 1.2.

Изменения v1.2:
  - Добавлены слоты: impact_point_a, impact_point_b (место удара)
  - Добавлены слоты: speed_limit, road_signs (инфраструктура)
  - Добавлен слот:   vehicle_b_origin (откуда появился второй участник)
  - Добавлены слоты: has_dashcam_a, has_dashcam_b (доказательная база)
  - Умный пропуск слотов: road_signs/speed_limit/vehicle_b_origin
    задаются только когда релевантны ситуации
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Структура слотов
# ---------------------------------------------------------------------------

DISAGREEMENT_SLOT_DEFAULTS: dict = {
    # Место и инфраструктура
    "road_type": None,
    "priority_signs": None,
    "road_signs": None,           # знаки на дороге: уступи, стоп, главная дорога
    "speed_limit": None,          # ограничение скорости на участке
    "traffic_light_state": None,  # сигнал светофора для ТС А
    "traffic_light_state_b": None,# сигнал светофора для ТС Б
    "road_markings": None,
    "road_condition": None,

    # Манёвры и позиции
    "vehicle_a_maneuver": None,
    "vehicle_b_maneuver": None,
    "vehicle_b_origin": None,     # откуда появился ТС Б: двор, парковка, дорога
    "impact_point_a": None,       # место удара на ТС А: перед/бок/зад
    "impact_point_b": None,       # место удара на ТС Б: перед/бок/зад

    # Версии участников
    "vehicle_a_version": None,
    "vehicle_b_version": None,

    # Уточняющие
    "speed_a_approx": None,
    "speed_b_approx": None,
    "visibility": None,

    # Доказательная база
    "has_dashcam_a": None,        # есть ли регистратор у ТС А
    "has_dashcam_b": None,        # есть ли регистратор у ТС Б
}

# Ключевые поля — без них анализ не запускается
REQUIRED_SLOTS: list[str] = [
    "road_type",
    "priority_signs",
    "vehicle_a_maneuver",
    "vehicle_b_maneuver",
    "vehicle_a_version",
    "vehicle_b_version",
    "impact_point_a",
    "impact_point_b",
]

# Основной порядок опроса
SLOT_ORDER: list[str] = [
    "road_type",
    "priority_signs",
    "road_signs",
    "traffic_light_state",
    "traffic_light_state_b",
    "vehicle_b_origin",
    "vehicle_a_maneuver",
    "vehicle_b_maneuver",
    "impact_point_a",
    "impact_point_b",
    "vehicle_a_version",
    "vehicle_b_version",
    "speed_limit",
    "road_markings",
    "road_condition",
    "has_dashcam_a",
    "has_dashcam_b",
]

# Уточняющие поля — запрашиваются только при низкой уверенности
CLARIFYING_SLOTS: list[str] = [
    "speed_a_approx",
    "speed_b_approx",
    "visibility",
]

# ---------------------------------------------------------------------------
# Вопросы для каждого слота
# ---------------------------------------------------------------------------

SLOT_QUESTIONS: dict[str, str] = {
    "road_type": (
        "Где именно произошло столкновение?\n"
        "Варианты: перекрёсток / прямой участок дороги / парковка / двор / другое"
    ),
    "priority_signs": (
        "Кто имел приоритет на этом участке?\n"
        "Варианты: я ехал по главной дороге / я ехал по второстепенной / "
        "дороги равнозначные / был светофор / мигающий жёлтый / не знаю"
    ),
    "road_signs": (
        "Были ли дорожные знаки в месте ДТП?\n"
        "Варианты: знак «Уступи дорогу» / знак «Стоп» / знак «Главная дорога» / "
        "знака не было / не заметил"
    ),
    "speed_limit": (
        "Какое ограничение скорости действовало на этом участке?\n"
        "Укажите цифру (например: 40, 60, 90) или напишите «не знаю»."
    ),
    "traffic_light_state": (
        "Какой сигнал светофора был для вас в момент столкновения?\n"
        "Варианты: зелёный / жёлтый мигающий / красный / светофора не было"
    ),
    "traffic_light_state_b": (
        "Какой сигнал светофора был для второго участника в момент столкновения?\n"
        "Варианты: зелёный / жёлтый мигающий / красный / не знаю"
    ),
    "vehicle_b_origin": (
        "Откуда появился второй участник непосредственно перед столкновением?\n"
        "Варианты: ехал по дороге / выезжал со двора / выезжал с парковки / "
        "выезжал с прилегающей территории / выезжал с второстепенной дороги"
    ),
    "vehicle_a_maneuver": (
        "Что делали вы в момент столкновения?\n"
        "Варианты: ехал прямо / поворачивал налево / поворачивал направо / "
        "разворачивался / перестраивался / двигался задним ходом / стоял"
    ),
    "vehicle_b_maneuver": (
        "Что делал второй участник в момент столкновения?\n"
        "Варианты: ехал прямо / поворачивал налево / поворачивал направо / "
        "разворачивался / перестраивался / двигался задним ходом / стоял / "
        "начинал движение"
    ),
    "impact_point_a": (
        "Какая часть вашего автомобиля получила основной удар?\n"
        "Варианты: передняя / передняя левая / передняя правая / "
        "левый бок / правый бок / задняя / задняя левая / задняя правая"
    ),
    "impact_point_b": (
        "Какая часть автомобиля второго участника получила основной удар?\n"
        "Варианты: передняя / передняя левая / передняя правая / "
        "левый бок / правый бок / задняя / задняя левая / задняя правая"
    ),
    "vehicle_a_version": (
        "Опишите своими словами, как произошло столкновение с вашей точки зрения."
    ),
    "vehicle_b_version": (
        "Как второй участник объясняет произошедшее? "
        "Если он ничего не сказал — напишите «не сообщил»."
    ),
    "road_markings": (
        "Какая разметка была на дороге в месте столкновения?\n"
        "Варианты: сплошная линия / прерывистая / пешеходный переход / "
        "стоп-линия / разметки не было / не заметил"
    ),
    "road_condition": (
        "Какое было состояние дороги?\n"
        "Варианты: сухая / мокрая / лёд / снег / другое"
    ),
    "speed_a_approx": (
        "Примерно с какой скоростью вы двигались в момент столкновения? "
        "Укажите цифру в км/ч или напишите «стоял»."
    ),
    "speed_b_approx": (
        "Примерно с какой скоростью двигался второй участник? "
        "Укажите цифру в км/ч или напишите «не знаю»."
    ),
    "visibility": (
        "Какова была видимость в момент ДТП?\n"
        "Варианты: хорошая / ограниченная (туман, дождь) / плохая (ночь, гололёд)"
    ),
    "has_dashcam_a": (
        "У вас есть видеорегистратор, который зафиксировал момент ДТП?\n"
        "Варианты: да / нет / не знаю"
    ),
    "has_dashcam_b": (
        "У второго участника есть видеорегистратор?\n"
        "Варианты: да / нет / не знаю"
    ),
}

# Слоты которые можно пропустить если пользователь не знает
SKIPPABLE_SLOTS: frozenset[str] = frozenset({
    "road_signs",
    "speed_limit",
    "traffic_light_state",
    "traffic_light_state_b",
    "vehicle_b_origin",
    "road_markings",
    "road_condition",
    "speed_a_approx",
    "speed_b_approx",
    "visibility",
    "has_dashcam_b",
})

# ---------------------------------------------------------------------------
# Условия умного пропуска слотов
# ---------------------------------------------------------------------------

def _should_skip(slot: str, d_slots: dict) -> bool:
    """
    Возвращает True если слот нерелевантен текущей ситуации
    и должен быть автоматически помечен как "не применимо".
    """
    priority = str(d_slots.get("priority_signs") or "").lower()
    road_type = str(d_slots.get("road_type") or "").lower()
    has_tl = (
        "светофор" in priority
        or "мигающий" in priority
        or d_slots.get("traffic_light_state") not in (None, "не применимо", "светофора не было")
    )

    # Светофорные слоты — только если есть светофор
    if slot in ("traffic_light_state", "traffic_light_state_b"):
        return not has_tl and priority != ""

    # Знаки дороги — пропускаем если уже есть светофор (светофор важнее знаков)
    if slot == "road_signs":
        return has_tl

    # Откуда появился второй участник — только если тип места неочевиден
    if slot == "vehicle_b_origin":
        return road_type in ("парковка", "двор")

    # Ограничение скорости — пропускаем при ДТП во дворе/парковке
    if slot == "speed_limit":
        return road_type in ("парковка", "двор")

    return False


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def init_disagreement_slots(existing: dict | None = None) -> dict:
    """Инициализирует слоты разногласий."""
    result = dict(DISAGREEMENT_SLOT_DEFAULTS)
    if existing:
        for k in result:
            if k in existing:
                result[k] = existing[k]
        for k, v in existing.items():
            if k.startswith("_"):
                result[k] = v
    return result


def get_next_slot(d_slots: dict) -> str | None:
    """
    Возвращает следующий незаполненный слот из основного порядка.
    Автоматически пропускает нерелевантные слоты.
    None если все основные слоты заполнены.
    """
    for slot in SLOT_ORDER:
        if d_slots.get(slot) is not None:
            continue
        if _should_skip(slot, d_slots):
            d_slots[slot] = "не применимо"
            continue
        return slot
    return None


def get_next_clarifying_slot(d_slots: dict) -> str | None:
    """Возвращает следующий незаполненный уточняющий слот."""
    for slot in CLARIFYING_SLOTS:
        if d_slots.get(slot) is None:
            return slot
    return None


# Значения которые НЕ считаются заполненными для обязательных слотов
_UNCERTAIN_VALUES: frozenset[str] = frozenset({
    "неизвестно", "не знаю", "не сообщил", "нет данных", "unknown",
})


def are_required_slots_filled(d_slots: dict) -> bool:
    """
    Проверяет что все обязательные слоты заполнены осмысленными данными.
    Значения типа "неизвестно" для обязательных слотов не засчитываются —
    агент должен задать уточняющий вопрос.
    """
    for slot in REQUIRED_SLOTS:
        val = d_slots.get(slot)
        if val is None:
            return False
        if isinstance(val, str) and val.strip().lower() in _UNCERTAIN_VALUES:
            return False
    return True


def get_uncertain_required_slot(d_slots: dict) -> str | None:
    """
    Возвращает первый обязательный слот с неопределённым значением.
    Используется чтобы задать уточняющий вопрос вместо запуска анализа.
    """
    for slot in REQUIRED_SLOTS:
        val = d_slots.get(slot)
        if val is not None and isinstance(val, str):
            if val.strip().lower() in _UNCERTAIN_VALUES:
                return slot
    return None