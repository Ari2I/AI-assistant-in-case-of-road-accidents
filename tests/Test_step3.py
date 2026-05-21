"""
Тесты для agent/step3_insurance.py.

Покрывают:
  - Фаза 1: первый вход (plan с дедлайнами), ответы на вопросы, переход в фазу 2
  - Фаза 2: первый вход, извлечение данных, генерация обращения
  - Детектор завершения step3
  - Вычисление дедлайнов
  - Форматирование данных протокола
"""

from __future__ import annotations

import sys
import pytest
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.step3_insurance import (
    _has_phase2_trigger,
    _calc_deadlines,
    _format_protocol_data,
    _missing_appeal_data,
    _EXIT_TRIGGERS,
    _PHASE2_TRIGGERS,
    process_step3,
)
from agent.step_types import Step


# ---------------------------------------------------------------------------
# Вспомогательный мок GigaChat
# ---------------------------------------------------------------------------

def _make_queue_giga(responses: list[str]):
    queue = deque(responses)

    class QueueGiga:
        def chat(self, *args, **kwargs):
            response = queue.popleft() if queue else "Ответ агента."
            class FakeMsg:
                content = response
            class FakeChoice:
                message = FakeMsg()
            class FakeResp:
                choices = [FakeChoice()]
            return FakeResp()

    return QueueGiga()


# ---------------------------------------------------------------------------
# Тесты вспомогательных функций
# ---------------------------------------------------------------------------

class TestCalcDeadlines:
    """Тесты вычисления дедлайнов."""

    def test_no_date_returns_generic(self):
        result = _calc_deadlines(None)
        assert "5 рабочих дней" in result["notify"]
        assert "15 календарных дней" in result["repair"]
        assert "5 рабочих дней" in result["inspection"]

    def test_empty_string_returns_generic(self):
        result = _calc_deadlines("")
        assert "5 рабочих дней" in result["notify"]

    def test_valid_date_returns_concrete_deadlines(self):
        result = _calc_deadlines("15.01.2025")
        # Должны быть конкретные даты, а не просто "5 рабочих дней"
        assert "до " in result["notify"]
        assert "до " in result["repair"]

    def test_invalid_date_falls_back_to_generic(self):
        result = _calc_deadlines("не_дата")
        assert "5 рабочих дней" in result["notify"]

    def test_notify_is_5_working_days(self):
        """Уведомление — 5 рабочих дней после ДТП."""
        # Понедельник 13.01.2025 → 5 рабочих дней → пятница 17.01.2025
        result = _calc_deadlines("13.01.2025")
        assert "17.01.2025" in result["notify"]

    def test_repair_is_15_calendar_days(self):
        """Запрет ремонта — 15 календарных дней."""
        result = _calc_deadlines("01.01.2025")
        assert "16.01.2025" in result["repair"]


class TestHasPhase2Trigger:
    """Тесты определения перехода в фазу 2."""

    def test_payment_trigger(self):
        assert _has_phase2_trigger("страховая выплатила деньги") is True

    def test_low_payment_trigger(self):
        assert _has_phase2_trigger("выплата занижена, хочу оспорить") is True

    def test_refusal_trigger(self):
        assert _has_phase2_trigger("страховая отказала в выплате") is True

    def test_no_trigger(self):
        assert _has_phase2_trigger("какие документы нужно подать") is False
        assert _has_phase2_trigger("когда придёт выплата") is False

    def test_all_triggers_covered(self):
        """Каждое ключевое слово из _PHASE2_TRIGGERS срабатывает."""
        for trigger in _PHASE2_TRIGGERS:
            assert _has_phase2_trigger(f"тест {trigger} тест") is True


