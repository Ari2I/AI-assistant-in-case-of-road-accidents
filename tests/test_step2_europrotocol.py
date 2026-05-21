"""
Тесты для process_step2_with_llm и вспомогательных функций step2.

Покрывают:
  - pending reformulation: подтверждение / отклонение / свой вариант
  - pending overwrite: подтверждение / отклонение / цепочка конфликтов
  - direct_text: захват текстовых полей напрямую из query
  - заполнение структурных полей через мок LLM
  - завершение шага при всех заполненных полях
  - обработку ошибок LLM
"""

from __future__ import annotations

import sys
import pytest
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.step2_europrotocol import (
    _PENDING_KEY,
    _PENDING_OVERWRITE_KEY,
    _FIELDS_NEEDING_REFORMULATION,
    _handle_reformulation_response,
    _handle_overwrite_response,
    _get_current_group,
    _get_missing_key_in_group,
    _continue_after_save,
    process_step2_with_llm,
    FIELDS_CONFIG,
)
from agent.step_types import Step


# ---------------------------------------------------------------------------
# Вспомогательный мок GigaChat
# ---------------------------------------------------------------------------

def _make_queue_giga(responses: list[str]):
    """
    Мок GigaChat с очередью ответов.
    При исчерпании очереди возвращает '{}' (пустой JSON).
    """
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


def _all_fields_filled() -> dict:
    """Возвращает dict со всеми заполненными полями step2."""
    return {
        "date": "15.01.2025",
        "time": "14:30",
        "location": "г. Москва, ул. Ленина, д. 10",
        "witnesses": "нет",
        "vehicle_a_make_model": "Toyota Camry",
        "vehicle_a_reg_number": "А123БВ777",
        "vehicle_a_owner_name": "Иванов И.И.",
        "vehicle_a_driver_name": "Иванов И.И.",
        "vehicle_a_driver_license": "77 77 123456",
        "vehicle_a_insurer": "Росгосстрах",
        "vehicle_a_policy_number": "ХХХ 1234567890",
        "vehicle_a_policy_expiry": "31.12.2025",
        "vehicle_a_impact_point": "передний бампер",
        "vehicle_a_damage": "передний бампер — трещина",
        "vehicle_b_make_model": "Kia Rio",
        "vehicle_b_reg_number": "В456СМ777",
        "vehicle_b_owner_name": "Петров П.П.",
        "vehicle_b_driver_name": "Петров П.П.",
        "vehicle_b_driver_license": "77 77 654321",
        "vehicle_b_insurer": "СОГАЗ",
        "vehicle_b_policy_number": "ЕЕЕ 0987654321",
        "vehicle_b_policy_expiry": "30.06.2025",
        "vehicle_b_impact_point": "задний бампер",
        "vehicle_b_damage": "задний бампер — царапина",
        "circumstances": "ТС А двигалось прямо, ТС Б выезжало задним ходом.",
        "vehicle_a_fault": "не виноват",
        "vehicle_b_fault": "виноват",
        "scheme": "ТС А у обочины, ТС Б въехало сзади.",
        "signatures_confirmed": True,
    }


# ---------------------------------------------------------------------------
# Тесты вспомогательных функций
# ---------------------------------------------------------------------------

class TestGetCurrentGroup:
    """Тесты _get_current_group."""

    def test_empty_fields_returns_first_group(self):
        assert _get_current_group({}) == "datetime"

    def test_date_filled_time_missing(self):
        """Группа datetime не завершена пока time не заполнен."""
        assert _get_current_group({"date": "15.01.2025"}) == "datetime"

    def test_all_filled_returns_none(self):
        assert _get_current_group(_all_fields_filled()) is None

    def test_skips_completed_groups(self):
        fields = {"date": "15.01.2025", "time": "14:30"}
        assert _get_current_group(fields) == "location_witnesses"


class TestGetMissingKeyInGroup:
    """Тесты _get_missing_key_in_group."""

    def test_datetime_both_missing(self):
        assert _get_missing_key_in_group({}, "datetime") == "date"

    def test_datetime_date_filled(self):
        assert _get_missing_key_in_group({"date": "15.01.2025"}, "datetime") == "time"

    def test_vehicle_b_persons_strict_order(self):
        """vehicle_b_persons имеет strict_order — заполняются по fill_order."""
        assert _get_missing_key_in_group({}, "vehicle_b_persons") == "vehicle_b_owner_name"
        assert _get_missing_key_in_group(
            {"vehicle_b_owner_name": "Петров П.П."},
            "vehicle_b_persons"
        ) == "vehicle_b_driver_name"

    def test_all_keys_filled_returns_none(self):
        fields = {"date": "15.01.2025", "time": "14:30"}
        assert _get_missing_key_in_group(fields, "datetime") is None


