"""
Unit-тесты для модуля step2_europrotocol.

Проверяют детерминированную логику проверки возможности Европротокола.
"""

from __future__ import annotations

import unittest

from agent.step2_europrotocol import (
    EuroprotocolCheckResult,
    StopFactor,
    LIMIT_BASE,
    LIMIT_WITH_APP_NO_DISAGREEMENT,
    LIMIT_WITH_APP_DISAGREEMENT,
    process_step2_check,
    validate_slots_for_step2,
)


class TestStopFactor(unittest.TestCase):
    """Тесты для класса StopFactor."""

    def test_to_dict(self) -> None:
        """Проверка конвертации в словарь."""
        sf = StopFactor(
            code="victims",
            message="Есть пострадавшие",
            severity="critical",
        )

        result = sf.to_dict()

        self.assertEqual(result["code"], "victims")
        self.assertEqual(result["message"], "Есть пострадавшие")
        self.assertEqual(result["severity"], "critical")


class TestEuroprotocolCheckResult(unittest.TestCase):
    """Тесты для класса EuroprotocolCheckResult."""

    def test_to_dict_empty(self) -> None:
        """Проверка конвертации пустого результата."""
        result = EuroprotocolCheckResult(
            is_possible=True,
            stop_factors=[],
            recommendation="Test",
            next_step="step3",
            limits={"base": 100000},
        )

        result_dict = result.to_dict()

        self.assertTrue(result_dict["is_possible"])
        self.assertEqual(result_dict["stop_factors"], [])
        self.assertEqual(result_dict["recommendation"], "Test")
        self.assertEqual(result_dict["next_step"], "step3")
        self.assertEqual(result_dict["limits"], {"base": 100000})

    def test_to_dict_with_stop_factors(self) -> None:
        """Проверка конвертации со стоп-факторами."""
        result = EuroprotocolCheckResult(
            is_possible=False,
            stop_factors=[
                StopFactor("victims", "Пострадавшие", "critical"),
            ],
            recommendation="Call 102",
            next_step="call_gibdd",
            limits={},
        )

        result_dict = result.to_dict()

        self.assertFalse(result_dict["is_possible"])
        self.assertEqual(len(result_dict["stop_factors"]), 1)
        self.assertEqual(result_dict["stop_factors"][0]["code"], "victims")


