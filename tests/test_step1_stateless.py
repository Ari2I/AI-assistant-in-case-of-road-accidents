"""
Тесты для Stateless Step 1 — сбор фактов ДТП.

Покрывают:
  - Инициализацию и валидацию слотов
  - Определение пустых слотов
  - Форматирование известных фактов
  - Маппинг слот -> блок алгоритма
  - Fallback-вопросы
"""

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))


# =============================================================================
# ТЕСТЫ ВАЛИДАЦИИ СЛОТОВ
# =============================================================================

class TestSlotValidation:
    """Тесты валидации структуры слотов."""

    def test_valid_complete_slots(self):
        """Полный набор валидных слотов."""
        from agent.step1_stateless import validate_slots
        slots = {
            "safety_confirmed": True,
            "emergency_sign": False,
            "victims": False,
            "participants_count": 2,
            "osago_both": True,
            "disagreement": False,
        }
        is_valid, errors = validate_slots(slots)
        assert is_valid is True
        assert len(errors) == 0

    def test_valid_partial_slots(self):
        """Частично заполненные слоты (с None)."""
        from agent.step1_stateless import validate_slots
        slots = {
            "safety_confirmed": True,
            "emergency_sign": None,
            "victims": None,
            "participants_count": None,
            "osago_both": None,
            "disagreement": None,
        }
        is_valid, errors = validate_slots(slots)
        assert is_valid is True

    def test_invalid_type_safety_confirmed(self):
        """Неверный тип safety_confirmed."""
        from agent.step1_stateless import validate_slots
        slots = {"safety_confirmed": "yes", "emergency_sign": None,
                 "victims": None, "participants_count": None,
                 "osago_both": None, "disagreement": None}
        is_valid, errors = validate_slots(slots)
        assert is_valid is False
        assert any("safety_confirmed must be bool" in e for e in errors)

    def test_invalid_type_participants_count(self):
        """Неверный тип participants_count."""
        from agent.step1_stateless import validate_slots
        slots = {"safety_confirmed": True, "emergency_sign": True,
                 "victims": False, "participants_count": "два",
                 "osago_both": True, "disagreement": False}
        is_valid, errors = validate_slots(slots)
        assert is_valid is False
        assert any("participants_count must be int" in e for e in errors)

    def test_missing_slot(self):
        """Отсутствующий обязательный слот."""
        from agent.step1_stateless import validate_slots
        slots = {
            "safety_confirmed": True,
            "victims": False,
            "participants_count": 2,
            "osago_both": True,
            "disagreement": False,
        }
        is_valid, errors = validate_slots(slots)
        assert is_valid is False
        assert any("Missing required slot: emergency_sign" in e for e in errors)


# =============================================================================
# ТЕСТЫ ИНИЦИАЛИЗАЦИИ СЛОТОВ
# =============================================================================

class TestSlotInitialization:
    """Тесты инициализации слотов."""

    def test_init_empty(self):
        """Инициализация пустых слотов."""
        from agent.step1_stateless import _init_slots
        slots = _init_slots({})
        assert slots["safety_confirmed"] is None
        assert slots["emergency_sign"] is None
        assert slots["victims"] is None
        assert slots["participants_count"] is None
        assert slots["osago_both"] is None
        assert slots["disagreement"] is None

    def test_init_with_values(self):
        """Инициализация с переданными значениями."""
        from agent.step1_stateless import _init_slots
        slots = _init_slots({"safety_confirmed": True, "victims": False})
        assert slots["safety_confirmed"] is True
        assert slots["victims"] is False
        assert slots["emergency_sign"] is None
        assert slots["participants_count"] is None

    def test_init_ignores_unknown_keys(self):
        """Неизвестные ключи игнорируются."""
        from agent.step1_stateless import _init_slots
        slots = _init_slots({"safety_confirmed": True, "unknown_key": "value"})
        assert slots["safety_confirmed"] is True
        assert "unknown_key" not in slots


# =============================================================================
# ТЕСТЫ ОПРЕДЕЛЕНИЯ ПУСТЫХ СЛОТОВ
# =============================================================================

class TestEmptySlots:
    """Тесты определения незаполненных слотов."""

    def test_all_empty(self):
        """Все слоты пустые."""
        from agent.step1_stateless import _get_empty_slots
        slots = {k: None for k in ["safety_confirmed", "emergency_sign",
                                    "victims", "participants_count",
                                    "osago_both", "disagreement"]}
        empty = _get_empty_slots(slots)
        assert len(empty) == 6
        assert empty[0] == "safety_confirmed"

    def test_all_filled(self):
        """Все слоты заполнены."""
        from agent.step1_stateless import _get_empty_slots
        slots = {
            "safety_confirmed": True, "emergency_sign": True,
            "victims": False, "participants_count": 2,
            "osago_both": True, "disagreement": False,
        }
        empty = _get_empty_slots(slots)
        assert len(empty) == 0

    def test_partial_filled(self):
        """Частично заполненные слоты."""
        from agent.step1_stateless import _get_empty_slots
        slots = {
            "safety_confirmed": True, "emergency_sign": True,
            "victims": None, "participants_count": None,
            "osago_both": None, "disagreement": None,
        }
        empty = _get_empty_slots(slots)
        assert len(empty) == 4
        assert empty[0] == "victims"

    def test_order_preserved(self):
        """Порядок пустых слотов соответствует SLOT_ORDER."""
        from agent.step1_stateless import _get_empty_slots
        slots = {
            "safety_confirmed": None, "emergency_sign": True,
            "victims": None, "participants_count": 2,
            "osago_both": None, "disagreement": False,
        }
        empty = _get_empty_slots(slots)
        assert empty == ["safety_confirmed", "victims", "osago_both"]


