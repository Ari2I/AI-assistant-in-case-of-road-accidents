"""
SaluteSpeech клиент для синтеза и распознавания речи.

Поддерживает:
- TTS (text-to-speech): синтез речи из текста
- STT (speech-to-text): распознавание речи в текст
- Кэширование токена авторизации с автоматическим обновлением
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

from utils.catalog import validate_tts_voice, validate_tts_format, validate_stt_model
from config import GIGA_AUTH

logger = logging.getLogger(__name__)

# URL API SaluteSpeech (берутся из config или используются дефолтные)
_DEFAULT_TTS_URL = "https://smartspeech.sber.ru/rest/v1/text:synthesize"
_DEFAULT_STT_URL = "https://smartspeech.sber.ru/rest/v1/stt"
_DEFAULT_AUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"

# Дефолтный голос для TTS
_DEFAULT_VOICE = "Nec_24000"

# Формат аудио по умолчанию
_DEFAULT_AUDIO_FORMAT = "opus"

# Модель распознавания по умолчанию
_DEFAULT_RECOGNITION_MODEL = "general"


class SaluteSpeechClient:
    """
    Клиент для работы с SaluteSpeech API.

    Кэширует токен авторизации и автоматически обновляет его
    за 60 секунд до истечения срока жизни.
    """

    def __init__(
        self,
        auth_url: str | None = None,
        tts_url: str | None = None,
        stt_url: str | None = None,
        scope: str | None = None,
        default_voice: str | None = None,
        default_format: str | None = None,
    ):
        """
        Инициализирует клиент.

        Args:
            auth_url: URL для получения токена
            tts_url: URL для синтеза речи
            stt_url: URL для распознавания речи
            scope: OAuth scope (по умолчанию из config)
            default_voice: голос по умолчанию
            default_format: формат аудио по умолчанию
        """
        self._auth_url = auth_url or _DEFAULT_AUTH_URL
        self._tts_url = tts_url or _DEFAULT_TTS_URL
        self._stt_url = stt_url or _DEFAULT_STT_URL
        self._scope = scope or "SALUTE_SPEECH"
        self._default_voice = default_voice or _DEFAULT_VOICE
        self._default_format = default_format or _DEFAULT_AUDIO_FORMAT

        # Для аутентификации используем GIGA_AUTH как client_secret
        # В продакшне могут быть отдельные credentials для SaluteSpeech
        self._client_id = "client_id_placeholder"
        self._client_secret = GIGA_AUTH or ""

        # Кэш токена
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    def _get_access_token(self) -> str:
        """
        Получает или возвращает закэшированный токен авторизации.

        Токен обновляется за 60 секунд до истечения срока жизни.

        Returns:
            access token string
        """
        now = time.time()

        # Проверяем есть ли валидный токен (с запасом 60 секунд)
        if self._access_token and now < self._token_expires_at - 60:
            return self._access_token

        # Запрашиваем новый токен
        try:
            response = requests.post(
                self._auth_url,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "RqUID": "00000000-0000-0000-0000-000000000000",
                },
                data={
                    "scope": self._scope,
                },
                auth=(self._client_id, self._client_secret),
                verify=False,  # Для dev-среды; в продакшне включить проверку
                timeout=30,
            )
            response.raise_for_status()

            data = response.json()
            self._access_token = data.get("access_token")

            # Срок жизни токена обычно 30 минут (1800 секунд)
            expires_in = data.get("expires_in", 1800)
            self._token_expires_at = now + expires_in

            logger.info(f"Получен новый токен SaluteSpeech, истекает через {expires_in}с")
            return self._access_token

        except Exception as e:
            logger.error(f"Ошибка получения токена SaluteSpeech: {e}")
            raise

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

        token = self._get_access_token()

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

        token = self._get_access_token()

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
        """Очищает кэш токена (для тестов или принудительного обновления)."""
        self._access_token = None
        self._token_expires_at = 0.0


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