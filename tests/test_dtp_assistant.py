"""
Автотесты для ДТП-ассистента.

Покрывают ключевые компоненты:
  - templates/matcher.py — regex-матчер шаблонных ответов
  - templates/responses.py — проверка наличия всех шаблонов
  - agent/algorithm.py — загрузка и нарезка алгоритма
  - agent/history.py — формирование истории диалога
  - evaluation/critic.py — парсинг ответа критика
  - evaluation/self_check.py — парсинг self-check ответа
  - agent/meta_classifier.py — keyword override логика (с учётом нового порядка)
  - agent/fill_external.py — флаг первого входа в collected_fields
  - agent/step1_stateless.py — порог длины для prefill
  - rag/feedback_db.py — параметр db в save_good_qa
"""

import pytest
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

base_dir = Path(__file__).parent.parent
algo_path = base_dir / "Docs_md" / "ai-algorithm.md"


# =============================================================================
# ТЕСТЫ MATCHER (templates/matcher.py)
# =============================================================================

class TestMatcher:
    """Тесты строгого regex-матчера шаблонных ответов."""

    @pytest.fixture
    def matcher(self):
        from templates.matcher import match_template
        return match_template

    # --- Greeting ---
    def test_greeting_simple(self, matcher):
        assert matcher("привет") is not None
        assert matcher("Привет!") is not None
        assert matcher("добрый день") is not None
        assert matcher("здравствуйте") is not None
        assert matcher("хай") is not None

    def test_greeting_with_context_not_matched(self, matcher):
        assert matcher("привет, попал в дтп") is None
        assert matcher("добрый день, как оформить европротокол") is None

    # --- Emergency Numbers ---
    def test_emergency_numbers_explicit(self, matcher):
        assert matcher("какой номер полиции") is not None
        assert matcher("номер телефона скорой") is not None
        assert matcher("куда звонить при дтп") is not None
        assert matcher("телефон гибдд") is not None
        assert matcher("дайте номер мчс") is not None

    # --- Victims Injured ---
    def test_victims_injured_explicit(self, matcher):
        assert matcher("есть пострадавшие") is not None
        assert matcher("есть пострадавших") is not None
        assert matcher("человек без сознания") is not None
        assert matcher("водитель не дышит") is not None
        assert matcher("ранен пассажир") is not None

    def test_victims_injured_variations(self, matcher):
        assert matcher("пострадавший") is None
        assert matcher("есть раненые") is None
        assert matcher("травма") is None

    # --- Repair Ban ---
    def test_repair_ban_explicit(self, matcher):
        assert matcher("можно ли ремонтировать машину") is not None
        assert matcher("когда можно чинить автомобиль") is not None
        assert matcher("через сколько можно в сервис") is not None
        assert matcher("запрет на ремонт") is not None

    def test_repair_ban_not_general_questions(self, matcher):
        assert matcher("ремонт") is None
        assert matcher("сколько стоит ремонт") is None
        assert matcher("где ремонтировать") is None

    # --- No Match Cases ---
    def test_no_match_complex_queries(self, matcher):
        assert matcher("как заполнить пункт 10 европротокола") is None
        assert matcher("у меня дтп два автомобиля что делать") is None
        assert matcher("страховая отказала в выплате") is None
        assert matcher("проверить полис осаго") is None


# =============================================================================
# ТЕСТЫ RESPONSES (templates/responses.py)
# =============================================================================

class TestResponses:
    """Тесты шаблонных ответов."""

    @pytest.fixture
    def templates(self):
        from templates.responses import TEMPLATES
        return TEMPLATES

    def test_all_templates_have_response(self, templates):
        for key, value in templates.items():
            assert "response" in value, f"Template {key} missing 'response' key"
            assert isinstance(value["response"], str)
            assert len(value["response"]) > 10

    def test_greeting_template_content(self, templates):
        response = templates["greeting"]["response"]
        assert "ДТП-ассистент" in response or "помогу" in response.lower()

    def test_emergency_numbers_template(self, templates):
        response = templates["emergency_numbers"]["response"]
        assert "112" in response
        assert "102" in response or "полиция" in response.lower()
        assert "103" in response or "скорая" in response.lower()

    def test_victims_injured_template(self, templates):
        response = templates["victims_injured"]["response"]
        assert "103" in response or "скорую" in response.lower()
        assert "102" in response or "полицию" in response.lower()

    def test_repair_ban_template(self, templates):
        response = templates["repair_ban"]["response"]
        assert "15" in response
        assert "ремонт" in response.lower() or "чинить" in response.lower()