# =============================================================================
# ТЕСТЫ МАППИНГА СЛОТ -> БЛОК
# =============================================================================

class TestSlotToBlockMapping:
    """Тесты сопоставления слотов блокам алгоритма."""

    def test_safety_confirmed(self):
        from agent.step1_stateless import _slot_to_block
        assert _slot_to_block("safety_confirmed") == 0

    def test_emergency_sign(self):
        from agent.step1_stateless import _slot_to_block
        assert _slot_to_block("emergency_sign") == 1

    def test_victims(self):
        from agent.step1_stateless import _slot_to_block
        assert _slot_to_block("victims") == 2

    def test_participants_count(self):
        from agent.step1_stateless import _slot_to_block
        assert _slot_to_block("participants_count") == 3

    def test_osago_both(self):
        from agent.step1_stateless import _slot_to_block
        assert _slot_to_block("osago_both") == 4

    def test_disagreement(self):
        from agent.step1_stateless import _slot_to_block
        assert _slot_to_block("disagreement") == 5

    def test_unknown_slot(self):
        """Неизвестный слот возвращает блок 0 по умолчанию."""
        from agent.step1_stateless import _slot_to_block
        assert _slot_to_block("unknown") == 0


# =============================================================================
# ТЕСТЫ FALLBACK-ВОПРОСОВ
# =============================================================================

class TestFallbackQuestions:
    """Тесты запасных вопросов (когда LLM недоступна)."""

    def test_safety_confirmed_question(self):
        from agent.step1_stateless import _fallback_question
        q = _fallback_question("safety_confirmed")
        assert "безопасности" in q.lower() or "пожара" in q.lower()

    def test_emergency_sign_question(self):
        from agent.step1_stateless import _fallback_question
        q = _fallback_question("emergency_sign")
        assert "аварийную" in q.lower() or "знак" in q.lower()

    def test_victims_question(self):
        from agent.step1_stateless import _fallback_question
        q = _fallback_question("victims")
        assert "пострадавшие" in q.lower()

    def test_participants_count_question(self):
        from agent.step1_stateless import _fallback_question
        q = _fallback_question("participants_count")
        assert "сколько" in q.lower() or "участвовало" in q.lower()

    def test_osago_both_question(self):
        from agent.step1_stateless import _fallback_question
        q = _fallback_question("osago_both")
        assert "осаго" in q.lower() or "полис" in q.lower()

    def test_disagreement_question(self):
        from agent.step1_stateless import _fallback_question
        q = _fallback_question("disagreement")
        assert "согласны" in q.lower() or "разногласия" in q.lower()

    def test_unknown_slot_default(self):
        from agent.step1_stateless import _fallback_question
        q = _fallback_question("unknown")
        assert len(q) > 0


# =============================================================================
# ТЕСТЫ ФОРМАТИРОВАНИЯ ИЗВЕСТНЫХ ФАКТОВ
# =============================================================================

class TestFormatKnownFacts:
    """Тесты форматирования известных фактов для промпта."""

    def test_empty_slots(self):
        from agent.step1_stateless import _format_known_facts
        slots = {k: None for k in ["safety_confirmed", "emergency_sign",
                                    "victims", "participants_count",
                                    "osago_both", "disagreement"]}
        result = _format_known_facts(slots)
        assert "ничего не известно" in result.lower()

    def test_partial_slots(self):
        from agent.step1_stateless import _format_known_facts
        slots = {
            "safety_confirmed": True, "emergency_sign": None,
            "victims": False, "participants_count": None,
            "osago_both": None, "disagreement": None,
        }
        result = _format_known_facts(slots)
        assert "safety_confirmed: True" in result
        assert "victims: False" in result
        assert "emergency_sign" not in result

    def test_all_slots(self):
        from agent.step1_stateless import _format_known_facts
        slots = {
            "safety_confirmed": True, "emergency_sign": True,
            "victims": False, "participants_count": 2,
            "osago_both": True, "disagreement": False,
        }
        result = _format_known_facts(slots)
        lines = [l.strip() for l in result.split("\n") if l.strip()]
        assert len(lines) == 6


# =============================================================================
# ТЕСТЫ STEP1RESPONSE
# =============================================================================