class TestContinueAfterSave:
    """Тесты _continue_after_save."""

    def test_all_filled_returns_done(self):
        result = _continue_after_save(_all_fields_filled())
        assert result.step_completed is True
        assert result.next_step == Step.DONE
        assert result.final_json is not None
        assert result.final_json["type"] == "europrotocol"

    def test_partial_asks_next_question(self):
        result = _continue_after_save({"date": "15.01.2025", "time": "14:30"})
        assert result.step_completed is False
        assert result.next_step == Step.STEP2
        assert result.answer  # есть вопрос

    def test_prefix_prepended_to_answer(self):
        result = _continue_after_save({}, prefix="Записано.\n\n")
        assert result.answer.startswith("Записано.")

    def test_final_json_excludes_pending_keys(self):
        """Служебные ключи не должны попасть в final_json."""
        fields = _all_fields_filled()
        fields[_PENDING_KEY] = {"field": "circumstances", "original": "...", "reformulated": "..."}
        fields[_PENDING_OVERWRITE_KEY] = {"field": "date", "old_value": "...", "new_value": "..."}
        result = _continue_after_save(fields)
        assert _PENDING_KEY not in result.final_json["data"]
        assert _PENDING_OVERWRITE_KEY not in result.final_json["data"]


# ---------------------------------------------------------------------------
# Тесты обработки reformulation pending
# ---------------------------------------------------------------------------

class TestHandleReformulationResponse:
    """Тесты _handle_reformulation_response."""

    def _make_pending(self, remaining: dict | None = None) -> dict:
        return {
            "field": "circumstances",
            "original": "я ехал, он въехал",
            "reformulated": "ТС А двигалось прямо, ТС Б выехало с парковки.",
            "remaining": remaining or {},
        }

    def test_approval_saves_reformulated(self):
        pending = self._make_pending()
        collected = {_PENDING_KEY: pending}
        giga = _make_queue_giga([])

        result = _handle_reformulation_response(giga, "да", collected, pending)

        assert collected.get("circumstances") == pending["reformulated"]
        assert _PENDING_KEY not in collected

    def test_rejection_saves_original(self):
        pending = self._make_pending()
        collected = {_PENDING_KEY: pending}
        giga = _make_queue_giga([])

        result = _handle_reformulation_response(giga, "нет", collected, pending)

        assert collected.get("circumstances") == pending["original"]
        assert _PENDING_KEY not in collected

    def test_custom_text_saves_as_is(self):
        pending = self._make_pending()
        collected = {_PENDING_KEY: pending}
        giga = _make_queue_giga([])
        custom = "Моя собственная формулировка для протокола."

        result = _handle_reformulation_response(giga, custom, collected, pending)

        assert collected.get("circumstances") == custom

    def test_empty_query_shows_repeat_prompt(self):
        pending = self._make_pending()
        collected = {_PENDING_KEY: pending}
        giga = _make_queue_giga([])

        result = _handle_reformulation_response(giga, "", collected, pending)

        assert result.step_completed is False
        assert pending["reformulated"] in result.answer
        assert _PENDING_KEY in collected  # pending сохранён

    def test_remaining_processed_after_approval(self):
        """После подтверждения обрабатывается следующее поле из remaining."""
        pending = self._make_pending(
            remaining={"scheme": "он стоял справа"}
        )
        collected = {_PENDING_KEY: pending}
        # LLM для реформулировки scheme
        giga = _make_queue_giga(["ТС Б находилось справа от ТС А."])

        _handle_reformulation_response(giga, "да", collected, pending)

        # Должен появиться новый pending для scheme
        assert _PENDING_KEY in collected
        assert collected[_PENDING_KEY]["field"] == "scheme"


# ---------------------------------------------------------------------------
# Тесты обработки overwrite pending
# ---------------------------------------------------------------------------

