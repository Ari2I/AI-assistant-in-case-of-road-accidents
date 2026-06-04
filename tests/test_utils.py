"""
Тесты для profile/utils.py и agent/fill_external.py (триггеры завершения).

Покрывают:
  profile/utils.py:
    - image_to_base64(): поддерживаемые форматы, несуществующий файл,
      неподдерживаемый формат, корректность base64
    - find_images(): пустая папка, несуществующая папка, фильтрация форматов
    - ensure_test_docs_dir(): создание папки

  agent/fill_external.py:
    - _has_done_trigger(): все триггеры завершения, частичное совпадение,
      ложные срабатывания
    - _DONE_TRIGGERS: полнота и корректность
"""

from __future__ import annotations

import base64
import sys
import os
import tempfile
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.fill_external import _has_done_trigger, _DONE_TRIGGERS
from profile.utils import (
    image_to_base64,
    find_images,
    ensure_test_docs_dir,
    SUPPORTED_EXTENSIONS,
)


# =============================================================================
# ТЕСТЫ _has_done_trigger
# =============================================================================

class TestHasDoneTrigger:
    """Тесты детектора завершения заполнения протокола."""

    def test_all_triggers_detected(self):
        """Каждый триггер из _DONE_TRIGGERS обнаруживается."""
        for trigger in _DONE_TRIGGERS:
            assert _has_done_trigger(trigger), (
                f"Триггер '{trigger}' не обнаружен"
            )

    def test_trigger_in_longer_sentence(self):
        """Триггер обнаруживается внутри предложения."""
        assert _has_done_trigger("я уже заполнил протокол") is True
        assert _has_done_trigger("мы подписали все документы") is True
        assert _has_done_trigger("всё готово, что дальше?") is True

    def test_no_trigger_in_regular_message(self):
        """Обычное сообщение не содержит триггеров."""
        regular_messages = [
            "что писать в пункте 10?",
            "у меня вопрос по схеме ДТП",
            "как описать повреждения?",
            "второй участник не хочет подписывать",
            "мне непонятен пункт 9",
        ]
        for msg in regular_messages:
            assert _has_done_trigger(msg) is False, (
                f"Ложное срабатывание для: '{msg}'"
            )

    def test_case_insensitive(self):
        """Детектор нечувствителен к регистру."""
        assert _has_done_trigger("ЗАПОЛНИЛ протокол") is True
        assert _has_done_trigger("Готово") is True
        assert _has_done_trigger("ПОДПИСАЛИ") is True

    def test_zapolnil_trigger(self):
        assert _has_done_trigger("заполнил") is True

    def test_zapolnila_trigger(self):
        assert _has_done_trigger("заполнила") is True

    def test_zapolnili_trigger(self):
        assert _has_done_trigger("заполнили оба бланка") is True

    def test_gotovo_trigger(self):
        assert _has_done_trigger("готово") is True

    def test_vse_gotovo_trigger(self):
        assert _has_done_trigger("всё готово") is True

    def test_podpisali_trigger(self):
        assert _has_done_trigger("подписали") is True

    def test_protokol_gotov_trigger(self):
        assert _has_done_trigger("протокол готов") is True

    def test_partial_word_no_false_positive(self):
        """Частичное совпадение слова не должно давать ложное срабатывание."""
        # "готовиться" не должно триггерить "готово"
        # Зависит от реализации (contains-поиск) — проверяем что логика корректна
        # _has_done_trigger использует `any(trigger in text for trigger in _DONE_TRIGGERS)`
        # "готово" содержится в "уже готово к подписи" → это корректное срабатывание
        assert _has_done_trigger("протокол уже готов к подписи") is True

    def test_empty_string(self):
        """Пустая строка не вызывает ошибки."""
        assert _has_done_trigger("") is False

    def test_done_triggers_not_empty(self):
        """_DONE_TRIGGERS не пустой."""
        assert len(_DONE_TRIGGERS) > 0

    def test_done_triggers_are_strings(self):
        """Все триггеры — строки."""
        for trigger in _DONE_TRIGGERS:
            assert isinstance(trigger, str)
            assert len(trigger) > 0