class TestStep1Response:
    """Тесты класса ответа Step1Response."""

    def test_incomplete_step(self):
        """Незавершённый шаг."""
        from agent.step1_stateless import Step1Response
        result = Step1Response({
            "slots": {"safety_confirmed": True},
            "answer": "Вопрос пользователю",
            "step_completed": False,
            "next_step": None,
        })
        assert result.step_completed is False
        assert result.answer == "Вопрос пользователю"
        assert result.next_step is None

    def test_completed_step(self):
        """Завершённый шаг."""
        from agent.step1_stateless import Step1Response
        result = Step1Response({
            "slots": {"safety_confirmed": True, "victims": False},
            "answer": None,
            "step_completed": True,
            "next_step": "step2_europrotocol_check",
        })
        assert result.step_completed is True
        assert result.answer is None
        assert result.next_step == "step2_europrotocol_check"

    def test_dict_access(self):
        """Доступ как к словарю."""
        from agent.step1_stateless import Step1Response
        result = Step1Response({"slots": {"a": 1}})
        assert result["slots"] == {"a": 1}



# =============================================================================
# ТЕСТЫ process_step1_with_llm С МОКИРОВАНИЕМ GIGACHAT
# =============================================================================

class TestStep1WithLLM:
    """Тесты process_step1_with_llm с мокированием GigaChat."""

    @staticmethod
    def _make_giga(json_response: str):
        """Возвращает мок GigaChat с фиксированным ответом."""
        class FakeMsg:
            content = json_response
        class FakeChoice:
            message = FakeMsg()
        class FakeResp:
            choices = [FakeChoice()]
        class FakeGiga:
            def chat(self, *args, **kwargs):
                return FakeResp()
        return FakeGiga()

    def test_victims_stops_at_call_gibdd(self):
        from agent.step1_stateless import process_step1_with_llm
        giga = self._make_giga(
            '{"victims": true, "safety_confirmed": null, '
            '"emergency_sign": null, "participants_count": null, '
            '"osago_both": null, "disagreement": null}'
        )
        result = process_step1_with_llm(giga, "есть пострадавший", [], {})
        assert result.step_completed is True
        assert str(result.next_step) in ("call_gibdd", "Step.CALL_GIBDD")
        assert "103" in result.answer or "102" in result.answer

    def test_no_osago_stops_at_call_gibdd(self):
        from agent.step1_stateless import process_step1_with_llm
        giga = self._make_giga(
            '{"victims": false, "participants_count": 2, '
            '"osago_both": false, "safety_confirmed": null, '
            '"emergency_sign": null, "disagreement": null}'
        )
        result = process_step1_with_llm(giga, "нет ОСАГО", [], {})
        assert result.step_completed is True
        assert str(result.next_step) in ("call_gibdd", "Step.CALL_GIBDD")

    def test_all_slots_transitions_to_step2(self):
        from agent.step1_stateless import process_step1_with_llm
        full_slots = {
            "safety_confirmed": True, "emergency_sign": True,
            "victims": False, "participants_count": 2,
            "osago_both": True, "disagreement": False,
        }
        # LLM не добавляет ничего нового
        giga = self._make_giga(
            '{"safety_confirmed": null, "emergency_sign": null, '
            '"victims": null, "participants_count": null, '
            '"osago_both": null, "disagreement": null}'
        )
        result = process_step1_with_llm(giga, "всё верно", [], full_slots)
        assert result.step_completed is True
        assert str(result.next_step) in ("step2", "Step.STEP2")

    def test_partial_slots_asks_question(self):
        from agent.step1_stateless import process_step1_with_llm
        giga = self._make_giga(
            '{"safety_confirmed": true, "emergency_sign": null, '
            '"victims": null, "participants_count": null, '
            '"osago_both": null, "disagreement": null}'
        )
        result = process_step1_with_llm(giga, "аварийку включил", [], {})
        assert result.step_completed is False
        assert str(result.next_step) in ("step1", "Step.STEP1")
        assert result.answer

    def test_broken_json_preserves_current_slots(self):
        from agent.step1_stateless import process_step1_with_llm
        class BrokenGiga:
            def chat(self, *a, **kw):
                class R:
                    class C:
                        class M:
                            content = "не JSON"
                        message = M()
                    choices = [C()]
                return R()
        current = {"safety_confirmed": True}
        result = process_step1_with_llm(BrokenGiga(), "непонятно", [], current)
        assert result.slots.get("safety_confirmed") is True

    def test_three_participants_stops(self):
        from agent.step1_stateless import process_step1_with_llm
        giga = self._make_giga(
            '{"victims": false, "participants_count": 3, '
            '"osago_both": null, "safety_confirmed": null, '
            '"emergency_sign": null, "disagreement": null}'
        )
        result = process_step1_with_llm(giga, "три машины", [], {})
        assert result.step_completed is True
        assert str(result.next_step) in ("call_gibdd", "Step.CALL_GIBDD")