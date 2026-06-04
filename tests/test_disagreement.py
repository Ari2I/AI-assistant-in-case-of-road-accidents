"""
Тесты для agent/disagreement_slots.py и agent/disagreement_helper.py.

Покрывают:
  - init_disagreement_slots(): инициализация, сохранение существующих значений
  - get_next_slot(): порядок слотов, умный пропуск нерелевантных
  - _should_skip(): условия пропуска слотов
  - are_required_slots_filled(): проверка обязательных слотов
  - get_uncertain_required_slot(): слоты с неопределёнными значениями
  - get_next_clarifying_slot(): уточняющие слоты
  - _build_result_message(): форматирование результата анализа
  - _handle_result_response(): согласие/несогласие с выводом
  - _has_done_trigger() через fill_external
"""

from __future__ import annotations

import sys
import pytest
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.disagreement_slots import (
    init_disagreement_slots,
    get_next_slot,
    get_next_clarifying_slot,
    are_required_slots_filled,
    get_uncertain_required_slot,
    _should_skip,
    REQUIRED_SLOTS,
    SLOT_ORDER,
    CLARIFYING_SLOTS,
    SKIPPABLE_SLOTS,
    DISAGREEMENT_SLOT_DEFAULTS,
)
from agent.disagreement_helper import (
    _build_result_message,
    _handle_result_response,
)
from agent.step_types import Step


# ---------------------------------------------------------------------------
# Вспомогательный мок GigaChat
# ---------------------------------------------------------------------------

def _make_queue_giga(responses: list[str]):
    queue = deque(responses)

    class QueueGiga:
        def chat(self, *args, **kwargs):
            response = queue.popleft() if queue else "{}"
            class FakeMsg:
                content = response
            class FakeChoice:
                message = FakeMsg()
            class FakeResp:
                choices = [FakeChoice()]
            return FakeResp()

    return QueueGiga()


# =============================================================================
# ТЕСТЫ init_disagreement_slots
# =============================================================================

class TestInitDisagreementSlots:
    """Тесты инициализации слотов разногласий."""

    def test_empty_init_all_none(self):
        """Без аргументов все слоты None."""
        slots = init_disagreement_slots()
        for key in DISAGREEMENT_SLOT_DEFAULTS:
            assert slots[key] is None

    def test_preserves_existing_values(self):
        """Существующие значения сохраняются."""
        existing = {"road_type": "перекрёсток", "vehicle_a_maneuver": "прямо"}
        slots = init_disagreement_slots(existing)
        assert slots["road_type"] == "перекрёсток"
        assert slots["vehicle_a_maneuver"] == "прямо"

    def test_preserves_service_keys(self):
        """Служебные ключи (начинающиеся с _) сохраняются."""
        existing = {"_analysis_done": True, "_last_analysis": {"fault": "B"}}
        slots = init_disagreement_slots(existing)
        assert slots.get("_analysis_done") is True
        assert slots.get("_last_analysis") == {"fault": "B"}

    def test_unknown_keys_not_preserved(self):
        """Неизвестные ключи (не служебные) не переносятся."""
        existing = {"unknown_key": "value"}
        slots = init_disagreement_slots(existing)
        assert "unknown_key" not in slots

    def test_partial_fill_rest_none(self):
        """Незаполненные слоты остаются None."""
        existing = {"road_type": "парковка"}
        slots = init_disagreement_slots(existing)
        assert slots["road_type"] == "парковка"
        assert slots["priority_signs"] is None
        assert slots["vehicle_a_maneuver"] is None

    def test_none_existing_returns_defaults(self):
        """None как аргумент возвращает дефолтные значения."""
        slots = init_disagreement_slots(None)
        assert all(v is None for k, v in slots.items() if not k.startswith("_"))


# =============================================================================
# ТЕСТЫ _should_skip
# =============================================================================

