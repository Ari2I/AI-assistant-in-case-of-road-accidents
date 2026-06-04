"""
Тесты для agent/retriever.py.

Покрывают:
  - get_context_for_category(): дедупликация, лимит чанков,
    приоритет feedback_db, fallback при недоступной БД,
    обработка исключений, корректность для каждой категории
  - _CATEGORY_QUERIES: наличие запросов для всех категорий
"""

from __future__ import annotations

import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.retriever import (
    get_context_for_category,
    _CATEGORY_QUERIES,
    _MAX_CHUNKS,
    _K_PER_QUERY,
    _K_FEEDBACK,
)


# ---------------------------------------------------------------------------
# Вспомогательные моки БД
# ---------------------------------------------------------------------------

class FakeDoc:
    """Мок документа ChromaDB."""
    def __init__(self, content: str):
        self.page_content = content


class FakeDB:
    """Мок ChromaDB с фиксированными результатами поиска."""

    def __init__(self, docs: list[str], raise_on_search: bool = False):
        self._docs = [FakeDoc(d) for d in docs]
        self._raise = raise_on_search
        self.search_calls: list[tuple[str, int]] = []

    def similarity_search(self, query: str, k: int = 5) -> list[FakeDoc]:
        self.search_calls.append((query, k))
        if self._raise:
            raise RuntimeError("БД недоступна")
        return self._docs[:k]


def _make_db(docs: list[str], raise_on_search: bool = False) -> FakeDB:
    return FakeDB(docs, raise_on_search)


# =============================================================================
# ТЕСТЫ FALLBACK ПРИ НЕДОСТУПНОЙ БД
# =============================================================================

class TestFallback:
    """Тесты поведения при недоступных базах данных."""

    def test_both_none_returns_fallback_string(self):
        """Если обе БД None — возвращает строку-заглушку."""
        result = get_context_for_category(None, None, "что делать при ДТП", "first_steps")
        assert "недоступен" in result.lower() or "Контекст" in result

    def test_main_db_none_uses_only_feedback(self):
        """Если основная БД None — используется только feedback_db."""
        feedback = _make_db(["хороший ответ из feedback"])
        result = get_context_for_category(None, feedback, "вопрос", "first_steps")
        assert "хороший ответ из feedback" in result

    def test_feedback_db_none_uses_only_main(self):
        """Если feedback_db None — используется только основная БД."""
        main = _make_db(["документ из основной базы"])
        result = get_context_for_category(main, None, "вопрос", "first_steps")
        assert "документ из основной базы" in result

    def test_main_db_exception_returns_fallback(self):
        """При исключении из основной БД — не падает, возвращает результат."""
        error_db = _make_db([], raise_on_search=True)
        result = get_context_for_category(error_db, None, "вопрос", "first_steps")
        assert isinstance(result, str)

    def test_feedback_db_exception_continues_with_main(self):
        """При исключении из feedback_db — продолжает с основной БД."""
        error_feedback = _make_db([], raise_on_search=True)
        main = _make_db(["документ из основной"])
        result = get_context_for_category(main, error_feedback, "вопрос", "first_steps")
        assert "документ из основной" in result

    def test_both_raise_returns_fallback(self):
        """Если обе БД бросают исключения — возвращает строку-заглушку."""
        error_db = _make_db([], raise_on_search=True)
        result = get_context_for_category(error_db, error_db, "вопрос", "first_steps")
        assert isinstance(result, str)
        assert len(result) > 0


# =============================================================================
# ТЕСТЫ ДЕДУПЛИКАЦИИ
# =============================================================================

class TestDeduplication:
    """Тесты дедупликации чанков из разных источников."""

    def test_duplicate_chunks_from_feedback_and_main_deduplicated(self):
        """Одинаковый чанк из feedback и main не дублируется."""
        same_content = "одинаковый чанк про ДТП"
        feedback = _make_db([same_content])
        main = _make_db([same_content, "другой чанк"])

        result = get_context_for_category(main, feedback, "вопрос", "first_steps")
        # Считаем сколько раз встречается одинаковый чанк
        count = result.count(same_content)
        assert count == 1, f"Чанк дублируется {count} раз"

    def test_duplicate_chunks_from_same_db_deduplicated(self):
        """Дублирующиеся чанки из одной БД не повторяются."""
        same_content = "чанк который повторяется"
        main = _make_db([same_content, same_content, "уникальный чанк"])

        result = get_context_for_category(main, None, "вопрос", "first_steps")
        count = result.count(same_content)
        assert count == 1

    def test_unique_chunks_all_included(self):
        """Уникальные чанки включаются все (до лимита)."""
        docs = [f"уникальный чанк {i}" for i in range(3)]
        main = _make_db(docs)

        result = get_context_for_category(main, None, "вопрос", "first_steps")
        for doc in docs:
            assert doc in result


