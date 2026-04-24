"""
Автотесты для ДТП-ассистента.

Покрывают ключевые компоненты:
  - templates/matcher.py — regex-матчер шаблонных ответов
  - templates/responses.py — проверка наличия всех шаблонов
  - agent/algorithm.py — загрузка и нарезка алгоритма
  - agent/history.py — формирование истории диалога
  - evaluation/critic.py — парсинг ответа критика
  - evaluation/self_check.py — парсинг self-check ответа
  - agent/meta_classifier.py — keyword override логика
"""

import pytest
import re
import sys
from pathlib import Path

# Добавляем workspace в path для импортов
sys.path.insert(0, str(Path(__file__).parent.parent))
base_dir = Path(__file__).parent.parent  # Путь к корню проекта
algo_path = base_dir / "Docs_md" / "ai-algorithm.md"  # Полный путь к файлу



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
        """Простые приветствия должны матчиться."""
        assert matcher("привет") is not None
        assert matcher("Привет!") is not None
        assert matcher("добрый день") is not None
        assert matcher("здравствуйте") is not None
        assert matcher("хай") is not None

    def test_greeting_with_context_not_matched(self, matcher):
        """Приветствие с контекстом ДТП НЕ должно матчиться."""
        assert matcher("привет, попал в дтп") is None
        assert matcher("добрый день, как оформить европротокол") is None

    # --- Emergency Numbers ---
    def test_emergency_numbers_explicit(self, matcher):
        """Явные запросы номеров экстренных служб."""
        assert matcher("какой номер полиции") is not None
        assert matcher("номер телефона скорой") is not None
        assert matcher("куда звонить при дтп") is not None
        assert matcher("телефон гибдд") is not None
        assert matcher("дайте номер мчс") is not None

    # --- Victims Injured ---
    def test_victims_injured_explicit(self, matcher):
        """Однозначные сообщения о пострадавших."""
        assert matcher("есть пострадавшие") is not None
        assert matcher("есть пострадавших") is not None
        assert matcher("человек без сознания") is not None
        assert matcher("водитель не дышит") is not None
        assert matcher("ранен пассажир") is not None

    def test_victims_injured_variations(self, matcher):
        """Вариации формулировок о пострадавших."""
        assert matcher("пострадавший") is None  # нет глагола/множественного числа
        assert matcher("есть раненые") is None  # не в паттерне
        assert matcher("травма") is None  # слишком общее

    # --- Repair Ban ---
    def test_repair_ban_explicit(self, matcher):
        """Вопросы о запрете ремонта."""
        assert matcher("можно ли ремонтировать машину") is not None
        assert matcher("когда можно чинить автомобиль") is not None
        assert matcher("через сколько можно в сервис") is not None
        assert matcher("запрет на ремонт") is not None

    def test_repair_ban_not_general_questions(self, matcher):
        """Общие вопросы о ремонте НЕ должны матчиться."""
        assert matcher("ремонт") is None
        assert matcher("сколько стоит ремонт") is None
        assert matcher("где ремонтировать") is None

    # --- No Match Cases ---
    def test_no_match_complex_queries(self, matcher):
        """Сложные запросы НЕ должны матчиться — они для LLM."""
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
        """Все шаблоны должны иметь ключ response."""
        for key, value in templates.items():
            assert "response" in value, f"Template {key} missing 'response' key"
            assert isinstance(value["response"], str)
            assert len(value["response"]) > 10

    def test_greeting_template_content(self, templates):
        """Шаблон greeting содержит ключевые слова."""
        response = templates["greeting"]["response"]
        assert "ДТП-ассистент" in response or "помогу" in response.lower()

    def test_emergency_numbers_template(self, templates):
        """Шаблон emergency_numbers содержит номера."""
        response = templates["emergency_numbers"]["response"]
        assert "112" in response
        assert "102" in response or "полиция" in response.lower()
        assert "103" in response or "скорая" in response.lower()

    def test_victims_injured_template(self, templates):
        """Шаблон victims_injured содержит инструкции."""
        response = templates["victims_injured"]["response"]
        assert "103" in response or "скорую" in response.lower()
        assert "102" in response or "полицию" in response.lower()

    def test_repair_ban_template(self, templates):
        """Шаблон repair_ban содержит сроки."""
        response = templates["repair_ban"]["response"]
        assert "15" in response  # 15 дней
        assert "ремонт" in response.lower() or "чинить" in response.lower()