class TestProcessStep2Check(unittest.TestCase):
    """Тесты для основной функции process_step2_check."""

    # =========================================================================
    # СЦЕНАРИЙ A: Европротокол возможен
    # =========================================================================

    def test_europrotocol_possible_no_disagreement(self) -> None:
        """✅ Европротокол возможен: нет разногласий, без приложения."""
        slots = {
            "victims": False,
            "participants_count": 2,
            "osago_both": True,
            "disagreement": False,
        }

        result = process_step2_check(slots, has_app=False)

        self.assertTrue(result.is_possible)
        self.assertEqual(len(result.stop_factors), 0)
        self.assertEqual(result.next_step, "step3_fixation")
        self.assertIn("base", result.limits)
        self.assertEqual(result.limits["base"], LIMIT_BASE)

    def test_europrotocol_possible_with_app(self) -> None:
        """✅ Европротокол возможен: с приложением, максимальный лимит."""
        slots = {
            "victims": False,
            "participants_count": 2,
            "osago_both": True,
            "disagreement": False,
        }

        result = process_step2_check(slots, has_app=True)

        self.assertTrue(result.is_possible)
        self.assertEqual(len(result.stop_factors), 0)
        self.assertEqual(result.next_step, "step3_fixation")
        self.assertEqual(
            result.limits["base"],
            LIMIT_WITH_APP_NO_DISAGREEMENT,
        )

    # =========================================================================
    # СЦЕНАРИЙ B: Европротокол невозможен (критические стоп-факторы)
    # =========================================================================

    def test_victims_present(self) -> None:
        """❌ Пострадавшие: Европротокол невозможен."""
        slots = {
            "victims": True,
            "participants_count": 2,
            "osago_both": True,
            "disagreement": False,
        }

        result = process_step2_check(slots, has_app=False)

        self.assertFalse(result.is_possible)
        self.assertEqual(len(result.stop_factors), 1)
        self.assertEqual(result.stop_factors[0].code, "victims")
        self.assertEqual(result.stop_factors[0].severity, "critical")
        self.assertEqual(result.next_step, "call_gibdd")

    def test_participants_3plus(self) -> None:
        """❌ Участников > 2: Европротокол невозможен."""
        slots = {
            "victims": False,
            "participants_count": 3,
            "osago_both": True,
            "disagreement": False,
        }

        result = process_step2_check(slots, has_app=False)

        self.assertFalse(result.is_possible)
        self.assertEqual(len(result.stop_factors), 1)
        self.assertEqual(
            result.stop_factors[0].code,
            "participants_3plus",
        )
        self.assertEqual(result.next_step, "call_gibdd")

    def test_single_participant(self) -> None:
        """❌ Один участник: Европротокол невозможен."""
        slots = {
            "victims": False,
            "participants_count": 1,
            "osago_both": True,
            "disagreement": False,
        }

        result = process_step2_check(slots, has_app=False)

        self.assertFalse(result.is_possible)
        self.assertEqual(len(result.stop_factors), 1)
        self.assertEqual(
            result.stop_factors[0].code,
            "participants_1",
        )
        self.assertEqual(result.next_step, "call_gibdd")

    def test_no_osago(self) -> None:
        """❌ Нет ОСАГО: Европротокол невозможен."""
        slots = {
            "victims": False,
            "participants_count": 2,
            "osago_both": False,
            "disagreement": False,
        }

        result = process_step2_check(slots, has_app=False)

        self.assertFalse(result.is_possible)
        self.assertEqual(len(result.stop_factors), 1)
        self.assertEqual(result.stop_factors[0].code, "no_osago")
        self.assertEqual(result.next_step, "call_gibdd")

    def test_multiple_critical_factors(self) -> None:
        """❌ Несколько критических факторов одновременно."""
        slots = {
            "victims": True,
            "participants_count": 3,
            "osago_both": False,
            "disagreement": True,
        }

        result = process_step2_check(slots, has_app=False)

        self.assertFalse(result.is_possible)
        # Должны быть все критические факторы
        codes = [sf.code for sf in result.stop_factors]
        self.assertIn("victims", codes)
        self.assertIn("participants_3plus", codes)
        self.assertIn("no_osago", codes)
        self.assertEqual(result.next_step, "call_gibdd")

    # =========================================================================
    # СЦЕНАРИЙ C: Европротокол условно возможен (разногласия)
    # =========================================================================

    def test_disagreement_without_app(self) -> None:
        """⚠️ Разногласия без приложения: условно возможен."""
        slots = {
            "victims": False,
            "participants_count": 2,
            "osago_both": True,
            "disagreement": True,
        }

        result = process_step2_check(slots, has_app=False)

        self.assertEqual(result.is_possible, "conditional")
        self.assertEqual(len(result.stop_factors), 1)
        self.assertEqual(
            result.stop_factors[0].code,
            "disagreement_no_app",
        )
        self.assertEqual(result.stop_factors[0].severity, "warning")
        self.assertEqual(
            result.next_step,
            "step3_fixation_with_disagreement",
        )
        self.assertEqual(result.limits.get("base"), 0)
        self.assertEqual(
            result.limits.get("with_app"),
            LIMIT_WITH_APP_DISAGREEMENT,
        )

    def test_disagreement_with_app(self) -> None:
        """✅ Разногласия с приложением: возможен (лимит 200к)."""
        slots = {
            "victims": False,
            "participants_count": 2,
            "osago_both": True,
            "disagreement": True,
        }

        result = process_step2_check(slots, has_app=True)

        # С приложением разногласия не блокируют
        self.assertTrue(result.is_possible)
        self.assertEqual(len(result.stop_factors), 0)
        self.assertEqual(result.next_step, "step3_fixation")
        self.assertEqual(
            result.limits["base"],
            LIMIT_WITH_APP_DISAGREEMENT,
        )

    # =========================================================================
    # ГРАНИЧНЫЕ СЛУЧАИ
    # =========================================================================

    def test_none_values_in_slots(self) -> None:
        """Проверка обработки None значений в слотах."""
        slots = {
            "victims": None,
            "participants_count": None,
            "osago_both": None,
            "disagreement": None,
        }

        # None значения не должны вызывать ошибок
        # и не должны считаться стоп-факторами
        result = process_step2_check(slots, has_app=False)

        # При None значениях Европротокол считается возможным
        # (логика проверяет только явные True/False)
        self.assertTrue(result.is_possible)

    def test_missing_slots(self) -> None:
        """Проверка обработки отсутствующих слотов."""
        slots: dict = {}

        # Пустые слоты не должны вызывать ошибок
        result = process_step2_check(slots, has_app=False)

        # Без данных Европротокол считается возможным
        # (валидация должна происходить до вызова этой функции)
        self.assertTrue(result.is_possible)