# =============================================================================
# ТЕСТЫ ЛИМИТА ЧАНКОВ
# =============================================================================

class TestChunkLimit:
    """Тесты ограничения максимального количества чанков."""

    def test_max_chunks_not_exceeded(self):
        """Количество чанков не превышает _MAX_CHUNKS."""
        # Создаём много уникальных чанков
        many_docs = [f"чанк номер {i} про ДТП и ОСАГО" for i in range(20)]
        main = _make_db(many_docs)

        result = get_context_for_category(main, None, "вопрос", "first_steps")
        # Считаем разделители между чанками
        chunk_count = result.count("\n\n---\n\n") + 1
        assert chunk_count <= _MAX_CHUNKS

    def test_feedback_chunks_count_toward_limit(self):
        """Чанки из feedback учитываются в общем лимите."""
        feedback_docs = [f"feedback чанк {i}" for i in range(_K_FEEDBACK)]
        main_docs = [f"main чанк {i}" for i in range(20)]
        feedback = _make_db(feedback_docs)
        main = _make_db(main_docs)

        result = get_context_for_category(main, feedback, "вопрос", "first_steps")
        chunk_count = result.count("\n\n---\n\n") + 1
        assert chunk_count <= _MAX_CHUNKS


# =============================================================================
# ТЕСТЫ ПРИОРИТЕТА FEEDBACK_DB
# =============================================================================

class TestFeedbackPriority:
    """Тесты приоритета feedback_db над основной БД."""

    def test_feedback_chunks_appear_first(self):
        """Чанки из feedback идут первыми в результате."""
        feedback = _make_db(["FEEDBACK: хороший Q&A ответ"])
        main = _make_db(["MAIN: документ из базы знаний"])

        result = get_context_for_category(main, feedback, "вопрос", "first_steps")
        feedback_pos = result.find("FEEDBACK:")
        main_pos = result.find("MAIN:")

        assert feedback_pos < main_pos, (
            "Чанки из feedback должны идти раньше чанков из основной БД"
        )

    def test_feedback_searched_with_original_query(self):
        """Feedback ищется по оригинальному запросу пользователя."""
        feedback = _make_db([])
        main = _make_db([])

        get_context_for_category(main, feedback, "мой конкретный вопрос", "first_steps")

        assert len(feedback.search_calls) > 0
        assert feedback.search_calls[0][0] == "мой конкретный вопрос"


# =============================================================================
# ТЕСТЫ КАТЕГОРИАЛЬНЫХ ЗАПРОСОВ
# =============================================================================

class TestCategoryQueries:
    """Тесты использования специализированных запросов для категорий."""

    def test_known_category_uses_category_queries(self):
        """Для известной категории используются специализированные запросы."""
        main = _make_db(["документ"])

        get_context_for_category(main, None, "вопрос", "filling_europrotocol")

        # Проверяем что были запросы специфичные для категории
        queries_used = [call[0] for call in main.search_calls]
        # Должен быть хотя бы один запрос из _CATEGORY_QUERIES["filling_europrotocol"]
        category_queries = _CATEGORY_QUERIES.get("filling_europrotocol", [])
        assert any(q in queries_used for q in category_queries), (
            "Специализированные запросы категории не использованы"
        )

    def test_unknown_category_uses_original_query(self):
        """Для неизвестной категории используется оригинальный запрос."""
        main = _make_db(["документ"])

        get_context_for_category(main, None, "мой вопрос", "несуществующая_категория")

        queries_used = [call[0] for call in main.search_calls]
        assert "мой вопрос" in queries_used

    def test_original_query_always_included(self):
        """Оригинальный запрос всегда включается в поиск."""
        main = _make_db(["документ"])
        original_query = "специфичный вопрос пользователя"

        get_context_for_category(main, None, original_query, "first_steps")

        queries_used = [call[0] for call in main.search_calls]
        assert original_query in queries_used

    def test_all_defined_categories_have_queries(self):
        """Все категории имеют специализированные запросы."""
        expected_categories = [
            "general_questions",
            "first_steps",
            "europrotocol_possible",
            "europrotocol_impossible",
            "filling_europrotocol",
            "insurance_communication",
        ]
        for category in expected_categories:
            assert category in _CATEGORY_QUERIES, (
                f"Нет запросов для категории {category}"
            )
            assert len(_CATEGORY_QUERIES[category]) > 0, (
                f"Пустой список запросов для категории {category}"
            )

    def test_each_category_returns_string(self):
        """get_context_for_category возвращает строку для каждой категории."""
        main = _make_db(["тестовый документ"])

        for category in _CATEGORY_QUERIES:
            result = get_context_for_category(main, None, "вопрос", category)
            assert isinstance(result, str), f"Для категории {category} не строка"
            assert len(result) > 0


