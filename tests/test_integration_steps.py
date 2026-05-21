"""
Интеграционные тесты: flow step1 -> step2.
Мокирует GigaChat, не делает реальных API-вызовов.
Симулирует поведение Django-бэкенда (хранение и передача состояния).

Обновление: после рефакторинга core.py (_make_giga вызывается один раз
внутри run_agent через `with _make_giga() as giga`), мок QueueGiga должен
поддерживать контекстный менеджер (__enter__/__exit__).
Это уже было реализовано, тесты совместимы.
"""

import sys
import pytest
from collections import deque
from unittest.mock import patch


def _make_queue_giga(responses: list[str]):
    """
    Мок GigaChat с очередью ответов.
    Каждый вызов chat() берёт следующий элемент из очереди.
    При исчерпании — возвращает '{}' (пустой JSON).
    Поддерживает контекстный менеджер для совместимости с `with _make_giga() as giga`.
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

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    return QueueGiga()


class TestStep1Isolated:
    """Тесты step1 в изоляции (без run_agent)."""

    def test_stop_factor_victims(self):
        from agent.step1_stateless import process_step1_with_llm
        from agent.step_types import Step
        giga = _make_queue_giga([
            '{"victims": true, "participants_count": null, '
            '"osago_both": null, "safety_confirmed": null, '
            '"emergency_sign": null, "disagreement": null}'
        ])
        result = process_step1_with_llm(giga, "есть пострадавший", [], {})
        assert result.step_completed is True
        assert result.next_step == Step.CALL_GIBDD

    def test_stop_factor_no_osago(self):
        from agent.step1_stateless import process_step1_with_llm
        from agent.step_types import Step
        giga = _make_queue_giga([
            '{"victims": false, "participants_count": 2, '
            '"osago_both": false, "safety_confirmed": null, '
            '"emergency_sign": null, "disagreement": null}'
        ])
        result = process_step1_with_llm(giga, "нет ОСАГО", [], {})
        assert result.step_completed is True
        assert result.next_step == Step.CALL_GIBDD

    def test_completes_when_all_filled(self):
        from agent.step1_stateless import process_step1_with_llm
        from agent.step_types import Step
        giga = _make_queue_giga([
            '{"safety_confirmed": null, "emergency_sign": null, '
            '"victims": null, "participants_count": null, '
            '"osago_both": null, "disagreement": null}'
        ])
        all_slots = {
            "safety_confirmed": True, "emergency_sign": True,
            "victims": False, "participants_count": 2,
            "osago_both": True, "disagreement": False,
        }
        result = process_step1_with_llm(giga, "всё верно", [], all_slots)
        assert result.step_completed is True
        assert result.next_step == Step.OFFER_EUROPROTOCOL

    def test_asks_question_when_incomplete(self):
        from agent.step1_stateless import process_step1_with_llm
        from agent.step_types import Step
        giga = _make_queue_giga([
            '{"safety_confirmed": true, "emergency_sign": null, '
            '"victims": null, "participants_count": null, '
            '"osago_both": null, "disagreement": null}',
            "Включили ли вы аварийную сигнализацию?",
        ])
        result = process_step1_with_llm(giga, "место безопасное", [], {})
        assert result.step_completed is False
        assert result.next_step == Step.STEP1
        assert result.answer

    def test_slots_accumulate_across_calls(self):
        """Слоты накапливаются через current_slots."""
        from agent.step1_stateless import process_step1_with_llm

        giga1 = _make_queue_giga([
            '{"safety_confirmed": true, "emergency_sign": null, '
            '"victims": null, "participants_count": null, '
            '"osago_both": null, "disagreement": null}',
            "Есть ли пострадавшие?",
        ])
        r1 = process_step1_with_llm(giga1, "всё безопасно", [], {})
        assert r1.slots.get("safety_confirmed") is True

        giga2 = _make_queue_giga([
            '{"safety_confirmed": null, "emergency_sign": true, '
            '"victims": false, "participants_count": null, '
            '"osago_both": null, "disagreement": null}',
            "Сколько участников?",
        ])
        r2 = process_step1_with_llm(
            giga2, "знак выставил, пострадавших нет", [], r1.slots
        )
        assert r2.slots.get("safety_confirmed") is True
        assert r2.slots.get("emergency_sign") is True
        assert r2.slots.get("victims") is False


class TestStep2Isolated:
    """Тесты step2 в изоляции (без run_agent)."""

    def test_asks_first_empty_field(self):
        from agent.step2_europrotocol import process_step2_with_llm
        from agent.step_types import Step
        giga = _make_queue_giga([
            '{"datetime": null, "location": null}'
        ])
        result = process_step2_with_llm(giga, "начнём", [], {}, {})
        assert result.step_completed is False
        assert result.next_step == Step.STEP2
        assert result.answer

    def test_collects_field_from_message(self):
        from agent.step2_europrotocol import process_step2_with_llm
        giga = _make_queue_giga([
            '{"date": "15.01.2024", "time": "14:30"}'
        ])
        result = process_step2_with_llm(
            giga, "ДТП было 15.01.2024 в 14:30", [], {}, {}
        )
        assert result.collected_fields.get("date") == "15.01.2024"
        assert result.collected_fields.get("time") == "14:30"

    def test_completes_when_all_fields_filled(self):
        from agent.step2_europrotocol import process_step2_with_llm
        all_fields = {
            "date": "15.01.2024",
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
            "circumstances": "А двигался прямо, Б поворачивал.",
            "vehicle_a_fault": "не виноват",
            "vehicle_b_fault": "виноват",
            "scheme": "А стоял у обочины, Б въехал сзади.",
            "signatures_confirmed": True,
        }
        giga = _make_queue_giga(['{}'])
        result = process_step2_with_llm(
            giga, "всё верно", [], {}, all_fields
        )
        assert result.step_completed is True
        assert result.final_json is not None
        assert result.final_json["type"] == "europrotocol"


class TestFullFlow:
    """
    Сквозные тесты: step1 -> step2 через run_agent().
    Симулирует бэкенд: хранит и передаёт состояние вручную.

    После рефакторинга core.py: _make_giga вызывается один раз внутри
    run_agent через `with _make_giga() as giga`. Мок подменяет _make_giga
    функцией, возвращающей QueueGiga. QueueGiga поддерживает __enter__/__exit__,
    поэтому `with _make_giga() as giga` корректно получает экземпляр мока.
    """

    def _backend_call(
        self,
        query: str,
        current_step: str,
        history: list,
        slots: dict,
        collected_fields: dict,
        giga_responses: list[str],
    ) -> dict:
        """
        Один цикл запрос -> ответ через run_agent() с мокированием GigaChat.
        """
        from agent.core import run_agent
        mock_giga = _make_queue_giga(giga_responses)

        # _make_giga заменяем функцией, возвращающей мок.
        # Мок поддерживает контекстный менеджер, поэтому
        # `with _make_giga() as giga` получит экземпляр QueueGiga.
        with patch("agent.core._make_giga", return_value=mock_giga):
            response = run_agent(
                query=query,
                current_step=current_step,
                history=history,
                slots=slots,
                collected_fields=collected_fields,
            )
        return response

    def test_step1_to_offer_europrotocol_transition(self):
        """
        Сценарий: пользователь заполняет все слоты step1 →
        автоматический переход на offer_europrotocol.
        """
        from agent.step_types import Step
        history = []
        slots = {}
        collected_fields = {}
        current_step = "step1"

        slot_batches = [
            '{"victims": false, "participants_count": 2, '
            '"osago_both": null, "safety_confirmed": null, '
            '"emergency_sign": null, "disagreement": null}',
            '{"victims": null, "participants_count": null, '
            '"osago_both": true, "safety_confirmed": true, '
            '"emergency_sign": null, "disagreement": null}',
            '{"victims": null, "participants_count": null, '
            '"osago_both": null, "safety_confirmed": null, '
            '"emergency_sign": true, "disagreement": false}',
        ]

        for i, slot_json in enumerate(slot_batches):
            resp = self._backend_call(
                query=f"реплика {i+1}",
                current_step=current_step,
                history=history,
                slots=slots,
                collected_fields=collected_fields,
                giga_responses=[slot_json],
            )
            history.append({"query": f"реплика {i+1}", "answer": resp["answer"]})
            if resp.get("slots"):
                slots = resp["slots"]

            if resp.get("step_completed") and resp.get("next_step") == Step.OFFER_EUROPROTOCOL:
                current_step = str(Step.OFFER_EUROPROTOCOL)
                break

        assert current_step == str(Step.OFFER_EUROPROTOCOL), (
            "Должен перейти на offer_europrotocol после заполнения всех слотов"
        )
        assert slots.get("victims") is False
        assert slots.get("participants_count") == 2
        assert slots.get("osago_both") is True

    def test_stop_factor_prevents_offer(self):
        """
        Сценарий: стоп-фактор в step1 не допускает перехода на offer_europrotocol.
        """
        from agent.step_types import Step
        resp = self._backend_call(
            query="есть пострадавшие",
            current_step="step1",
            history=[],
            slots={},
            collected_fields={},
            giga_responses=[
                '{"victims": true, "participants_count": null, '
                '"osago_both": null, "safety_confirmed": null, '
                '"emergency_sign": null, "disagreement": null}'
            ],
        )
        assert resp["step_completed"] is True
        assert resp["next_step"] == Step.CALL_GIBDD

    def test_step2_produces_final_json(self):
        """
        Сценарий: step2 с предзаполненными полями -> final_json.
        """
        all_fields = {
            "date": "15.01.2024",
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
            "circumstances": "А двигался прямо, Б поворачивал.",
            "vehicle_a_fault": "не виноват",
            "vehicle_b_fault": "виноват",
            "scheme": "А у обочины, Б въехал сзади.",
            "signatures_confirmed": True,
        }
        resp = self._backend_call(
            query="всё верно, подтверждаем",
            current_step="step2",
            history=[],
            slots={},
            collected_fields=all_fields,
            giga_responses=["{}"],
        )
        assert resp["step_completed"] is True
        assert resp["final_json"] is not None
        assert resp["final_json"]["type"] == "europrotocol"
        assert resp["final_json"]["data"] == all_fields

    def test_general_mode_not_affected(self):
        """
        Без current_step шаблонный ответ на приветствие возвращается
        ДО создания GigaChat-соединения.
        """
        from agent.core import run_agent
        resp = run_agent(query="привет", current_step=None, history=[])
        assert resp["source"] == "template"
        assert not resp.get("step_completed")

    def test_single_giga_instance_per_call(self):
        """
        Проверяем что _make_giga вызывается ровно один раз на run_agent.
        """
        from agent.core import run_agent
        call_count = []

        original_giga = _make_queue_giga(["{}"])

        def counting_make_giga():
            call_count.append(1)
            return original_giga

        with patch("agent.core._make_giga", side_effect=counting_make_giga):
            run_agent(
                query="есть пострадавшие",
                current_step="step1",
                history=[],
                slots={},
                collected_fields={},
            )

        assert len(call_count) == 1, (
            f"_make_giga должна вызываться ровно 1 раз на run_agent, "
            f"но была вызвана {len(call_count)} раз(а)"
        )

    def test_step2_receives_slots_from_step1(self):
        """
        Слоты из step1 корректно передаются в step2.
        step2 не должен падать при наличии slots.
        """
        slots_from_step1 = {
            "safety_confirmed": True, "emergency_sign": True,
            "victims": False, "participants_count": 2,
            "osago_both": True, "disagreement": False,
        }
        resp = self._backend_call(
            query="начинаем оформление",
            current_step="step2",
            history=[],
            slots=slots_from_step1,
            collected_fields={},
            giga_responses=['{}'],
        )
        assert resp["source"] == "step2"
        assert "answer" in resp
        assert resp["step_completed"] is not None

    def test_offer_europrotocol_our_app_transitions_to_step2(self):
        """
        Выбор '1' (наше приложение) на экране offer переводит в step2.
        """
        from agent.step_types import Step
        from agent.core import run_agent

        resp = run_agent(
            query="1",
            current_step=str(Step.OFFER_EUROPROTOCOL),
            history=[],
            slots={
                "safety_confirmed": True, "emergency_sign": True,
                "victims": False, "participants_count": 2,
                "osago_both": True, "disagreement": False,
            },
            collected_fields={},
        )
        assert resp["step_completed"] is True
        assert resp["next_step"] == Step.STEP2

    def test_offer_europrotocol_paper_transitions_to_fill_external(self):
        """
        Выбор '3' (бумажный бланк) переводит в fill_external.
        """
        from agent.step_types import Step
        from agent.core import run_agent

        resp = run_agent(
            query="3",
            current_step=str(Step.OFFER_EUROPROTOCOL),
            history=[],
            slots={},
            collected_fields={},
        )
        assert resp["step_completed"] is True
        assert resp["next_step"] == Step.FILL_EXTERNAL

    def test_offer_europrotocol_refuse_transitions_to_consultant(self):
        """
        'нет' / 'ГИБДД' переводит в consultant_only.
        """
        from agent.step_types import Step
        from agent.core import run_agent

        resp = run_agent(
            query="нет",
            current_step=str(Step.OFFER_EUROPROTOCOL),
            history=[],
            slots={},
            collected_fields={},
        )
        assert resp["step_completed"] is True
        assert resp["next_step"] == Step.CONSULTANT_ONLY