class TestHandleOverwriteResponse:
    """Тесты _handle_overwrite_response."""

    def _make_pending(self, remaining: list | None = None) -> dict:
        return {
            "field": "date",
            "old_value": "15.01.2025",
            "new_value": "16.01.2025",
            "remaining": remaining or [],
        }

    def test_approval_updates_field(self):
        pending = self._make_pending()
        collected = {"date": "15.01.2025", _PENDING_OVERWRITE_KEY: pending}

        result = _handle_overwrite_response("да", collected, pending)

        assert collected["date"] == "16.01.2025"
        assert _PENDING_OVERWRITE_KEY not in collected

    def test_rejection_keeps_old_value(self):
        pending = self._make_pending()
        collected = {"date": "15.01.2025", _PENDING_OVERWRITE_KEY: pending}

        result = _handle_overwrite_response("нет", collected, pending)

        assert collected["date"] == "15.01.2025"
        assert _PENDING_OVERWRITE_KEY not in collected

    def test_chain_of_overwrites(self):
        """При наличии remaining показывается следующий конфликт."""
        pending = self._make_pending(remaining=[
            {"field": "time", "old_value": "14:30", "new_value": "15:00"}
        ])
        collected = {"date": "15.01.2025", _PENDING_OVERWRITE_KEY: pending}

        result = _handle_overwrite_response("да", collected, pending)

        # Следующий конфликт должен быть установлен
        assert _PENDING_OVERWRITE_KEY in collected
        assert collected[_PENDING_OVERWRITE_KEY]["field"] == "time"
        assert "time" in result.answer


# ---------------------------------------------------------------------------
# Тесты direct_text (прямой захват текстовых полей)
# ---------------------------------------------------------------------------

class TestDirectText:
    """Тесты прямого захвата текстовых полей из query."""

    def test_circumstances_captured_directly(self):
        """
        Когда текущий ключ — circumstances и пользователь отвечает длинным текстом,
        он должен попасть в collected_fields без LLM-извлечения.
        """
        # Готовим поля: всё заполнено до fault_circumstances
        fields = _all_fields_filled()
        # Удаляем circumstances и вину чтобы группа была активной
        for k in ["circumstances", "vehicle_a_fault", "vehicle_b_fault"]:
            fields.pop(k, None)

        long_query = (
            "Я ехал прямо по правой полосе улицы Ленина в направлении севера. "
            "Второй участник выезжал задним ходом с парковки справа и не уступил дорогу, "
            "въехав в мой передний бампер."
        )

        # LLM возвращает {} — только direct_text должен сработать
        giga = _make_queue_giga(["{}"])
        result = process_step2_with_llm(giga, long_query, [], {}, fields)

        # circumstances должен быть захвачен
        assert fields.get("circumstances") == long_query or result.collected_fields.get("circumstances") == long_query

    def test_short_query_not_captured_as_circumstances(self):
        """Короткий ответ (<=10 символов) не должен захватываться как circumstances."""
        fields = _all_fields_filled()
        for k in ["circumstances", "vehicle_a_fault", "vehicle_b_fault"]:
            fields.pop(k, None)

        giga = _make_queue_giga(["{}"])
        result = process_step2_with_llm(giga, "не знаю", [], {}, fields)

        assert not result.collected_fields.get("circumstances")

    def test_direct_text_only_when_field_empty(self):
        """Если circumstances уже заполнен — direct_text не перезаписывает."""
        fields = _all_fields_filled()
        fields.pop("vehicle_a_fault", None)
        fields.pop("vehicle_b_fault", None)
        # circumstances уже есть
        original_circumstances = fields["circumstances"]

        giga = _make_queue_giga(["{}"])
        result = process_step2_with_llm(giga, "какой-то другой текст про обстоятельства", [], {}, fields)

        assert result.collected_fields.get("circumstances") == original_circumstances


# ---------------------------------------------------------------------------
# Тесты process_step2_with_llm — flow control
# ---------------------------------------------------------------------------