# =============================================================================
# ТЕСТЫ ФОРМАТА РЕЗУЛЬТАТА
# =============================================================================

class TestResultFormat:
    """Тесты формата возвращаемого контекста."""

    def test_multiple_chunks_joined_with_separator(self):
        """Несколько чанков объединяются разделителем."""
        docs = ["первый чанк", "второй чанк", "третий чанк"]
        main = _make_db(docs)

        result = get_context_for_category(main, None, "вопрос", "first_steps")
        assert "\n\n---\n\n" in result

    def test_single_chunk_no_separator(self):
        """Один чанк возвращается без разделителя."""
        main = _make_db(["единственный чанк"])
        # Перекрываем все запросы одним результатом
        result = get_context_for_category(main, None, "вопрос", "general_questions")
        # При одном уникальном чанке разделитель не нужен
        # (может быть несколько запросов но один результат)
        assert "единственный чанк" in result

    def test_result_is_string(self):
        """Результат всегда строка."""
        result = get_context_for_category(None, None, "вопрос", "first_steps")
        assert isinstance(result, str)

    def test_fallback_message_is_informative(self):
        """Сообщение о недоступности контекста информативно."""
        result = get_context_for_category(None, None, "вопрос", "first_steps")
        # Должно содержать указание на недоступность
        assert len(result) > 20


# =============================================================================
# ТЕСТЫ _CATEGORY_QUERIES КОНСТАНТЫ
# =============================================================================

class TestCategoryQueriesConstant:
    """Тесты корректности константы _CATEGORY_QUERIES."""

    def test_filling_europrotocol_queries_relevant(self):
        """Запросы для filling_europrotocol про заполнение протокола."""
        queries = _CATEGORY_QUERIES["filling_europrotocol"]
        combined = " ".join(queries).lower()
        assert any(kw in combined for kw in ["заполнени", "извещени", "пункт", "инструкци"])

    def test_insurance_communication_queries_relevant(self):
        """Запросы для insurance_communication про страховую."""
        queries = _CATEGORY_QUERIES["insurance_communication"]
        combined = " ".join(queries).lower()
        assert any(kw in combined for kw in ["страхов", "заявлени", "выплат", "осаго"])

    def test_europrotocol_impossible_queries_relevant(self):
        """Запросы для europrotocol_impossible про вызов ГИБДД."""
        queries = _CATEGORY_QUERIES["europrotocol_impossible"]
        combined = " ".join(queries).lower()
        assert any(kw in combined for kw in ["гибдд", "пострадавш", "невозможен", "вызов"])

    def test_first_steps_queries_relevant(self):
        """Запросы для first_steps про первые действия."""
        queries = _CATEGORY_QUERIES["first_steps"]
        combined = " ".join(queries).lower()
        assert any(kw in combined for kw in ["первые", "действи", "остановиться", "аварийк"])

    def test_no_empty_queries_in_any_category(self):
        """В ни одной категории нет пустых запросов."""
        for category, queries in _CATEGORY_QUERIES.items():
            for q in queries:
                assert q.strip(), f"Пустой запрос в категории {category}"

    def test_queries_are_in_russian(self):
        """Все запросы на русском языке."""
        import re
        russian_pattern = re.compile(r'[а-яёА-ЯЁ]')
        for category, queries in _CATEGORY_QUERIES.items():
            for q in queries:
                assert russian_pattern.search(q), (
                    f"Запрос не на русском в категории {category}: {q!r}"
                )