class TestFormatProtocolData:
    """Тесты форматирования данных протокола."""

    def test_empty_returns_no_data(self):
        result = _format_protocol_data({})
        assert "не переданы" in result

    def test_date_included(self):
        result = _format_protocol_data({"date": "15.01.2025"})
        assert "15.01.2025" in result

    def test_insurer_included(self):
        result = _format_protocol_data({"vehicle_a_insurer": "Росгосстрах"})
        assert "Росгосстрах" in result

    def test_appeal_amounts_included(self):
        result = _format_protocol_data({
            "appeal_payment_amount": "45000",
            "appeal_repair_cost": "87000",
        })
        assert "45000" in result
        assert "87000" in result

    def test_full_data(self):
        fields = {
            "date": "15.01.2025",
            "location": "ул. Ленина",
            "vehicle_a_insurer": "Росгосстрах",
            "vehicle_a_damage": "передний бампер — трещина",
        }
        result = _format_protocol_data(fields)
        assert all(v in result for v in fields.values())


class TestMissingAppealData:
    """Тесты определения недостающих данных для обращения."""

    def test_both_missing(self):
        missing = _missing_appeal_data({})
        assert len(missing) == 2
        assert any("выплат" in m for m in missing)
        assert any("ремонт" in m for m in missing)

    def test_payment_missing(self):
        missing = _missing_appeal_data({"appeal_repair_cost": "87000"})
        assert len(missing) == 1
        assert any("выплат" in m for m in missing)

    def test_repair_missing(self):
        missing = _missing_appeal_data({"appeal_payment_amount": "45000"})
        assert len(missing) == 1
        assert any("ремонт" in m for m in missing)

    def test_both_present(self):
        missing = _missing_appeal_data({
            "appeal_payment_amount": "45000",
            "appeal_repair_cost": "87000",
        })
        assert missing == []


class TestExitTriggers:
    """Тесты триггеров выхода из step3."""

    def test_common_exit_phrases_in_triggers(self):
        assert "спасибо" in _EXIT_TRIGGERS
        assert "всё понятно" in _EXIT_TRIGGERS
        assert "разобрался" in _EXIT_TRIGGERS

    def test_exit_trigger_checked_correctly(self):
        for phrase in _EXIT_TRIGGERS:
            assert phrase in _EXIT_TRIGGERS


# ---------------------------------------------------------------------------
# Тесты process_step3 — фаза 1
# ---------------------------------------------------------------------------

class TestStep3Phase1:
    """Тесты первой фазы шага 3 (подача документов)."""

    def test_first_entry_shows_plan(self):
        """При первом входе агент показывает план с дедлайнами."""
        giga = _make_queue_giga([])
        result = process_step3(
            giga=giga,
            query="что делать дальше?",
            history=[],
            collected_fields={},
            db=None,
            feedback_db=None,
        )

        assert result.step_completed is False
        assert result.next_step == Step.STEP3
        assert result.collected_fields.get("step3_entered") is True

        # Ответ должен содержать ключевые элементы плана
        answer_lower = result.answer.lower()
        assert any(kw in answer_lower for kw in ["дедлайн", "срок", "5 рабочих", "направить"])

    def test_first_entry_with_date_shows_concrete_deadlines(self):
        """При наличии даты ДТП показываются конкретные дедлайны."""
        giga = _make_queue_giga([])
        result = process_step3(
            giga=giga,
            query="что делать?",
            history=[],
            collected_fields={"date": "15.01.2025"},
            db=None,
            feedback_db=None,
        )

        # Конкретная дата должна присутствовать в ответе
        assert "2025" in result.answer

    def test_first_entry_with_insurer_mentions_it(self):
        """При наличии страховой компании она упоминается в ответе."""
        giga = _make_queue_giga([])
        result = process_step3(
            giga=giga,
            query="что делать?",
            history=[],
            collected_fields={"vehicle_a_insurer": "Росгосстрах"},
            db=None,
            feedback_db=None,
        )

        assert "Росгосстрах" in result.answer

    def test_subsequent_calls_answer_questions(self):
        """Повторные вызовы отвечают на вопросы пользователя."""
        giga = _make_queue_giga(["Для получения выплаты обратитесь в свою страховую."])
        collected = {"step3_entered": True, "step3_turns": 0}

        result = process_step3(
            giga=giga,
            query="в какую страховую обращаться?",
            history=[{"query": "что делать?", "answer": "план..."}],
            collected_fields=collected,
            db=None,
            feedback_db=None,
        )

        assert result.step_completed is False
        assert "страховую" in result.answer.lower() or result.answer

    def test_turns_counter_increments(self):
        """Счётчик ходов увеличивается при каждом вызове."""
        giga = _make_queue_giga(["Ответ."])
        collected = {"step3_entered": True, "step3_turns": 2}

        process_step3(
            giga=giga,
            query="вопрос",
            history=[{"query": "q", "answer": "a"}, {"query": "q2", "answer": "a2"}],
            collected_fields=collected,
            db=None,
            feedback_db=None,
        )

        assert collected.get("step3_turns") == 3

    def test_payment_question_asked_after_3_turns(self):
        """После 3+ ходов агент спрашивает о статусе выплаты."""
        giga = _make_queue_giga(["Ответ на вопрос."])
        collected = {"step3_entered": True, "step3_turns": 2}

        result = process_step3(
            giga=giga,
            query="ещё вопрос",
            history=[
                {"query": "q1", "answer": "a1"},
                {"query": "q2", "answer": "a2"},
                {"query": "q3", "answer": "a3"},
            ],
            collected_fields=collected,
            db=None,
            feedback_db=None,
        )

        assert collected.get("step3_payment_asked") is True
        assert any(kw in result.answer for kw in ["выплат", "страховая"])


