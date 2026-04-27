"""
Каталог поддерживаемых моделей и параметров GigaChat API.

Используется для валидации model_override и других параметров.
"""

from __future__ import annotations

# === Chat модели ===
SUPPORTED_CHAT_MODELS: list[str] = [
    "GigaChat-2",
    "GigaChat-2-Pro",
    "GigaChat-2-Max",
    "provider-default",
]

# === Embedding модели ===
SUPPORTED_EMBEDDING_MODELS: list[str] = [
    "Embeddings",
    "Embeddings-2",
    "EmbeddingsGigaR",
]

# === TTS голоса (SaluteSpeech) ===
SUPPORTED_TTS_VOICES: list[str] = [
    "Nec_24000",
    "Bys_24000",
    "May_24000",
    "Fil_24000",
    "Erm_24000",
    "Tar_24000",
    "Tat_24000",
    "Lev_24000",
    "Ler_24000",
    "Zak_24000",
    "Aid_24000",
    "Ale_24000",
    "Ali_24000",
    "Ani_24000",
    "Ann_24000",
    "Ant_24000",
    "Art_24000",
    "Ast_24000",
    "Bel_24000",
    "Bor_24000",
    "Val_24000",
    "Var_24000",
    "Vas_24000",
    "Ver_24000",
    "Vik_24000",
    "Vin_24000",
    "Vir_24000",
    "Vla_24000",
    "Vla2_24000",
    "Vor_24000",
    "Yul_24000",
]

# === TTS форматы ===
SUPPORTED_TTS_FORMATS: list[str] = [
    "opus",
    "wav",
]

# === STT модели распознавания ===
SUPPORTED_STT_MODELS: list[str] = [
    "general",
]


def validate_chat_model(model: str | None) -> str | None:
    """
    Валидирует название chat-модели.

    Args:
        model: название модели или None

    Returns:
        model если валидна, иначе None
    """
    if model is None:
        return None
    if model in SUPPORTED_CHAT_MODELS:
        return model
    return None


def validate_embedding_model(model: str | None) -> str | None:
    """
    Валидирует название embedding-модели.

    Args:
        model: название модели или None

    Returns:
        model если валидна, иначе None
    """
    if model is None:
        return None
    if model in SUPPORTED_EMBEDDING_MODELS:
        return model
    return None


def validate_tts_voice(voice: str | None) -> str | None:
    """
    Валидирует название TTS-голоса.

    Args:
        voice: название голоса или None

    Returns:
        voice если валиден, иначе None
    """
    if voice is None:
        return None
    if voice in SUPPORTED_TTS_VOICES:
        return voice
    return None


def validate_tts_format(audio_format: str | None) -> str | None:
    """
    Валидирует формат TTS-аудио.

    Args:
        audio_format: формат аудио или None

    Returns:
        format если валиден, иначе None
    """
    if audio_format is None:
        return None
    if audio_format in SUPPORTED_TTS_FORMATS:
        return audio_format
    return None


def validate_stt_model(model: str | None) -> str | None:
    """
    Валидирует название STT-модели.

    Args:
        model: название модели или None

    Returns:
        model если валидна, иначе None
    """
    if model is None:
        return None
    if model in SUPPORTED_STT_MODELS:
        return model
    return None