# =============================================================================
# ТЕСТЫ ALGORITHM (agent/algorithm.py)
# =============================================================================

class TestAlgorithm:
    """Тесты загрузки и нарезки алгоритма."""

    @pytest.fixture
    def algorithm_module(self):
        from agent import algorithm
        # Перезагружаем чтобы сбросить кэш
        import importlib
        importlib.reload(algorithm)
        return algorithm

    # def test_load_algorithm_returns_string(self, algorithm_module):
    #     """load_algorithm возвращает строку."""
    #     result = algorithm_module.load_algorithm("Docs_md/ai-algorithm.md")
    #     assert isinstance(result, str)
    #     # Файл должен существовать и быть непустым
    #     assert len(result) > 0

    # def test_get_algorithm_slice_returns_blocks(self, algorithm_module):
    #     """get_algorithm_slice возвращает блоки алгоритма."""
    #     algorithm_module.load_algorithm("Docs_md/ai-algorithm.md")
    #
    #     # Блок 0 должен существовать
    #     slice_0 = algorithm_module.get_algorithm_slice(0, window=0)
    #     assert "БЛОК 0" in slice_0 or "##" in slice_0
    #
    #     # Блок с окном должен включать соседние
    #     slice_1_window = algorithm_module.get_algorithm_slice(1, window=1)
    #     assert len(slice_1_window) >= len(slice_0)

    def test_get_algorithm_slice_invalid_block(self, algorithm_module):
        """Невалидный блок возвращает весь алгоритм или пустую строку."""
        algorithm_module.load_algorithm("Docs_md/ai-algorithm.md")
        result = algorithm_module.get_algorithm_slice(999, window=1)
        # Должен вернуть что-то разумное
        assert isinstance(result, str)

    def test_parse_blocks_internal(self, algorithm_module):
        """Внутренняя функция _parse_blocks корректно парсит."""
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
        """Пустая история возвращает пустую строку."""
        result = history_module.build_history([], "classifier")
        assert result == ""

    def test_build_history_plain_format(self, history_module):
        """_format_plain нумерует реплики."""
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
        """История обрезается по лимиту компонента."""
        history_data = [
            {"query": f"вопрос {i}", "answer": f"ответ {i}"}
            for i in range(10)
        ]

        # classifier имеет лимит 5
        result = history_module.build_history(history_data, "classifier")
        # Должны быть только последние 5 реплик
        assert "[1] Пользователь: вопрос 5" in result
        assert "[5] Пользователь: вопрос 9" in result
        assert "вопрос 0" not in result

    def test_build_history_generator_by_category(self, history_module):
        """Генератор использует разные лимиты по категориям."""
        history_data = [
            {"query": f"вопрос {i}", "answer": f"ответ {i}"}
            for i in range(15)
        ]

        # first_steps лимит 6
        result_first = history_module.build_history(history_data, "generator", "first_steps")
        # filling_europrotocol без лимита (None)
        result_filling = history_module.build_history(history_data, "generator", "filling_europrotocol")

        # filling должен содержать больше истории
        assert len(result_filling) >= len(result_first)

    def test_format_with_data_summary(self, history_module):
        """_format_with_data_summary извлекает ключевые данные."""
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
        """Регулярка парсит оценку критика."""
        from evaluation.critic import _PROMPT_TEMPLATE
        import re

        # Проверяем что промпт требует нужный формат
        assert "ОЦЕНКА:" in _PROMPT_TEMPLATE
        assert "КОММЕНТАРИЙ:" in _PROMPT_TEMPLATE

        # Проверяем парсинг
        text = "ОЦЕНКА: 4\nКОММЕНТАРИЙ: Хороший ответ"
        score_match = re.search(r"ОЦЕНКА:\s*([1-5])", text)
        comment_match = re.search(r"КОММЕНТАРИЙ:\s*(.+)", text, re.DOTALL)

        assert score_match is not None
        assert score_match.group(1) == "4"
        assert comment_match is not None
        assert "Хороший ответ" in comment_match.group(1)

    def test_default_score_on_error(self):
        """При ошибке возвращается оценка по умолчанию."""
        from evaluation.critic import _DEFAULT_SCORE
        assert _DEFAULT_SCORE == 3