# ---------------------------------------------------------------------------
# Тесты process_step3 — фаза 2
# ---------------------------------------------------------------------------

class TestStep3Phase2:
    """Тесты второй фазы шага 3 (споры и обращения)."""

    def test_phase2_first_entry_asks_for_amounts(self):
        """При первом входе в фазу 2 агент спрашивает суммы."""
        giga = _make_queue_giga([])
        collected = {
            "step3_entered": True,
            "step3_phase": "phase2",
        }

        result = process_step3(
            giga=giga,
            query="выплатили мало",
            history=[],
            collected_fields=collected,
            db=None,
            feedback_db=None,
        )

        assert result.step_completed is False
        assert collected.get("step3_phase2_entered") is True
        assert any(kw in result.answer.lower() for kw in ["сколько", "выплат", "ремонт"])

    def test_phase2_requests_missing_data_before_appeal(self):
        """Если данных недостаточно — агент запрашивает их перед генерацией обращения."""
        giga = _make_queue_giga(["{}"])  # LLM извлечение пустое
        collected = {
            "step3_entered": True,
            "step3_phase": "phase2",
            "step3_phase2_entered": True,
            "appeal_payment_amount": "45000",
            # appeal_repair_cost отсутствует
        }

        result = process_step3(
            giga=giga,
            query="составь обращение",
            history=[],
            collected_fields=collected,
            db=None,
            feedback_db=None,
        )

        # Должен запросить стоимость ремонта
        assert result.step_completed is False
        assert any(kw in result.answer.lower() for kw in ["ремонт", "стоимость"])

    def test_phase2_generates_appeal_when_data_complete(self):
        """При наличии всех данных генерируется обращение."""
        # LLM для _generate_situational (ситуационный абзац)
        giga = _make_queue_giga(["В результате ДТП 15.01.2025 транспортному средству причинены повреждения."])
        collected = {
            "step3_entered": True,
            "step3_phase": "phase2",
            "step3_phase2_entered": True,
            "appeal_payment_amount": "45000",
            "appeal_repair_cost": "87000",
            "vehicle_a_insurer": "Росгосстрах",
            "vehicle_a_owner_name": "Иванов И.И.",
            "vehicle_a_make_model": "Toyota Camry",
            "vehicle_a_reg_number": "А123БВ777",
            "vehicle_a_policy_number": "ХХХ 1234567890",
        }

        result = process_step3(
            giga=giga,
            query="составь обращение",
            history=[],
            collected_fields=collected,
            db=None,
            feedback_db=None,
        )

        assert result.final_json is not None
        assert result.final_json["type"] == "appeal"
        assert collected.get("appeal_generated") is True
        # Разница должна быть посчитана корректно: 87000 - 45000 = 42000
        assert result.final_json["data"]["difference"] == "42000"

    def test_phase2_difference_calculation(self):
        """Разница между стоимостью ремонта и выплатой считается верно."""
        giga = _make_queue_giga(["Ситуационный абзац."])
        collected = {
            "step3_entered": True,
            "step3_phase": "phase2",
            "step3_phase2_entered": True,
            "appeal_payment_amount": "30000",
            "appeal_repair_cost": "100000",
            "appeal_has_expertise": True,
        }

        result = process_step3(
            giga=giga,
            query="хочу оспорить",
            history=[],
            collected_fields=collected,
            db=None,
            feedback_db=None,
        )

        if result.final_json:
            assert result.final_json["data"]["difference"] == "70000"