class TestValidateSlotsForStep2(unittest.TestCase):
    """Тесты для функции валидации слотов."""

    def test_valid_slots(self) -> None:
        """Валидные слоты."""
        slots = {
            "victims": False,
            "participants_count": 2,
            "osago_both": True,
            "disagreement": False,
        }

        is_valid, errors = validate_slots_for_step2(slots)

        self.assertTrue(is_valid)
        self.assertEqual(errors, [])

    def test_missing_required_slot(self) -> None:
        """Отсутствует обязательный слот."""
        slots = {
            "victims": False,
            "participants_count": 2,
            # osago_both отсутствует
            "disagreement": False,
        }

        is_valid, errors = validate_slots_for_step2(slots)

        self.assertFalse(is_valid)
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("osago_both" in err for err in errors))

    def test_invalid_type_victims(self) -> None:
        """Неверный тип для victims."""
        slots = {
            "victims": "yes",  # должно быть bool
            "participants_count": 2,
            "osago_both": True,
            "disagreement": False,
        }

        is_valid, errors = validate_slots_for_step2(slots)

        self.assertFalse(is_valid)
        self.assertTrue(any("victims must be bool" in err for err in errors))

    def test_invalid_type_participants_count(self) -> None:
        """Неверный тип для participants_count."""
        slots = {
            "victims": False,
            "participants_count": "two",  # должно быть int
            "osago_both": True,
            "disagreement": False,
        }

        is_valid, errors = validate_slots_for_step2(slots)

        self.assertFalse(is_valid)
        self.assertTrue(
            any("participants_count must be int" in err for err in errors)
        )

    def test_invalid_type_osago_both(self) -> None:
        """Неверный тип для osago_both."""
        slots = {
            "victims": False,
            "participants_count": 2,
            "osago_both": "yes",  # должно быть bool
            "disagreement": False,
        }

        is_valid, errors = validate_slots_for_step2(slots)

        self.assertFalse(is_valid)
        self.assertTrue(any("osago_both must be bool" in err for err in errors))

    def test_invalid_type_disagreement(self) -> None:
        """Неверный тип для disagreement."""
        slots = {
            "victims": False,
            "participants_count": 2,
            "osago_both": True,
            "disagreement": "no",  # должно быть bool
        }

        is_valid, errors = validate_slots_for_step2(slots)

        self.assertFalse(is_valid)
        self.assertTrue(
            any("disagreement must be bool" in err for err in errors)
        )

    def test_null_values_allowed(self) -> None:
        """None значения допустимы."""
        slots = {
            "victims": None,
            "participants_count": None,
            "osago_both": None,
            "disagreement": None,
        }

        is_valid, errors = validate_slots_for_step2(slots)

        # None значения допустимы
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])


class TestRecommendations(unittest.TestCase):
    """Тесты для рекомендаций в результатах."""

    def test_victims_recommendation_includes_103(self) -> None:
        """Рекомендация при пострадавших включает 103."""
        slots = {
            "victims": True,
            "participants_count": 2,
            "osago_both": True,
            "disagreement": False,
        }

        result = process_step2_check(slots, has_app=False)

        self.assertIn("103", result.recommendation)
        self.assertIn("102", result.recommendation)

    def test_no_victims_recommendation_includes_102(self) -> None:
        """Рекомендация без пострадавших включает 102."""
        slots = {
            "victims": False,
            "participants_count": 3,
            "osago_both": True,
            "disagreement": False,
        }

        result = process_step2_check(slots, has_app=False)

        self.assertIn("102", result.recommendation)
        self.assertNotIn("103", result.recommendation)

    def test_possible_recommendation_mentions_apps(self) -> None:
        """Рекомендация при возможном Европротоколе упоминает приложения."""
        slots = {
            "victims": False,
            "participants_count": 2,
            "osago_both": True,
            "disagreement": False,
        }

        result = process_step2_check(slots, has_app=False)

        self.assertTrue(result.is_possible)
        # Проверяем, что есть упоминание приложений или лимита
        self.assertTrue(
            "приложение" in result.recommendation.lower()
            or "400 000" in result.recommendation
        )

    def test_conditional_recommendation_mentions_apps(self) -> None:
        """Рекомендация при разногласиях упоминает приложения."""
        slots = {
            "victims": False,
            "participants_count": 2,
            "osago_both": True,
            "disagreement": True,
        }

        result = process_step2_check(slots, has_app=False)

        self.assertEqual(result.is_possible, "conditional")
        self.assertTrue(
            "приложение" in result.recommendation.lower()
            or "Госуслуги" in result.recommendation
            or "Помощник" in result.recommendation
        )


if __name__ == "__main__":
    unittest.main()