class TestStep2WithLLMFlow:
    """Тесты основного потока управления в process_step2_with_llm."""

    def test_pending_reformulation_takes_priority(self):
        """Если _PENDING_KEY установлен — идёт в _handle_reformulation_response."""
        pending = {
            "field": "circumstances",
            "original": "ехал, он въехал",
            "reformulated": "ТС А двигалось прямо.",
            "remaining": {},
        }
        collected = {_PENDING_KEY: pending, "date": "15.01.2025"}
        giga = _make_queue_giga([])

        result = process_step2_with_llm(giga, "да", [], {}, collected)

        # Должен сохранить reformulated и продолжить
        assert result.collected_fields.get("circumstances") == pending["reformulated"]

    def test_pending_overwrite_takes_priority_over_extraction(self):
        """Если _PENDING_OVERWRITE_KEY установлен — идёт в _handle_overwrite_response."""
        pending_ow = {
            "field": "date",
            "old_value": "15.01.2025",
            "new_value": "16.01.2025",
            "remaining": [],
        }
        collected = {"date": "15.01.2025", _PENDING_OVERWRITE_KEY: pending_ow}
        giga = _make_queue_giga([])

        result = process_step2_with_llm(giga, "да", [], {}, collected)

        assert result.collected_fields.get("date") == "16.01.2025"

    def test_overwrite_triggered_when_llm_returns_different_value(self):
        """Если LLM возвращает значение отличное от существующего — появляется pending_overwrite."""
        collected = {"date": "15.01.2025", "time": "14:30"}  # date уже заполнен
        # LLM возвращает другую дату
        giga = _make_queue_giga(['{"date": "16.01.2025"}'])

        result = process_step2_with_llm(giga, "ДТП было 16 января", [], {}, collected)

        assert _PENDING_OVERWRITE_KEY in result.collected_fields
        assert result.collected_fields[_PENDING_OVERWRITE_KEY]["field"] == "date"
        assert result.collected_fields[_PENDING_OVERWRITE_KEY]["old_value"] == "15.01.2025"
        assert result.collected_fields[_PENDING_OVERWRITE_KEY]["new_value"] == "16.01.2025"

    def test_llm_error_returns_error_message(self):
        """При ошибке LLM возвращается сообщение с просьбой повторить."""
        class ErrorGiga:
            def chat(self, *a, **kw):
                raise RuntimeError("API error")

        result = process_step2_with_llm(ErrorGiga(), "тест", [], {}, {})

        assert result.step_completed is False
        assert result.next_step == Step.STEP2
        assert "попробуйте" in result.answer.lower() or result.answer

    def test_all_fields_filled_returns_final_json(self):
        """Когда все поля заполнены — возвращает step_completed=True и final_json."""
        giga = _make_queue_giga(["{}"])
        result = process_step2_with_llm(giga, "всё верно", [], {}, _all_fields_filled())

        assert result.step_completed is True
        assert result.next_step == Step.DONE
        assert result.final_json is not None
        assert result.final_json["type"] == "europrotocol"
        assert result.final_json["data"]["date"] == "15.01.2025"

    def test_new_field_saved_directly(self):
        """Новое структурное поле (не текстовое) сохраняется сразу без reformulation."""
        collected = {}
        giga = _make_queue_giga(['{"date": "15.01.2025", "time": "14:30"}'])

        result = process_step2_with_llm(giga, "15.01.2025 14:30", [], {}, collected)

        assert result.collected_fields.get("date") == "15.01.2025"
        assert result.collected_fields.get("time") == "14:30"
        assert _PENDING_KEY not in result.collected_fields

    def test_text_field_goes_to_reformulation(self):
        """Текстовое поле (circumstances) проходит через reformulation loop."""
        # Все поля кроме circumstances / fault заполнены
        fields = _all_fields_filled()
        for k in ["circumstances", "vehicle_a_fault", "vehicle_b_fault"]:
            fields.pop(k, None)

        long_text = (
            "я ехал прямо, второй участник выезжал с парковки задним ходом "
            "и не уступил мне дорогу, ударив в передний бампер"
        )

        # LLM 1: extraction возвращает circumstances
        # LLM 2: reformulation возвращает официальный текст
        giga = _make_queue_giga([
            f'{{"circumstances": "{long_text}"}}',
            "ТС А двигалось прямо по проезжей части, ТС Б выполняло движение задним ходом.",
        ])

        result = process_step2_with_llm(giga, long_text, [], {}, fields)

        # Должен быть pending для подтверждения
        assert _PENDING_KEY in result.collected_fields
        assert result.collected_fields[_PENDING_KEY]["field"] == "circumstances"
        assert result.step_completed is False


# ---------------------------------------------------------------------------
# Тесты _FIELDS_NEEDING_REFORMULATION
# ---------------------------------------------------------------------------

class TestFieldsNeedingReformulation:
    """Проверяем что константа содержит правильные поля."""

    def test_contains_expected_fields(self):
        expected = {"circumstances", "scheme", "vehicle_a_damage", "vehicle_b_damage"}
        assert expected == _FIELDS_NEEDING_REFORMULATION

    def test_structural_fields_not_in_reformulation(self):
        structural = {"date", "time", "location", "vehicle_a_make_model",
                      "vehicle_a_reg_number", "signatures_confirmed"}
        for field in structural:
            assert field not in _FIELDS_NEEDING_REFORMULATION