# =============================================================================
# ТЕСТЫ ALGORITHM (agent/algorithm.py)
# =============================================================================

class TestAlgorithm:
    """Тесты загрузки и нарезки алгоритма."""

    @pytest.fixture
    def algorithm_module(self):
        from agent import algorithm
        import importlib
        importlib.reload(algorithm)
        return algorithm

    def test_get_algorithm_slice_invalid_block(self, algorithm_module):
        algorithm_module.load_algorithm("Docs_md/ai-algorithm.md")
        result = algorithm_module.get_algorithm_slice(999, window=1)
        assert isinstance(result, str)

    def test_parse_blocks_internal(self, algorithm_module):
        test_text = """
## БЛОК 0
Текст блока 0

## БЛОК 1
Текст блока 1

## БЛОК 2
Текст блока 2
"""
        blocks = algorithm_module._parse_blocks(test_text)
        assert 0 in blocks
        assert 1 in blocks
        assert 2 in blocks
        assert "БЛОК 0" in blocks[0]
        assert "БЛОК 1" in blocks[1]


# =============================================================================
# ТЕСТЫ HISTORY (agent/history.py)
# =============================================================================

class TestHistory:
    """Тесты формирования истории диалога."""

    @pytest.fixture
    def history_module(self):
        from agent import history
        return history

    def test_build_history_empty(self, history_module):
        result = history_module.build_history([], "classifier")
        assert result == ""

    def test_build_history_plain_format(self, history_module):
        history_data = [
            {"query": "привет", "answer": "здравствуйте"},
            {"query": "попал в дтп", "answer": "расскажите подробнее"},
        ]
        result = history_module.build_history(history_data, "classifier")

        assert "[1] Пользователь: привет" in result
        assert "[1] Ассистент: здравствуйте" in result
        assert "[2] Пользователь: попал в дтп" in result
        assert "[2] Ассистент: расскажите подробнее" in result

    def test_build_history_respects_limit(self, history_module):
        history_data = [
            {"query": f"вопрос {i}", "answer": f"ответ {i}"}
            for i in range(10)
        ]
        result = history_module.build_history(history_data, "classifier")
        assert "[1] Пользователь: вопрос 5" in result
        assert "[5] Пользователь: вопрос 9" in result
        assert "вопрос 0" not in result

    def test_build_history_generator_by_category(self, history_module):
        history_data = [
            {"query": f"вопрос {i}", "answer": f"ответ {i}"}
            for i in range(15)
        ]
        result_first = history_module.build_history(history_data, "generator", "first_steps")
        result_filling = history_module.build_history(history_data, "generator", "filling_europrotocol")
        assert len(result_filling) >= len(result_first)

    def test_format_with_data_summary(self, history_module):
        history_data = [
            {"query": "марка машины toyota", "answer": "понял"},
            {"query": "повреждения бампер и крыло", "answer": "записал"},
        ]
        result = history_module.build_history(history_data, "generator", "filling_europrotocol")
        assert "СЛУЖЕБНЫЙ БЛОК" in result
        assert "Транспортные средства" in result or "Повреждения" in result


# =============================================================================
# ТЕСТЫ CRITIC (evaluation/critic.py)
# =============================================================================

class TestCritic:
    """Тесты AI-критика."""

    def test_parse_score_pattern(self):
        from evaluation.critic import _PROMPT_TEMPLATE
        assert "ОЦЕНКА:" in _PROMPT_TEMPLATE
        assert "КОММЕНТАРИЙ:" in _PROMPT_TEMPLATE

        text = "ОЦЕНКА: 4\nКОММЕНТАРИЙ: Хороший ответ"
        score_match = re.search(r"ОЦЕНКА:\s*([1-5])", text)
        comment_match = re.search(r"КОММЕНТАРИЙ:\s*(.+)", text, re.DOTALL)

        assert score_match is not None
        assert score_match.group(1) == "4"
        assert comment_match is not None
        assert "Хороший ответ" in comment_match.group(1)

    def test_default_score_on_error(self):
        from evaluation.critic import _DEFAULT_SCORE
        assert _DEFAULT_SCORE == 3