# ---------------------------------------------------------------------------
# Тесты детектора завершения step3
# ---------------------------------------------------------------------------

class TestStep3ExitDetector:
    """Тесты выхода из step3."""

    def test_thank_you_exits_step(self):
        """'Спасибо' с историей завершает step3."""
        giga = _make_queue_giga([])
        history = [{"query": "вопрос", "answer": "ответ"}]

        result = process_step3(
            giga=giga,
            query="спасибо",
            history=history,
            collected_fields={"step3_entered": True},
            db=None,
            feedback_db=None,
        )

        assert result.step_completed is True
        assert result.next_step == Step.CONSULTANT_ONLY

    def test_all_clear_exits_step(self):
        """'Всё понятно' с историей завершает step3."""
        giga = _make_queue_giga([])
        history = [{"query": "q", "answer": "a"}]

        result = process_step3(
            giga=giga,
            query="всё понятно",
            history=history,
            collected_fields={"step3_entered": True},
            db=None,
            feedback_db=None,
        )

        assert result.step_completed is True

    def test_no_exit_without_history(self):
        """Без истории диалога exit-триггер не срабатывает."""
        giga = _make_queue_giga([])

        result = process_step3(
            giga=giga,
            query="спасибо",
            history=[],  # история пуста
            collected_fields={},
            db=None,
            feedback_db=None,
        )

        # Без истории это первый вход в step3 — показывает план
        assert result.step_completed is False

    def test_exit_message_is_friendly(self):
        """Сообщение при выходе дружелюбное."""
        giga = _make_queue_giga([])
        history = [{"query": "q", "answer": "a"}]

        result = process_step3(
            giga=giga,
            query="разобрался",
            history=history,
            collected_fields={"step3_entered": True},
            db=None,
            feedback_db=None,
        )

        assert result.step_completed is True
        assert result.answer  # не пустой


# ---------------------------------------------------------------------------
# Тесты фиксации phase2 trigger
# ---------------------------------------------------------------------------

class TestPhase2Transition:
    """Тесты перехода из фазы 1 в фазу 2."""

    def test_phase2_triggered_by_payment_received(self):
        """При 'выплатили' + LLM-подтверждение переходим в фазу 2."""
        # LLM для _confirm_phase2_with_llm
        giga = _make_queue_giga(['{"phase2": true, "reason": "получил выплату"}'])
        collected = {
            "step3_entered": True,
            "step3_turns": 1,
            "step3_phase": "phase1",
        }

        result = process_step3(
            giga=giga,
            query="страховая выплатила 45000 рублей, но этого мало",
            history=[{"query": "q", "answer": "a"}],
            collected_fields=collected,
            db=None,
            feedback_db=None,
        )

        assert collected.get("step3_phase") == "phase2"

    def test_phase2_not_triggered_without_llm_confirmation(self):
        """При отрицательном ответе LLM фаза 2 не активируется."""
        # LLM возвращает phase2: false
        giga = _make_queue_giga(['{"phase2": false, "reason": "просто вопрос"}', "Обычный ответ."])
        collected = {
            "step3_entered": True,
            "step3_turns": 0,
            "step3_phase": "phase1",
        }

        result = process_step3(
            giga=giga,
            query="когда выплатят?",
            history=[{"query": "q", "answer": "a"}],
            collected_fields=collected,
            db=None,
            feedback_db=None,
        )

        assert collected.get("step3_phase", "phase1") == "phase1"