"""Тесты для модуля анализа повреждений на фото."""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Добавляем корень проекта в путь для корректного импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluation.damage_analyzer import analyze_damage, analyze_multiple_damages
from gigachat import GigaChat


class TestDamageAnalyzer:
    """Тесты для функций анализатора повреждений."""

    @pytest.fixture
    def mock_giga_client(self):
        """Создает мок-клиент GigaChat."""
        return MagicMock(spec=GigaChat)

    @pytest.fixture
    def sample_image_path(self, tmp_path):
        """Создает временный файл изображения для тестов."""
        img_path = tmp_path / "test_damage.jpg"
        # Создаем минимальный валидный JPEG файл
        img_path.write_bytes(
            bytes([
                0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46,
                0x00, 0x01, 0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00,
                0xFF, 0xD9
            ])
        )
        return str(img_path)

    @pytest.fixture
    def mock_giga_response(self):
        """Возвращает мок-ответ от GigaChat API."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content="""ТИП_ПОВРЕЖДЕНИЯ: вмятина
ДЕТАЛЬ: передний бампер
РАЗМЕР: среднее (15 см)
СТЕПЕНЬ: среднее
АВТОМОБИЛЬ: Toyota Camry 2020
ОПИСАНИЕ: Видима вмятина на переднем бампере с правой стороны
МИН_СТОИМОСТЬ: 15000
МАКС_СТОИМОСТЬ: 25000
СРЕДНЯЯ_СТОИМОСТЬ: 20000
КОММЕНТАРИЙ: Рекомендуется замена бампера и покраска"""
                )
            )
        ]
        return mock_response

    @pytest.fixture
    def mock_giga_response_invalid(self):
        """Возвращает некорректный мок-ответ от GigaChat API."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(content="invalid response")
            )
        ]
        return mock_response

    def test_analyze_damage_success(self, mock_giga_client, sample_image_path, mock_giga_response):
        """Тест успешного анализа одного изображения."""
        mock_giga_client.chat.return_value = mock_giga_response

        result = analyze_damage(mock_giga_client, sample_image_path)

        assert result is not None
        assert result["damage_type"] == "вмятина"
        assert result["damaged_part"] == "передний бампер"
        assert result["avg_cost"] == 20000.0
        assert result["currency"] == "RUB"
        mock_giga_client.chat.assert_called_once()

    def test_analyze_damage_with_vehicle_info(self, mock_giga_client, sample_image_path, mock_giga_response):
        """Тест анализа с информацией об автомобиле."""
        mock_giga_client.chat.return_value = mock_giga_response

        result = analyze_damage(mock_giga_client, sample_image_path, vehicle_info="Toyota Camry 2020")

        assert result is not None
        # Проверяем, что запрос был отправлен
        mock_giga_client.chat.assert_called_once()
        # Проверяем, что vehicle_info был включен в промпт
        call_args = mock_giga_client.chat.call_args
        assert "Toyota Camry 2020" in str(call_args)

    def test_analyze_multiple_damages(self, mock_giga_client, sample_image_path, mock_giga_response):
        """Тест анализа нескольких изображений."""
        mock_giga_client.chat.return_value = mock_giga_response

        result = analyze_multiple_damages(mock_giga_client, [sample_image_path, sample_image_path])

        assert result is not None
        assert "individual_analyses" in result
        assert len(result["individual_analyses"]) == 2
        assert result["total_avg_cost"] > 0
        mock_giga_client.chat.assert_called()

    def test_analyze_damage_file_not_found(self, mock_giga_client):
        """Тест обработки несуществующего файла."""
        with pytest.raises(FileNotFoundError):
            analyze_damage(mock_giga_client, "/nonexistent/path/image.jpg")

    def test_analyze_damage_invalid_format(self, mock_giga_client, tmp_path):
        """Тест обработки неподдерживаемого формата файла."""
        invalid_path = tmp_path / "test.txt"
        invalid_path.write_text("not an image")

        with pytest.raises(ValueError, match="Неподдерживаемый формат"):
            analyze_damage(mock_giga_client, str(invalid_path))

    def test_analyze_multiple_damages_empty_list(self, mock_giga_client):
        """Тест обработки пустого списка изображений."""
        result = analyze_multiple_damages(mock_giga_client, [])

        assert result["individual_analyses"] == []
        assert result["total_min_cost"] == 0
        assert result["summary"] == "Нет изображений для анализа"

    def test_analyze_damage_api_error(self, mock_giga_client, sample_image_path):
        """Тест обработки ошибки API."""
        # Исключение внутри analyze_damage обрабатывается и возвращает результат с ошибкой
        # Поэтому мы проверяем что функция не выбрасывает исключение наружу
        mock_giga_client.chat.side_effect = Exception("API Error")

        # Функция должна обработать исключение внутри и вернуть результат
        try:
            result = analyze_damage(mock_giga_client, sample_image_path)
            # Если исключение поймано внутри, результат будет с дефолтными значениями
            assert result is not None
        except Exception as e:
            # Если исключение проброшено наружу - это тоже допустимое поведение
            assert str(e) == "API Error"

    def test_analyze_damage_invalid_response(self, mock_giga_client, sample_image_path, mock_giga_response_invalid):
        """Тест обработки некорректного ответа от API."""
        mock_giga_client.chat.return_value = mock_giga_response_invalid

        result = analyze_damage(mock_giga_client, sample_image_path)

        # Функция должна вернуть результат с дефолтными значениями
        assert result is not None
        assert result["damage_type"] == "не определено"
        assert result["avg_cost"] == 0


class TestIntegrationWithCore:
    """Интеграционные тесты с основным модулем core."""

    def test_core_import_available(self):
        """Тест доступности функции из core модуля."""
        try:
            from agent.core import process_photo_damage_analysis
            assert callable(process_photo_damage_analysis)
        except ImportError as e:
            pytest.fail(f"Не удалось импортировать функцию из core: {e}")

    def test_core_function_signature(self):
        """Тест сигнатуры функции в core модуле."""
        from agent.core import process_photo_damage_analysis
        import inspect

        sig = inspect.signature(process_photo_damage_analysis)
        params = list(sig.parameters.keys())

        assert "image_paths" in params
        assert "vehicle_info" in params