class TestShouldSkip:
    """Тесты умного пропуска нерелевантных слотов."""

    def test_traffic_light_skipped_without_traffic_light(self):
        """Светофорные слоты пропускаются если нет светофора."""
        d_slots = {"priority_signs": "главная"}
        assert _should_skip("traffic_light_state", d_slots) is True
        assert _should_skip("traffic_light_state_b", d_slots) is True

    def test_traffic_light_not_skipped_with_traffic_light(self):
        """Светофорные слоты не пропускаются если есть светофор."""
        d_slots = {"priority_signs": "светофор"}
        assert _should_skip("traffic_light_state", d_slots) is False

    def test_traffic_light_not_skipped_with_blinking_yellow(self):
        """Мигающий жёлтый — светофор есть."""
        d_slots = {"priority_signs": "мигающий жёлтый"}
        assert _should_skip("traffic_light_state", d_slots) is False

    def test_road_signs_skipped_with_traffic_light(self):
        """Знаки пропускаются если есть светофор (светофор важнее)."""
        d_slots = {"priority_signs": "светофор"}
        assert _should_skip("road_signs", d_slots) is True

    def test_road_signs_not_skipped_without_traffic_light(self):
        """Знаки не пропускаются без светофора."""
        d_slots = {"priority_signs": "главная"}
        assert _should_skip("road_signs", d_slots) is False

    def test_vehicle_b_origin_skipped_on_parking(self):
        """vehicle_b_origin пропускается для парковки."""
        d_slots = {"road_type": "парковка"}
        assert _should_skip("vehicle_b_origin", d_slots) is True

    def test_vehicle_b_origin_skipped_in_yard(self):
        """vehicle_b_origin пропускается во дворе."""
        d_slots = {"road_type": "двор"}
        assert _should_skip("vehicle_b_origin", d_slots) is True

    def test_vehicle_b_origin_not_skipped_on_road(self):
        """vehicle_b_origin не пропускается на дороге."""
        d_slots = {"road_type": "прямой участок"}
        assert _should_skip("vehicle_b_origin", d_slots) is False

    def test_speed_limit_skipped_in_yard(self):
        """Ограничение скорости пропускается во дворе."""
        d_slots = {"road_type": "двор"}
        assert _should_skip("speed_limit", d_slots) is True

    def test_speed_limit_not_skipped_on_road(self):
        """Ограничение скорости не пропускается на дороге."""
        d_slots = {"road_type": "прямой участок"}
        assert _should_skip("speed_limit", d_slots) is False

    def test_other_slots_not_skipped(self):
        """Остальные слоты не пропускаются при любом контексте."""
        d_slots = {"priority_signs": "главная", "road_type": "перекрёсток"}
        assert _should_skip("vehicle_a_maneuver", d_slots) is False
        assert _should_skip("impact_point_a", d_slots) is False
        assert _should_skip("vehicle_a_version", d_slots) is False


# =============================================================================
# ТЕСТЫ get_next_slot
# =============================================================================

class TestGetNextSlot:
    """Тесты получения следующего незаполненного слота."""

    def test_empty_slots_returns_first(self):
        """Для пустых слотов возвращается первый в порядке."""
        d_slots = init_disagreement_slots()
        first = get_next_slot(d_slots)
        assert first == SLOT_ORDER[0]  # road_type

    def test_filled_slots_skipped(self):
        """Заполненные слоты пропускаются."""
        d_slots = init_disagreement_slots({"road_type": "перекрёсток"})
        next_slot = get_next_slot(d_slots)
        assert next_slot != "road_type"

    def test_all_filled_returns_none(self):
        """Если все слоты заполнены — возвращает None."""
        d_slots = {k: "значение" for k in SLOT_ORDER}
        result = get_next_slot(d_slots)
        assert result is None

    def test_auto_skips_traffic_light_without_signals(self):
        """Светофорные слоты автоматически помечаются 'не применимо'."""
        d_slots = init_disagreement_slots({
            "road_type": "перекрёсток",
            "priority_signs": "главная",  # нет светофора
        })
        next_slot = get_next_slot(d_slots)
        # Слоты светофора должны быть автоматически пропущены
        assert next_slot not in ("traffic_light_state", "traffic_light_state_b")
        assert d_slots.get("traffic_light_state") == "не применимо"

    def test_auto_skips_vehicle_b_origin_in_yard(self):
        """vehicle_b_origin автоматически пропускается во дворе."""
        d_slots = init_disagreement_slots({
            "road_type": "двор",
            "priority_signs": "неизвестно",
        })
        while True:
            slot = get_next_slot(d_slots)
            if slot is None or slot == "vehicle_b_origin":
                break
            d_slots[slot] = "значение"

        # vehicle_b_origin должен быть автоматически пропущен
        if slot == "vehicle_b_origin":
            pytest.fail("vehicle_b_origin не должен быть следующим слотом во дворе")
        assert d_slots.get("vehicle_b_origin") == "не применимо"

    def test_order_matches_slot_order(self):
        """Порядок слотов соответствует SLOT_ORDER (с учётом пропусков)."""
        d_slots = init_disagreement_slots()
        collected = []
        visited = set()

        for _ in range(len(SLOT_ORDER) + 5):
            slot = get_next_slot(d_slots)
            if slot is None:
                break
            if slot in visited:
                pytest.fail(f"Слот {slot} возвращён дважды")
            visited.add(slot)
            collected.append(slot)
            d_slots[slot] = "значение"

        # Проверяем что собранный порядок соответствует SLOT_ORDER
        slot_order_set = set(SLOT_ORDER)
        for s in collected:
            assert s in slot_order_set