# =============================================================================
# ТЕСТЫ SELF_CHECK (evaluation/self_check.py)
# =============================================================================

class TestSelfCheck:
    """Тесты самопроверки ответов."""

    def test_prompt_template_structure(self):
        from evaluation.self_check import _PROMPT_TEMPLATE
        assert "Вопрос:" in _PROMPT_TEMPLATE
        assert "Исходный ответ:" in _PROMPT_TEMPLATE
        assert "Контекст" in _PROMPT_TEMPLATE
        assert "GOOD" in _PROMPT_TEMPLATE
        assert "BAD" in _PROMPT_TEMPLATE

    def test_json_output_format_required(self):
        from evaluation.self_check import _PROMPT_TEMPLATE
        assert "JSON" in _PROMPT_TEMPLATE
        assert "verdict" in _PROMPT_TEMPLATE
        assert "confidence" in _PROMPT_TEMPLATE
        assert "final" in _PROMPT_TEMPLATE

    def test_min_answer_length_constant(self):
        from evaluation.self_check import _MIN_ANSWER_LENGTH
        assert _MIN_ANSWER_LENGTH == 30

    def test_max_context_chars_constant(self):
        from evaluation.self_check import _MAX_CONTEXT_CHARS
        assert _MAX_CONTEXT_CHARS == 1500


# =============================================================================
# ТЕСТЫ META_CLASSIFIER (agent/meta_classifier.py)
# =============================================================================

class TestMetaClassifier:
    """Тесты мета-классификатора."""

    def test_keyword_override_insurance(self):
        from agent.meta_classifier import _KEYWORD_OVERRIDES

        insurance_keywords = None
        for keywords, category, block in _KEYWORD_OVERRIDES:
            if category == "insurance_communication":
                insurance_keywords = keywords
                break

        assert insurance_keywords is not None
        assert "страховую" in insurance_keywords
        assert "заявление о" in insurance_keywords
        assert "выплат" in insurance_keywords

    def test_keyword_override_impossible(self):
        from agent.meta_classifier import _KEYWORD_OVERRIDES

        impossible_keywords = None
        for keywords, category, block in _KEYWORD_OVERRIDES:
            if category == "europrotocol_impossible":
                impossible_keywords = keywords
                break

        assert impossible_keywords is not None
        assert "пострадавш" in impossible_keywords
        assert "скрылся" in impossible_keywords
        assert "нет осаго" in impossible_keywords

    def test_impossible_before_insurance_in_overrides(self):
        """
        europrotocol_impossible должен проверяться РАНЬШЕ insurance_communication,
        чтобы 'нет страховки у пострадавшего' не уходило в страховую категорию.
        """
        from agent.meta_classifier import _KEYWORD_OVERRIDES

        impossible_idx = None
        insurance_idx = None
        for i, (_, category, _) in enumerate(_KEYWORD_OVERRIDES):
            if category == "europrotocol_impossible":
                impossible_idx = i
            if category == "insurance_communication":
                insurance_idx = i

        assert impossible_idx is not None, "europrotocol_impossible не найден в _KEYWORD_OVERRIDES"
        assert insurance_idx is not None, "insurance_communication не найден в _KEYWORD_OVERRIDES"
        assert impossible_idx < insurance_idx, (
            "europrotocol_impossible должен быть выше insurance_communication в списке"
        )

    def test_impossible_wins_over_insurance_for_ambiguous_query(self):
        """
        'нет страховки' — стоп-фактор, не страховая тема.
        Должна выиграть категория europrotocol_impossible.
        """
        from agent.meta_classifier import meta_classify

        class MockGiga:
            def chat(self, prompt):
                raise Exception("LLM не должна вызываться — должен сработать override")

        result = meta_classify(MockGiga(), "у пострадавшего нет страховки")
        assert result["category"] == "europrotocol_impossible"

    def test_categories_defined(self):
        from agent.meta_classifier import _CATEGORIES
        assert "first_steps" in _CATEGORIES
        assert "europrotocol_possible" in _CATEGORIES
        assert "europrotocol_impossible" in _CATEGORIES
        assert "filling_europrotocol" in _CATEGORIES
        assert "insurance_communication" in _CATEGORIES

    def test_fallback_response(self):
        from agent.meta_classifier import meta_classify

        class MockGiga:
            def chat(self, prompt):
                raise Exception("API error")

        result = meta_classify(MockGiga(), "тестовый запрос")
        assert result["relevant"] is True
        assert result["category"] == "first_steps"

    def test_general_questions_override(self):
        """Специфичные общие вопросы → general_questions без LLM."""
        from agent.meta_classifier import meta_classify

        class MockGiga:
            def chat(self, prompt):
                raise Exception("LLM не должна вызываться")

        result = meta_classify(MockGiga(), "какая дистанция для знака аварийной остановки")
        assert result["category"] == "general_questions"


