"""
Утилиты для обработки аудио.

Подготовка аудио для SaluteSpeech API:
- Конвертация WAV → PCM 16bit
- Ресемплинг до 16000 Hz (ближайший сосед)
- Микширование многоканального аудио в моно (первый канал)
"""

from __future__ import annotations

import io
import logging
import struct
import wave
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

TARGET_SAMPLE_RATE = 16000


@dataclass
class NormalizedAudioPayload:
    """Результат нормализации аудио."""
    pcm_bytes: bytes  # сырые PCM данные для отправки в API
    content_type: str  # MIME тип для отправки в API
    sample_rate: int
    channels: int
    sample_width: int  # байт на сэмпл
    duration_ms: float | None = None  # приблизительная длительность


# Алиас для обратной совместимости
audio_bytes = property(lambda self: self.pcm_bytes)


def normalize_audio_for_salutespeech(
    audio_bytes: bytes,
    content_type: str,
) -> NormalizedAudioPayload:
    """
    Нормализует аудио для передачи в SaluteSpeech API.

    Поддерживаемые входные форматы:
    - audio/wav, audio/x-wav
    - audio/ogg;codecs=opus
    - audio/mpeg (MP3)

    Преобразования:
    - WAV → PCM 16bit (если другой формат)
    - Ресемплинг до 16000 Hz (ближайший сосед)
    - Микширование в моно (берём первый канал)

    Args:
        audio_bytes: исходные аудио данные
        content_type: MIME тип входного аудио

    Returns:
        NormalizedAudioPayload с готовыми данными
    """
    content_type_lower = content_type.lower()

    try:
        if "wav" in content_type_lower or "x-wav" in content_type_lower:
            return _normalize_wav(audio_bytes)
        elif "ogg" in content_type_lower or "opus" in content_type_lower:
            # Opus уже сжатый формат — для STT можно отправить как есть
            # Но если нужно именно PCM — требуется декодирование через opusfile
            # Для простоты возвращаем как есть с предупреждением
            logger.warning("OGG/Opus без декодирования — может потребоваться конвертация")
            return NormalizedAudioPayload(
                pcm_bytes=audio_bytes,
                content_type="audio/ogg;codecs=opus",
                sample_rate=TARGET_SAMPLE_RATE,  # предполагаем
                channels=1,
                sample_width=2,
            )
        elif "mpeg" in content_type_lower or "mp3" in content_type_lower:
            # MP3 требует декодирования через pydub или аналог
            logger.warning("MP3 без декодирования — требуется pydub/ffmpeg")
            return NormalizedAudioPayload(
                pcm_bytes=audio_bytes,
                content_type="audio/mpeg",
                sample_rate=TARGET_SAMPLE_RATE,  # предполагаем
                channels=1,
                sample_width=2,
            )
        else:
            # Пытаемся обработать как WAV по умолчанию
            logger.warning(f"Неизвестный тип {content_type}, пробуем как WAV")
            return _normalize_wav(audio_bytes)

    except Exception as e:
        logger.error(f"Ошибка нормализации аудио: {e}")
        raise


def _normalize_wav(audio_bytes: bytes) -> NormalizedAudioPayload:
    """
    Нормализует WAV файл.

    - Извлекает параметры
    - Конвертирует в 16bit PCM если нужно
    - Ресемплит до 16000 Hz
    - Микширует в моно
    """
    with io.BytesIO(audio_bytes) as wav_io:
        with wave.open(wav_io, 'rb') as wav_file:
            n_channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            framerate = wav_file.getframerate()
            n_frames = wav_file.getnframes()

            raw_data = wav_file.readframes(n_frames)

    logger.debug(
        f"WAV параметры: {n_channels} каналов, {sample_width} байт, "
        f"{framerate} Hz, {n_frames} фреймов"
    )

    # Конвертируем sample width к 2 байтам (16bit)
    if sample_width != 2:
        raw_data = _convert_sample_width(raw_data, sample_width, 2)
        sample_width = 2

    # Микшируем в моно если много каналов
    if n_channels > 1:
        raw_data = _mix_to_mono(raw_data, n_channels, sample_width)
        n_channels = 1

    # Ресемплинг до TARGET_SAMPLE_RATE
    if framerate != TARGET_SAMPLE_RATE:
        raw_data = _resample_nearest_neighbor(raw_data, framerate, TARGET_SAMPLE_RATE)
        framerate = TARGET_SAMPLE_RATE

    # Вычисляем длительность
    duration_ms = (n_frames / framerate) * 1000 if framerate > 0 else None

    # Собираем обратно в WAV
    output_bytes = _create_wav_bytes(raw_data, n_channels, sample_width, framerate)

    return NormalizedAudioPayload(
        pcm_bytes=output_bytes,
        content_type="audio/wav",
        sample_rate=framerate,
        channels=n_channels,
        sample_width=sample_width,
        duration_ms=duration_ms,
    )