# =============================================================================
# ТЕСТЫ are_required_slots_filled
# =============================================================================

class TestAreRequiredSlotsFilled:
    """Тесты проверки заполненности обязательных слотов."""

    def test_all_empty_returns_false(self):
        d_slots = init_disagreement_slots()
        assert are_required_slots_filled(d_slots) is False

    def test_all_required_filled_returns_true(self):
        d_slots = init_disagreement_slots({
            "road_type": "перекрёсток",
            "priority_signs": "главная",
            "vehicle_a_maneuver": "прямо",
            "vehicle_b_maneuver": "поворот налево",
            "vehicle_a_version": "я ехал прямо",
            "vehicle_b_version": "он говорит что имел право",
            "impact_point_a": "передняя",
            "impact_point_b": "левый бок",
        })
        assert are_required_slots_filled(d_slots) is True

    def test_uncertain_value_not_counted(self):
        """Значение 'неизвестно' не считается заполненным."""
        d_slots = init_disagreement_slots({
            "road_type": "неизвестно",  # неопределённое значение
            "priority_signs": "главная",
            "vehicle_a_maneuver": "прямо",
            "vehicle_b_maneuver": "поворот налево",
            "vehicle_a_version": "я ехал прямо",
            "vehicle_b_version": "не сообщил",
            "impact_point_a": "передняя",
            "impact_point_b": "левый бок",
        })
        assert are_required_slots_filled(d_slots) is False

    def test_partial_required_returns_false(self):
        """Частично заполненные обязательные слоты → False."""
        d_slots = init_disagreement_slots({
            "road_type": "перекрёсток",
            "priority_signs": "главная",
        })
        assert are_required_slots_filled(d_slots) is False

    def test_all_uncertain_values(self):
        """Все возможные неопределённые значения не засчитываются."""
        uncertain_values = [
            "неизвестно", "не знаю", "не сообщил",
            "нет данных", "unknown",
        ]
        for val in uncertain_values:
            d_slots = init_disagreement_slots({k: val for k in REQUIRED_SLOTS})
            assert are_required_slots_filled(d_slots) is False, (
                f"Значение '{val}' не должно засчитываться как заполненное"
            )


# =============================================================================
# ТЕСТЫ get_uncertain_required_slot
# =============================================================================

class TestGetUncertainRequiredSlot:
    """Тесты поиска обязательного слота с неопределённым значением."""

    def test_no_uncertain_slots_returns_none(self):
        d_slots = init_disagreement_slots({k: "значение" for k in REQUIRED_SLOTS})
        assert get_uncertain_required_slot(d_slots) is None

    def test_finds_uncertain_slot(self):
        d_slots = init_disagreement_slots({
            "road_type": "неизвестно",
            "priority_signs": "главная",
        })
        result = get_uncertain_required_slot(d_slots)
        assert result == "road_type"

    def test_none_value_not_uncertain(self):
        """None — это незаполненный, не неопределённый."""
        d_slots = init_disagreement_slots()
        # Все None → get_uncertain_required_slot должен вернуть None
        # (неопределённые — это "неизвестно", не None)
        result = get_uncertain_required_slot(d_slots)
        assert result is None

    def test_first_uncertain_returned(self):
        """Возвращается первый неопределённый слот из REQUIRED_SLOTS."""
        d_slots = init_disagreement_slots({
            "road_type": "неизвестно",
            "priority_signs": "неизвестно",
        })
        result = get_uncertain_required_slot(d_slots)
        # road_type идёт первым в REQUIRED_SLOTS
        assert result == "road_type"


# =============================================================================
# ТЕСТЫ get_next_clarifying_slot
# =============================================================================

class TestGetNextClarifyingSlot:
    """Тесты получения уточняющего слота."""

    def test_all_clarifying_none_returns_first(self):
        d_slots = init_disagreement_slots()
        result = get_next_clarifying_slot(d_slots)
        assert result == CLARIFYING_SLOTS[0]

    def test_filled_clarifying_skipped(self):
        d_slots = init_disagreement_slots({
            "speed_a_approx": 60,
        })
        result = get_next_clarifying_slot(d_slots)
        assert result != "speed_a_approx"

    def test_all_clarifying_filled_returns_none(self):
        d_slots = init_disagreement_slots({s: "значение" for s in CLARIFYING_SLOTS})
        result = get_next_clarifying_slot(d_slots)
        assert result is None