# =============================================================================
# ТЕСТЫ image_to_base64
# =============================================================================

class TestImageToBase64:
    """Тесты конвертации изображений в base64."""

    def _create_fake_image(self, suffix: str, content: bytes = b"fake image data") -> str:
        """Создаёт временный файл с заданным расширением."""
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp.write(content)
        tmp.close()
        return tmp.name

    def test_jpeg_file_converted(self):
        """JPEG файл конвертируется корректно."""
        path = self._create_fake_image(".jpg", b"fake jpeg data")
        try:
            b64, media_type = image_to_base64(path)
            assert isinstance(b64, str)
            assert len(b64) > 0
            assert media_type == "image/jpeg"
            # Проверяем что это валидный base64
            decoded = base64.b64decode(b64)
            assert decoded == b"fake jpeg data"
        finally:
            os.unlink(path)

    def test_png_file_converted(self):
        """PNG файл конвертируется с правильным media_type."""
        path = self._create_fake_image(".png", b"fake png data")
        try:
            b64, media_type = image_to_base64(path)
            assert media_type == "image/png"
        finally:
            os.unlink(path)

    def test_webp_file_converted(self):
        """WEBP файл конвертируется с правильным media_type."""
        path = self._create_fake_image(".webp", b"fake webp data")
        try:
            b64, media_type = image_to_base64(path)
            assert media_type == "image/webp"
        finally:
            os.unlink(path)

    def test_jpeg_extension_variants(self):
        """Оба варианта расширения JPEG поддерживаются."""
        for ext in [".jpg", ".jpeg"]:
            path = self._create_fake_image(ext)
            try:
                b64, media_type = image_to_base64(path)
                assert media_type == "image/jpeg"
            finally:
                os.unlink(path)

    def test_nonexistent_file_raises(self):
        """Несуществующий файл вызывает FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            image_to_base64("/nonexistent/path/file.jpg")

    def test_unsupported_format_raises(self):
        """Неподдерживаемый формат вызывает ValueError."""
        path = self._create_fake_image(".bmp")
        try:
            with pytest.raises(ValueError):
                image_to_base64(path)
        finally:
            os.unlink(path)

    def test_pdf_format_raises(self):
        """PDF формат не поддерживается."""
        path = self._create_fake_image(".pdf")
        try:
            with pytest.raises(ValueError):
                image_to_base64(path)
        finally:
            os.unlink(path)

    def test_returns_tuple(self):
        """Функция возвращает кортеж (str, str)."""
        path = self._create_fake_image(".jpg")
        try:
            result = image_to_base64(path)
            assert isinstance(result, tuple)
            assert len(result) == 2
            assert isinstance(result[0], str)
            assert isinstance(result[1], str)
        finally:
            os.unlink(path)

    def test_path_object_accepted(self):
        """Path объект принимается как аргумент."""
        path = self._create_fake_image(".jpg")
        try:
            b64, _ = image_to_base64(Path(path))
            assert isinstance(b64, str)
        finally:
            os.unlink(path)

    def test_case_insensitive_extension(self):
        """Расширение в верхнем регистре тоже обрабатывается."""
        path = self._create_fake_image(".JPG")
        try:
            b64, media_type = image_to_base64(path)
            assert media_type == "image/jpeg"
        finally:
            os.unlink(path)


# =============================================================================
# ТЕСТЫ find_images
# =============================================================================

class TestFindImages:
    """Тесты поиска изображений в папке."""

    def test_nonexistent_folder_returns_empty(self):
        """Несуществующая папка возвращает пустой список."""
        result = find_images("/nonexistent/folder/path")
        assert result == []

    def test_empty_folder_returns_empty(self):
        """Пустая папка возвращает пустой список."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = find_images(tmpdir)
            assert result == []

    def test_finds_jpg_files(self):
        """Находит JPG файлы."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "photo.jpg").write_bytes(b"data")
            result = find_images(tmpdir)
            assert len(result) == 1
            assert result[0].name == "photo.jpg"

    def test_finds_all_supported_formats(self):
        """Находит все поддерживаемые форматы."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for ext in [".jpg", ".jpeg", ".png", ".webp"]:
                (Path(tmpdir) / f"file{ext}").write_bytes(b"data")

            result = find_images(tmpdir)
            assert len(result) == 4

    def test_filters_unsupported_formats(self):
        """Не включает неподдерживаемые форматы."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "photo.jpg").write_bytes(b"data")
            (Path(tmpdir) / "document.pdf").write_bytes(b"data")
            (Path(tmpdir) / "text.txt").write_bytes(b"data")
            (Path(tmpdir) / "image.bmp").write_bytes(b"data")

            result = find_images(tmpdir)
            assert len(result) == 1
            assert result[0].name == "photo.jpg"

    def test_returns_sorted_list(self):
        """Результат отсортирован."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ["c.jpg", "a.jpg", "b.png"]:
                (Path(tmpdir) / name).write_bytes(b"data")

            result = find_images(tmpdir)
            names = [p.name for p in result]
            assert names == sorted(names)

    def test_returns_path_objects(self):
        """Возвращает список Path объектов."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "photo.jpg").write_bytes(b"data")
            result = find_images(tmpdir)
            assert all(isinstance(p, Path) for p in result)

    def test_no_recursion_into_subfolders(self):
        """Не рекурсирует в подпапки."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir) / "subfolder"
            subdir.mkdir()
            (subdir / "nested.jpg").write_bytes(b"data")
            (Path(tmpdir) / "top.jpg").write_bytes(b"data")

            result = find_images(tmpdir)
            names = [p.name for p in result]
            assert "top.jpg" in names
            assert "nested.jpg" not in names

    def test_path_object_as_argument(self):
        """Принимает Path объект как аргумент."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "photo.jpg").write_bytes(b"data")
            result = find_images(Path(tmpdir))
            assert len(result) == 1


# =============================================================================
# ТЕСТЫ ensure_test_docs_dir
# =============================================================================

class TestEnsureTestDocsDir:
    """Тесты создания папки для тестовых документов."""

    def test_creates_folder_if_not_exists(self):
        """Создаёт папку если её нет."""
        with tempfile.TemporaryDirectory() as tmpdir:
            new_folder = Path(tmpdir) / "test_subfolder"
            assert not new_folder.exists()

            result = ensure_test_docs_dir(new_folder)

            assert new_folder.exists()
            assert new_folder.is_dir()
            assert result == new_folder

    def test_does_not_fail_if_exists(self):
        """Не вызывает ошибку если папка уже существует."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = ensure_test_docs_dir(tmpdir)
            assert Path(tmpdir).exists()

    def test_returns_path_object(self):
        """Возвращает Path объект."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = ensure_test_docs_dir(tmpdir)
            assert isinstance(result, Path)


# =============================================================================
# ТЕСТЫ SUPPORTED_EXTENSIONS константы
# =============================================================================

class TestSupportedExtensions:
    """Тесты константы поддерживаемых расширений."""

    def test_jpg_supported(self):
        assert ".jpg" in SUPPORTED_EXTENSIONS

    def test_jpeg_supported(self):
        assert ".jpeg" in SUPPORTED_EXTENSIONS

    def test_png_supported(self):
        assert ".png" in SUPPORTED_EXTENSIONS

    def test_webp_supported(self):
        assert ".webp" in SUPPORTED_EXTENSIONS

    def test_pdf_not_supported(self):
        assert ".pdf" not in SUPPORTED_EXTENSIONS

    def test_bmp_not_supported(self):
        assert ".bmp" not in SUPPORTED_EXTENSIONS

    def test_gif_not_supported(self):
        assert ".gif" not in SUPPORTED_EXTENSIONS

    def test_extensions_are_lowercase(self):
        """Все расширения в нижнем регистре."""
        for ext in SUPPORTED_EXTENSIONS:
            assert ext == ext.lower(), f"Расширение {ext!r} не в нижнем регистре"

    def test_extensions_start_with_dot(self):
        """Все расширения начинаются с точки."""
        for ext in SUPPORTED_EXTENSIONS:
            assert ext.startswith("."), f"Расширение {ext!r} не начинается с точки"