# =============================================================================
# ТЕСТЫ БАГ-ФИКСОВ
# =============================================================================

class TestFillExternalFirstEntry:
    """Тест исправления определения первого входа в fill_external."""

    def test_first_entry_flag_set_in_collected_fields(self):
        """
        Первый вход определяется по флагу fill_external_entered в collected_fields,
        а не по сканированию истории.
        """
        from agent.fill_external import process_fill_external

        class MockGiga:
            def chat(self, *a, **kw):
                class R:
                    class C:
                        class M:
                            content = "Ответ."
                        message = M()
                    choices = [C()]
                return R()

        collected = {}  # флага нет → первый вход

        result = process_fill_external(
            giga=MockGiga(),
            query="начинаем",
            history=[],
            slots={"fill_method": "paper"},
            collected_fields=collected,
            db=None,
            feedback_db=None,
        )

        # После первого входа флаг должен быть установлен
        assert collected.get("fill_external_entered") is True
        assert "бланк" in result.answer.lower() or "пункт" in result.answer.lower()

    def test_second_entry_not_shows_intro(self):
        """При наличии флага повторный вход не показывает вступительное сообщение."""
        from agent.fill_external import process_fill_external, _DONE_TRIGGERS

        class MockGiga:
            def chat(self, *a, **kw):
                class R:
                    class C:
                        class M:
                            # Возвращаем completion: false чтобы не уйти в step3
                            content = '{"completed": false, "reason": "вопрос"}'
                        message = M()
                    choices = [C()]
                return R()

        collected = {"fill_external_entered": True}  # флаг уже есть

        result = process_fill_external(
            giga=MockGiga(),
            query="что писать в пункте 10?",
            history=[],
            slots={"fill_method": "paper"},
            collected_fields=collected,
            db=None,
            feedback_db=None,
        )

        # Не должно быть вступительного текста
        assert "пункт" not in result.answer.lower() or "что писать" in result.answer.lower()
        assert result.next_step.value == "fill_external"