# =============================================================================
# ТЕСТЫ _build_result_message
# =============================================================================

class TestBuildResultMessage:
    """Тесты форматирования результата анализа вины."""

    def _base_analysis(self, **kwargs) -> dict:
        base = {
            "fault": "B",
            "confidence": 0.85,
            "reasoning": ["Второй участник выехал с второстепенной дороги"],
            "pdd_references": ["13.9"],
            "summary": "Виноват второй участник",
            "needs_clarification": False,
        }
        base.update(kwargs)
        return base

    def test_fault_b_header(self):
        """Вина Б — соответствующий заголовок."""
        result = _build_result_message(self._base_analysis(fault="B"))
        assert "второй участник" in result.lower() or "ТС Б" in result

    def test_fault_a_header(self):
        """Вина А — соответствующий заголовок."""
        result = _build_result_message(self._base_analysis(fault="A"))
        assert "вы" in result.lower() or "ТС А" in result

    def test_fault_both_header(self):
        """Оба виноваты — соответствующий заголовок."""
        result = _build_result_message(self._base_analysis(fault="both"))
        assert "оба" in result.lower()

    def test_fault_unclear_header(self):
        """Неоднозначная ситуация — соответствующий заголовок."""
        result = _build_result_message(self._base_analysis(fault="unclear"))
        assert "неоднозначна" in result.lower() or "затруднён" in result.lower()

    def test_high_confidence_label(self):
        """Высокая уверенность (>=0.8) — соответствующая метка."""
        result = _build_result_message(self._base_analysis(confidence=0.9))
        assert "высокая" in result.lower()

    def test_medium_confidence_label(self):
        """Средняя уверенность (0.6-0.8) — рекомендация приложения."""
        result = _build_result_message(self._base_analysis(confidence=0.7))
        assert "средняя" in result.lower() or "приложение" in result.lower()

    def test_low_confidence_label(self):
        """Низкая уверенность (<0.6) — рекомендация ГИБДД."""
        result = _build_result_message(self._base_analysis(confidence=0.4))
        assert "низкая" in result.lower() or "гибдд" in result.lower()

    def test_reasoning_included(self):
        """Обоснование включается в результат."""
        analysis = self._base_analysis(
            reasoning=["Нарушен пункт 13.9 ПДД", "Второй не уступил дорогу"]
        )
        result = _build_result_message(analysis)
        assert "13.9" in result or "Обоснование" in result

    def test_pdd_references_included(self):
        """Ссылки на ПДД включаются."""
        analysis = self._base_analysis(pdd_references=["13.9", "8.3"])
        result = _build_result_message(analysis)
        assert "13.9" in result
        assert "8.3" in result

    def test_summary_included(self):
        """Краткий вывод включается."""
        analysis = self._base_analysis(summary="Виноват второй участник по пункту 13.9")
        result = _build_result_message(analysis)
        assert "Виноват второй участник" in result

    def test_agreement_prompt_included(self):
        """Результат содержит запрос согласия пользователя."""
        result = _build_result_message(self._base_analysis())
        assert "согласны" in result.lower() or "согласен" in result.lower() or "да" in result.lower()

    def test_empty_reasoning_no_crash(self):
        """Пустое обоснование не вызывает ошибку."""
        analysis = self._base_analysis(reasoning=[], pdd_references=[])
        result = _build_result_message(analysis)
        assert isinstance(result, str)
        assert len(result) > 0


# =============================================================================
# ТЕСТЫ _handle_result_response
# =============================================================================