def _convert_sample_width(
    data: bytes,
    from_width: int,
    to_width: int,
) -> bytes:
    """
    Конвертирует битность сэмплов.

    Args:
        data: сырые аудио данные
        from_width: текущая ширина в байтах
        to_width: целевая ширина в байтах
    """
    if from_width == to_width:
        return data

    result = bytearray()

    # Читаем сэмплы согласно from_width
    if from_width == 1:
        # 8-bit unsigned → 16-bit signed
        for byte in data:
            # Конвертируем unsigned 8-bit в signed 16-bit
            signed_val = (byte - 128) << 8
            result.extend(struct.pack('<h', signed_val))
    elif from_width == 2:
        # 16-bit → 8-bit (downsample)
        for i in range(0, len(data), 2):
            val = struct.unpack('<h', data[i:i+2])[0]
            # Конвертируем signed 16-bit в unsigned 8-bit
            byte = ((val >> 8) + 128) & 0xFF
            result.append(byte)
    elif from_width == 4:
        # 32-bit float/int → 16-bit
        for i in range(0, len(data), 4):
            val = struct.unpack('<i', data[i:i+4])[0]
            # Масштабируем к 16-bit
            scaled = val >> 16
            result.extend(struct.pack('<h', scaled))
    else:
        raise ValueError(f"Неподдерживаемая ширина {from_width}")

    return bytes(result)


def _mix_to_mono(data: bytes, n_channels: int, sample_width: int) -> bytes:
    """
    Микширует многоканальное аудио в моно (берёт первый канал).

    Args:
        data: сырые аудио данные
        n_channels: количество каналов
        sample_width: ширина сэмпла в байтах
    """
    bytes_per_frame = n_channels * sample_width
    result = bytearray()

    for i in range(0, len(data), bytes_per_frame):
        frame = data[i:i+bytes_per_frame]
        # Берём только первый канал
        channel_data = frame[:sample_width]
        result.extend(channel_data)

    return bytes(result)


def _resample_nearest_neighbor(
    data: bytes,
    from_rate: int,
    to_rate: int,
) -> bytes:
    """
    Ресемплинг методом ближайшего соседа.

    Args:
        data: сырые аудио данные (предполагается 16bit)
        from_rate: исходная частота дискретизации
        to_rate: целевая частота дискретизации
    """
    if from_rate == to_rate:
        return data

    ratio = from_rate / to_rate

    # Читаем все сэмплы
    samples = []
    for i in range(0, len(data), 2):
        sample = struct.unpack('<h', data[i:i+2])[0]
        samples.append(sample)

    # Ресемплим
    resampled = []
    src_idx = 0.0
    while int(src_idx) < len(samples):
        resampled.append(samples[int(src_idx)])
        src_idx += ratio

    # Записываем обратно
    result = bytearray()
    for sample in resampled:
        result.extend(struct.pack('<h', sample))

    return bytes(result)


def _create_wav_bytes(
    data: bytes,
    n_channels: int,
    sample_width: int,
    framerate: int,
) -> bytes:
    """
    Создаёт WAV файл из сырых данных.

    Args:
        data: сырые PCM данные
        n_channels: количество каналов
        sample_width: ширина сэмпла в байтах
        framerate: частота дискретизации
    """
    output = io.BytesIO()

    with wave.open(output, 'wb') as wav_file:
        wav_file.setnchannels(n_channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(framerate)
        wav_file.writeframes(data)

    return output.getvalue()


def get_audio_duration_ms(payload: NormalizedAudioPayload) -> float:
    """
    Возвращает длительность аудио в миллисекундах.

    Args:
        payload: результат нормализации

    Returns:
        длительность в мс
    """
    if payload.duration_ms is not None:
        return payload.duration_ms

    # Вычисляем из параметров
    bytes_per_second = payload.sample_rate * payload.channels * payload.sample_width
    if bytes_per_second > 0:
        return (len(payload.pcm_bytes) / bytes_per_second) * 1000

    return 0.0