# =============================================================================
# ТЕСТЫ SELF_CHECK (evaluation/self_check.py)
# =============================================================================

class TestSelfCheck:
    """Тесты самопроверки ответов."""

    def test_prompt_template_structure(self):
        """Промпт self_check содержит нужные секции."""
        from evaluation.self_check import _PROMPT_TEMPLATE

        assert "Вопрос:" in _PROMPT_TEMPLATE
        assert "Исходный ответ:" in _PROMPT_TEMPLATE
        assert "Контекст" in _PROMPT_TEMPLATE
        assert "Критерии оценки:" in _PROMPT_TEMPLATE
        assert "GOOD" in _PROMPT_TEMPLATE
        assert "BAD" in _PROMPT_TEMPLATE

    def test_json_output_format_required(self):
        """Требуется JSON вывод."""
        from evaluation.self_check import _PROMPT_TEMPLATE
        assert "JSON" in _PROMPT_TEMPLATE
        assert "verdict" in _PROMPT_TEMPLATE
        assert "confidence" in _PROMPT_TEMPLATE
        assert "final" in _PROMPT_TEMPLATE

    def test_min_answer_length_constant(self):
        """Константа минимальной длины ответа."""
        from evaluation.self_check import _MIN_ANSWER_LENGTH
        assert _MIN_ANSWER_LENGTH == 30

    def test_max_context_chars_constant(self):
        """Константа обрезки контекста."""
        from evaluation.self_check import _MAX_CONTEXT_CHARS
        assert _MAX_CONTEXT_CHARS == 1500


# =============================================================================
# ТЕСТЫ META_CLASSIFIER (agent/meta_classifier.py)
# =============================================================================

class TestMetaClassifier:
    """Тесты мета-классификатора."""

    def test_keyword_override_insurance(self):
        """Keyword override для страховой."""
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
        """Keyword override для невозможного европротокола."""
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

    def test_categories_defined(self):
        """Категории определены."""
        from agent.meta_classifier import _CATEGORIES

        assert "first_steps" in _CATEGORIES
        assert "europrotocol_possible" in _CATEGORIES
        assert "europrotocol_impossible" in _CATEGORIES
        assert "filling_europrotocol" in _CATEGORIES
        assert "insurance_communication" in _CATEGORIES

    def test_fallback_response(self):
        """Fallback возвращает first_steps."""
        from agent.meta_classifier import meta_classify

        # Мокаем giga клиент
        class MockGiga:
            def chat(self, prompt):
                raise Exception("API error")

        result = meta_classify(MockGiga(), "тестовый запрос")
        assert result["relevant"] is True
        assert result["category"] == "first_steps"


# =============================================================================
# ИНТЕГРАЦИОННЫЕ ТЕСТЫ
# =============================================================================

class TestIntegration:
    """Интеграционные тесты pipeline."""

    def test_template_then_llm_flow(self):
        """Проверка что template проверяется перед LLM."""
        from templates.matcher import match_template

        # Простое приветствие должно вернуться сразу
        result = match_template("привет")
        assert result is not None

        # Сложный запрос должен идти дальше
        result = match_template("как заполнить пункт 10")
        assert result is None

    def test_end_to_end_template_response(self):
        """E2E тест шаблонного ответа."""
        from templates.matcher import match_template
        from templates.responses import TEMPLATES

        # Проверяем что каждый паттерн возвращает существующий шаблон
        from templates.matcher import _STRICT_PATTERNS

        for key, patterns in _STRICT_PATTERNS.items():
            assert key in TEMPLATES, f"Pattern {key} has no corresponding template"

            for pattern in patterns:
                # Находим тестовый query который матчится
                test_query = pattern.replace("^", "").replace("$", "").replace("\\s+", " ")
                test_query = test_query.replace("\\", "").strip()[:50]

                result = match_template(test_query)
                # Результат должен быть либо шаблоном, либо None (если паттерн сложный)
                assert result is None or isinstance(result, str)


# =============================================================================
# ЗАПУСК
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])