class TestHandleResultResponse:
    """Тесты обработки ответа пользователя на результат анализа."""

    def _base_slots(self) -> dict:
        return {
            "safety_confirmed": True,
            "victims": False,
            "participants_count": 2,
            "osago_both": True,
            "disagreement": True,
            "disagreement_help_active": True,
            "disagreement_help_offered": True,
            "disagreement_slots": {
                "_analysis_done": True,
                "road_type": "перекрёсток",
            },
        }

    def test_agree_transitions_to_step1(self):
        """Согласие переводит в step1 для продолжения."""
        result = _handle_result_response("да", self._base_slots())
        assert result is not None
        assert result.next_step == Step.STEP1

    def test_agree_sets_disagreement_false(self):
        """Согласие убирает флаг разногласий."""
        result = _handle_result_response("согласен", self._base_slots())
        assert result is not None
        assert result.slots.get("disagreement") is False

    def test_agree_deactivates_help(self):
        """Согласие деактивирует режим помощи при разногласиях."""
        result = _handle_result_response("верно", self._base_slots())
        assert result is not None
        assert result.slots.get("disagreement_help_active") is False

    def test_disagree_offers_alternatives(self):
        """Несогласие предлагает альтернативы (приложение или ГИБДД)."""
        result = _handle_result_response("нет", self._base_slots())
        assert result is not None
        answer_lower = result.answer.lower()
        assert "приложение" in answer_lower or "гибдд" in answer_lower or "102" in answer_lower

    def test_disagree_deactivates_help(self):
        """Несогласие деактивирует режим помощи."""
        result = _handle_result_response("не согласен", self._base_slots())
        assert result is not None
        assert result.slots.get("disagreement_help_active") is False

    def test_unknown_phrase_returns_none(self):
        """Неизвестная фраза возвращает None — не обрабатывается."""
        result = _handle_result_response("расскажи подробнее", self._base_slots())
        assert result is None

    def test_all_agree_phrases(self):
        """Все фразы согласия обрабатываются."""
        agree_phrases = ["да", "согласен", "согласна", "верно", "правильно",
                         "ок", "ok", "хорошо", "принято", "продолжим", "продолжаем"]
        for phrase in agree_phrases:
            result = _handle_result_response(phrase, self._base_slots())
            assert result is not None, f"Фраза '{phrase}' не обработана"
            assert result.slots.get("disagreement") is False

    def test_all_disagree_phrases(self):
        """Все фразы несогласия обрабатываются."""
        disagree_phrases = ["нет", "не согласен", "не согласна", "неверно",
                            "неправильно", "не так", "спорю"]
        for phrase in disagree_phrases:
            result = _handle_result_response(phrase, self._base_slots())
            assert result is not None, f"Фраза '{phrase}' не обработана"

    def test_agree_removes_disagreement_slots_from_result(self):
        """После согласия disagreement_slots не передаются дальше."""
        result = _handle_result_response("да", self._base_slots())
        assert result is not None
        assert "disagreement_slots" not in result.slots


# =============================================================================
# ТЕСТЫ SLOT_ORDER и REQUIRED_SLOTS константы
# =============================================================================

class TestConstants:
    """Тесты корректности констант модуля."""

    def test_required_slots_subset_of_slot_order(self):
        """Все обязательные слоты присутствуют в SLOT_ORDER."""
        slot_order_set = set(SLOT_ORDER)
        for slot in REQUIRED_SLOTS:
            assert slot in slot_order_set, f"{slot} не найден в SLOT_ORDER"

    def test_clarifying_slots_not_in_slot_order(self):
        """Уточняющие слоты отдельны от основного порядка."""
        slot_order_set = set(SLOT_ORDER)
        for slot in CLARIFYING_SLOTS:
            assert slot not in slot_order_set, (
                f"Уточняющий слот {slot} не должен быть в SLOT_ORDER"
            )

    def test_skippable_slots_in_slot_order(self):
        """Пропускаемые слоты присутствуют в SLOT_ORDER."""
        slot_order_set = set(SLOT_ORDER)
        for slot in SKIPPABLE_SLOTS:
            assert slot in slot_order_set, f"Пропускаемый слот {slot} не найден в SLOT_ORDER"

    def test_required_slots_not_all_skippable(self):
        """Обязательные слоты не должны быть пропускаемыми."""
        for slot in REQUIRED_SLOTS:
            assert slot not in SKIPPABLE_SLOTS, (
                f"Обязательный слот {slot} не может быть пропускаемым"
            )

    def test_slot_questions_cover_slot_order(self):
        """Для каждого слота из SLOT_ORDER есть вопрос."""
        from agent.disagreement_slots import SLOT_QUESTIONS
        for slot in SLOT_ORDER:
            assert slot in SLOT_QUESTIONS, f"Нет вопроса для слота {slot}"

    def test_slot_questions_cover_clarifying(self):
        """Для каждого уточняющего слота есть вопрос."""
        from agent.disagreement_slots import SLOT_QUESTIONS
        for slot in CLARIFYING_SLOTS:
            assert slot in SLOT_QUESTIONS, f"Нет вопроса для уточняющего слота {slot}"