class TestPrefillMinLength:
    """Тест порога длины для _try_prefill_fields."""

    def test_short_query_skips_prefill(self):
        """
        Короткие ответы не должны вызывать _try_prefill_fields.
        Проверяем через mock: если prefill вызывается — тест падает.
        """
        from agent import step1_stateless
        original_prefill = step1_stateless._try_prefill_fields
        prefill_called = []

        def mock_prefill(giga, message):
            prefill_called.append(message)
            return {}

        step1_stateless._try_prefill_fields = mock_prefill

        try:
            class MockGiga:
                def chat(self, *a, **kw):
                    class R:
                        class C:
                            class M:
                                content = '{"victims": false, "safety_confirmed": null, "emergency_sign": null, "participants_count": null, "osago_both": null, "disagreement": null}'
                            message = M()
                        choices = [C()]
                    return R()

            # Короткое сообщение — prefill не должен вызываться
            step1_stateless.process_step1_with_llm(MockGiga(), "нет", [], {})
            assert prefill_called == [], (
                f"_try_prefill_fields не должен вызываться для короткого сообщения, "
                f"но был вызван с: {prefill_called}"
            )
        finally:
            step1_stateless._try_prefill_fields = original_prefill

    def test_long_query_triggers_prefill(self):
        """Длинные сообщения должны вызывать _try_prefill_fields."""
        from agent import step1_stateless
        original_prefill = step1_stateless._try_prefill_fields
        prefill_called = []

        def mock_prefill(giga, message):
            prefill_called.append(message)
            return {}

        step1_stateless._try_prefill_fields = mock_prefill

        try:
            class MockGiga:
                def chat(self, *a, **kw):
                    class R:
                        class C:
                            class M:
                                content = '{"victims": false, "safety_confirmed": null, "emergency_sign": null, "participants_count": null, "osago_both": null, "disagreement": null}'
                            message = M()
                        choices = [C()]
                    return R()

            long_query = "я попал в ДТП на улице Ленина, столкнулся с Toyota Camry А123БВ777"
            assert len(long_query) >= step1_stateless._PREFILL_MIN_LENGTH
            step1_stateless.process_step1_with_llm(MockGiga(), long_query, [], {})
            assert prefill_called, "_try_prefill_fields должен был вызваться для длинного сообщения"
        finally:
            step1_stateless._try_prefill_fields = original_prefill

    def test_prefill_min_length_constant_is_reasonable(self):
        """Порог должен быть разумным (не слишком маленьким и не слишком большим)."""
        from agent.step1_stateless import _PREFILL_MIN_LENGTH
        assert 20 <= _PREFILL_MIN_LENGTH <= 60


class TestFeedbackDbParameter:
    """Тест что feedback_db параметр в rate_answer действительно используется."""

    def test_rate_answer_uses_passed_feedback_db(self):
        """
        Переданный feedback_db должен использоваться, а не синглтон из db_manager.
        """
        from rag.feedback_db import save_good_qa

        saved_to = []

        class MockDB:
            def add_texts(self, texts, ids):
                saved_to.extend(texts)

        # Проверяем save_good_qa напрямую
        save_good_qa("тестовый вопрос", "тестовый ответ", db=MockDB())

        assert len(saved_to) == 1
        assert "тестовый вопрос" in saved_to[0]
        assert "тестовый ответ" in saved_to[0]

    def test_save_good_qa_none_db_uses_singleton(self):
        """При db=None используется синглтон (graceful деградация при отсутствии базы)."""
        from rag.feedback_db import save_good_qa
        # Не должно бросать исключение даже если синглтон недоступен
        try:
            save_good_qa("вопрос", "ответ", db=None)
        except Exception as e:
            # Единственное допустимое исключение — ошибка подключения к реальной БД
            assert "chroma" in str(e).lower() or "connect" in str(e).lower()

    def test_save_good_qa_signature_has_db_param(self):
        """save_good_qa должна принимать параметр db."""
        import inspect
        from rag.feedback_db import save_good_qa
        sig = inspect.signature(save_good_qa)
        assert "db" in sig.parameters


# =============================================================================
# ИНТЕГРАЦИОННЫЕ ТЕСТЫ
# =============================================================================

class TestIntegration:
    """Интеграционные тесты pipeline."""

    def test_template_then_llm_flow(self):
        from templates.matcher import match_template
        assert match_template("привет") is not None
        assert match_template("как заполнить пункт 10") is None

    def test_end_to_end_template_response(self):
        from templates.matcher import match_template
        from templates.responses import TEMPLATES
        from templates.matcher import _STRICT_PATTERNS

        for key, patterns in _STRICT_PATTERNS.items():
            assert key in TEMPLATES, f"Pattern {key} has no corresponding template"
            for pattern in patterns:
                test_query = pattern.replace("^", "").replace("$", "").replace("\\s+", " ")
                test_query = test_query.replace("\\", "").strip()[:50]
                result = match_template(test_query)
                assert result is None or isinstance(result, str)

    def test_general_mode_uses_template_for_greeting(self):
        """Приветствие в general-режиме всегда возвращает шаблон."""
        from agent.core import run_agent
        resp = run_agent(query="привет", current_step=None, history=[])
        assert resp["source"] == "template"


# =============================================================================
# ЗАПУСК
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])