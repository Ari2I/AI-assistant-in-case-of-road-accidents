"""
SaluteSpeech клиент для синтеза и распознавания речи.

Поддерживает:
- TTS (text-to-speech): синтез речи из текста
- STT (speech-to-text): распознавание речи в текст
- Прямое использование токена SPEECH_AUTH без кэширования
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from utils.catalog import validate_tts_voice, validate_tts_format, validate_stt_model
from config import SPEECH_AUTH

logger = logging.getLogger(__name__)

# URL API SaluteSpeech
_DEFAULT_TTS_URL = "https://smartspeech.sber.ru/rest/v1/text:synthesize"
_DEFAULT_STT_URL = "https://smartspeech.sber.ru/rest/v1/stt"

# Дефолтный голос для TTS
_DEFAULT_VOICE = "Nec_24000"

# Формат аудио по умолчанию
_DEFAULT_AUDIO_FORMAT = "opus"

# Модель распознавания по умолчанию
_DEFAULT_RECOGNITION_MODEL = "general"


class SaluteSpeechClient:
    """
    Клиент для работы с SaluteSpeech API.

    Использует токен SPEECH_AUTH напрямую без кэширования и перезапроса.
    """

    def __init__(
        self,
        tts_url: str | None = None,
        stt_url: str | None = None,
        default_voice: str | None = None,
        default_format: str | None = None,
    ):
        """
        Инициализирует клиент.

        Args:
            tts_url: URL для синтеза речи
            stt_url: URL для распознавания речи
            default_voice: голос по умолчанию
            default_format: формат аудио по умолчанию
        """
        self._tts_url = tts_url or _DEFAULT_TTS_URL
        self._stt_url = stt_url or _DEFAULT_STT_URL
        self._default_voice = default_voice or _DEFAULT_VOICE
        self._default_format = default_format or _DEFAULT_AUDIO_FORMAT

        # Токен для авторизации (используется напрямую)
        self._access_token = SPEECH_AUTH or ""

        if not self._access_token:
            logger.warning("SPEECH_AUTH токен не найден в окружении")

    def synthesize(
        self,
        text: str,
        voice: str | None = None,
        audio_format: str | None = None,
    ) -> tuple[bytes, str, str]:
        """
        Синтезирует речь из текста.

        Args:
            text: текст для синтеза
            voice: голос (по умолчанию Nec_24000)
            audio_format: формат вывода (opus/wav)

        Returns:
            (audio_bytes, media_type, voice_used)
        """
        voice = validate_tts_voice(voice) or self._default_voice
        audio_format = validate_tts_format(audio_format) or self._default_format

        token = self._access_token

        try:
            response = requests.post(
                self._tts_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "voice": voice,
                    "format": audio_format,
                },
                verify=False,
                timeout=60,
            )
            response.raise_for_status()

            audio_bytes = response.content

            # Определяем media type по формату
            media_type = "audio/opus" if audio_format == "opus" else "audio/wav"

            logger.debug(f"Синтез речи: {len(text)} символов → {len(audio_bytes)} байт")
            return audio_bytes, media_type, voice

        except Exception as e:
            logger.error(f"Ошибка синтеза речи: {e}")
            raise

    def transcribe(
        self,
        audio_bytes: bytes,
        content_type: str = "audio/ogg;codecs=opus",
        recognition_model: str | None = None,
    ) -> tuple[str, str]:
        """
        Распознаёт речь из аудио.

        Args:
            audio_bytes: аудио данные
            content_type: MIME тип аудио (audio/ogg;codecs=opus, audio/wav)
            recognition_model: модель распознавания (general, etc.)

        Returns:
            (transcribed_text, model_used)
        """
        model = validate_stt_model(recognition_model) or _DEFAULT_RECOGNITION_MODEL

        token = self._access_token

        try:
            response = requests.post(
                self._stt_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": content_type,
                    "Model": model,
                },
                data=audio_bytes,
                verify=False,
                timeout=120,  # Распознавание может занять время
            )
            response.raise_for_status()

            # Ответ приходит как plain text с распознанным текстом
            text = response.text.strip()

            logger.debug(f"Распознавание речи: {len(audio_bytes)} байт → {len(text)} символов")
            return text, model

        except Exception as e:
            logger.error(f"Ошибка распознавания речи: {e}")
            raise

    def clear_cache(self) -> None:
        """Метод удалён — кэширование токена больше не используется."""
        pass


# === Модульные функции для удобного импорта ===

_default_client: SaluteSpeechClient | None = None


def _get_default_client() -> SaluteSpeechClient:
    """Возвращает или создаёт клиент по умолчанию."""
    global _default_client
    if _default_client is None:
        _default_client = SaluteSpeechClient()
    return _default_client


def transcribe_audio(
    audio_bytes: bytes,
    content_type: str = "audio/ogg;codecs=opus",
    recognition_model: str | None = None,
) -> tuple[str, str]:
    """
    Распознаёт речь из аудио (модульная функция для удобного импорта).

    Args:
        audio_bytes: аудио данные
        content_type: MIME тип аудио
        recognition_model: модель распознавания

    Returns:
        (transcribed_text, model_used)
    """
    client = _get_default_client()
    return client.transcribe(audio_bytes, content_type, recognition_model)


def synthesize_audio(
    text: str,
    voice: str | None = None,
    audio_format: str | None = None,
) -> tuple[bytes, str, str]:
    """
    Синтезирует речь из текста (модульная функция для удобного импорта).

    Args:
        text: текст для синтеза
        voice: голос (по умолчанию из config)
        audio_format: формат вывода (opus/wav)

    Returns:
        (audio_bytes, media_type, voice_used)
    """
    client = _get_default_client()
    return client.synthesize(text, voice, audio_format)