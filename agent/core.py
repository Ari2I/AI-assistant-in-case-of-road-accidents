"""
Pipeline v5.0 — с машиной состояний и Function Calling.
Изменения vs v4.0:
  - Добавлена машина состояний (dialog_flow.py) для детерминированного сбора фактов
  - Function Calling (gigachat_client.py) для надёжного извлечения фактов
  - Состояние диалога передаётся между вызовами run_agent()

Было: LLM управляет переходами между шагами (непредсказуемо)
Стало: явная машина состояний + LLM для категории ответа
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from gigachat import GigaChat

from config import GIGA_AUTH
from agent.meta_classifier import meta_classify
from agent.retriever import get_context_for_category
from agent.generator import generate_answer
from agent.algorithm import load_algorithm, get_algorithm_slice
from agent.history import build_history
from evaluation.self_check import improve_answer
from evaluation.critic import critic_rate_answer
from evaluation.damage_analyzer import analyze_damage, analyze_multiple_damages
from rag.feedback_db import save_good_qa
from templates.matcher import match_template
from services.dialog_flow import (
    AIConversationState,
    AIConversationFacts,
    create_initial_state,
    apply_facts_and_advance_step,
    build_known_facts_summary,
    is_terminal_step,
    STEP_READY_EUROPROTOCOL,
    STEP_POLICE_REQUIRED,
    STEP_SPECIAL_CASE,
)
from services.gigachat_client import extract_accident_facts
from services.salutespeech_client import transcribe_audio, synthesize_audio
from utils.audio_utils import normalize_audio_for_salutespeech

logger = logging.getLogger(__name__)

_CONFIDENCE_THRESHOLD = 0.65
_MAX_IMPROVE_ATTEMPTS = 2

# Маркеры неуверенности в ответе — если есть, запускаем self_check
# Иначе пропускаем (~2500 токенов экономии на уверенных ответах)
_UNCERTAINTY_MARKERS = [
    "не уверен", "возможно", "наверное", "кажется", "точно не знаю",
    "затрудняюсь", "не могу сказать", "уточните", "не помню",
]

# Алгоритм загружается один раз при старте — не читаем файл на каждый запрос
_ALGORITHM = load_algorithm()


def run_agent(
        query: str,
        history: list | None = None,
        db=None,
        feedback_db=None,
        state: AIConversationState | None = None,
) -> dict:
    """
    Обрабатывает сообщение пользователя и возвращает ответ.

    Args:
        query:       сообщение пользователя
        history:     история диалога [{"query": ..., "answer": ...}, ...]
        db:          основная ChromaDB (может быть None)
        feedback_db: база дообучения (может быть None)
        state:       состояние машины состояний (может быть None для нового диалога)

    Returns:
        {
            "answer":   str,
            "source":   str,   # "template" | "llm" | "filter" | "error"
            "category": str | None,
            "state":    dict,  # новое состояние для передачи в следующий вызов
        }
    """
    history = history or []
    state = state or create_initial_state()

    # ШАГ 1: Regex-шаблоны (0 токенов, мгновенно)
    template_answer = match_template(query)
    if template_answer:
        return _ok(template_answer, "template", None, state)

    try:
        with _make_giga() as giga:

            # ШАГ 2: Один вызов вместо трёх (filter + classifier + planner)
            classifier_history = build_history(history, component="classifier")
            meta = meta_classify(giga, query, classifier_history)

            if not meta["relevant"]:
                return _ok(
                    "Я консультирую только по вопросам ДТП и ОСАГО. "
                    "Если у вас произошла авария — опишите ситуацию.",
                    "filter",
                    None,
                    state,
                )

            category = meta["category"]
            block = meta["block"]

            # ШАГ 3: Function Calling для извлечения фактов (после классификации)
            # Если функция вернёт пустой dict — используем keyword-override из meta_classifier
            facts = extract_accident_facts(giga, query)

            # Применяем факты и продвигаем машину состояний
            if facts:
                state = apply_facts_and_advance_step(state, facts)

            # Проверяем, не перешли ли в сценарий разрешения разногласий
            if state.facts.has_disagreements is True and state.scenario == "standard":
                state.scenario = "dispute_resolution"

            # ШАГ 4: RAG — контекст по категории
            context = get_context_for_category(db, feedback_db, query, category)

            # ШАГ 5: Только нужный блок алгоритма ± 1 соседний
            algorithm_slice = get_algorithm_slice(block, window=1)

            plan = {
                "category": category,
                "stage": category,
                "answer_type": "steps",
                "algorithm_block": block,
            }


            # Добавляем сводку известных фактов в план для генератора
            plan["known_facts"] = build_known_facts_summary(state)
            plan["current_step"] = state.current_step
            plan["scenario"] = state.scenario

            # ШАГ 6: Генерация с условной самопроверкой
            generator_history = build_history(
                history, component="generator", category=category
            )
            answer, _ = _generate_with_selfcheck(
                giga, query, context, plan,
                algorithm_slice, generator_history,
            )

            return _ok(answer, "llm", category, state)

    except Exception as e:
        logger.error(f"[core] pipeline error: {e}")
        return _ok(
            "Произошла техническая ошибка. "
            "Если вы в опасной ситуации — немедленно звоните 112. "
            "Попробуйте повторить вопрос через несколько секунд.",
            "error",
            None,
            state,
        )


def rate_answer(
        query: str,
        answer: str,
        rating: int,
        feedback_db=None,
) -> dict:
    """
    Запускает AI-критика и при высоких оценках дообучает RAG.

    Args:
        query:       вопрос пользователя (из БД бэкенда)
        answer:      ответ агента (из БД бэкенда)
        rating:      оценка пользователя 0–5
        feedback_db: база дообучения

    Returns:
        {"critic_score": int, "critic_comment": str}
    """
    try:
        with _make_giga() as giga:
            score, comment = critic_rate_answer(giga, query, answer)

        if rating >= 4 and score >= 4:
            save_good_qa(query, answer)

        return {"critic_score": score, "critic_comment": comment}

    except Exception as e:
        print(f"[core] rate_answer error: {e}")
        return {"critic_score": 3, "critic_comment": "Ошибка оценки"}


def _make_giga() -> GigaChat:
    return GigaChat(
        credentials=GIGA_AUTH,
        verify_ssl_certs=False,
        scope="GIGACHAT_API_B2B",
    )


def _should_run_selfcheck(answer: str) -> bool:
    """Запускаем self_check только при явных маркерах неуверенности."""
    answer_lower = answer.lower()
    return any(marker in answer_lower for marker in _UNCERTAINTY_MARKERS)


def _generate_with_selfcheck(
        giga: GigaChat,
        query: str,
        context: str,
        plan: dict,
        algorithm_slice: str,
        generator_history: str,
) -> tuple[str, float]:
    raw = generate_answer(
        giga, query, context, plan,
        algorithm=algorithm_slice,
        history_text=generator_history,
    )

    if not _should_run_selfcheck(raw):
        return raw, 1.0

    for attempt in range(_MAX_IMPROVE_ATTEMPTS):
        verdict, conf, issues, improved = improve_answer(giga, query, raw, context)

        if verdict == "GOOD":
            return raw, conf

        raw = improved
        if issues:
            print(f"[core] self-check attempt {attempt + 1}: {issues[:80]}")

        if conf >= _CONFIDENCE_THRESHOLD:
            break

    return raw, 0.0


def _ok(answer: str, source: str, category: str | None, state: AIConversationState) -> dict:
    return {
        "answer": answer,
        "source": source,
        "category": category,
        "state": state.to_dict(),
    }


def process_voice_message(
    audio_bytes: bytes,
    content_type: str = "audio/ogg;codecs=opus",
    history: list | None = None,
    db=None,
    feedback_db=None,
    state: AIConversationState | None = None,
) -> dict:
    """
    Обрабатывает голосовое сообщение пользователя.

    1. Нормализует аудио (конвертация в PCM 16bit, 16kHz, моно)
    2. Распознаёт речь через SaluteSpeech STT
    3. Передаёт текст в run_agent()
    4. Возвращает ответ + синтезирует аудио (опционально)

    Args:
        audio_bytes: сырые аудио данные
        content_type: MIME тип входящего аудио
        history: история диалога
        db: основная ChromaDB
        feedback_db: база дообучения
        state: состояние машины состояний

    Returns:
        {
            "answer": str,
            "source": str,
            "category": str | None,
            "state": dict,
            "transcribed_text": str,
            "audio_response": bytes | None,
            "audio_media_type": str | None,
        }
    """
    try:
        # Шаг 1: Нормализация аудио
        normalized = normalize_audio_for_salutespeech(audio_bytes, content_type)

        # Шаг 2: Распознавание речи
        transcribed_text, _ = transcribe_audio(
            normalized.pcm_bytes,
            f"audio/pcm;rate={normalized.sample_rate}",
        )

        if not transcribed_text.strip():
            return {
                "answer": "Не удалось распознать речь. Попробуйте повторить сообщение.",
                "source": "error",
                "category": None,
                "state": (state or create_initial_state()).to_dict(),
                "transcribed_text": "",
                "audio_response": None,
                "audio_media_type": None,
            }

        # Шаг 3: Обработка текста через основной pipeline
        result = run_agent(
            query=transcribed_text,
            history=history,
            db=db,
            feedback_db=feedback_db,
            state=state,
        )

        # Шаг 4: Синтез ответа в аудио (опционально, можно отключить флагом)
        audio_response = None
        audio_media_type = None

        if result["source"] != "error":
            try:
                audio_response, audio_media_type, _ = synthesize_audio(result["answer"])
            except Exception as e:
                logger.warning(f"Ошибка синтеза аудио: {e}")
                # Не роняем весь запрос, просто возвращаем без аудио

        result["transcribed_text"] = transcribed_text
        result["audio_response"] = audio_response
        result["audio_media_type"] = audio_media_type

        return result

    except Exception as e:
        logger.error(f"[core] process_voice_message error: {e}")
        return {
            "answer": "Произошла техническая ошибка при обработке голоса. Попробуйте текстовый ввод.",
            "source": "error",
            "category": None,
            "state": (state or create_initial_state()).to_dict(),
            "transcribed_text": "",
            "audio_response": None,
            "audio_media_type": None,
        }



def process_photo_damage_analysis(
        image_paths: list[str],
        vehicle_info: Optional[str] = None,
) -> dict:
    """
    Анализирует фотографии повреждений автомобиля и оценивает сумму ущерба.

    Функция использует GigaChat для анализа одного или нескольких изображений,
    определения типа и степени повреждений, а также расчёта ориентировочной
    стоимости восстановительного ремонта.

    Args:
        image_paths: список путей к файлам изображений с повреждениями
        vehicle_info: информация об автомобиле (марка, модель, год) для уточнения оценки

    Returns:
        {
            "success": bool,
            "analysis": dict,              # результаты анализа (individual_analyses + totals)
            "total_min_cost": float,       # общая минимальная стоимость
            "total_max_cost": float,       # общая максимальная стоимость
            "total_avg_cost": float,       # общая средняя стоимость
            "summary": str,                # сводное описание
            "currency": str = "RUB",
            "error": str | None,           # сообщение об ошибке если есть
        }
    """
    if not image_paths:
        return {
            "success": False,
            "analysis": {},
            "total_min_cost": 0,
            "total_max_cost": 0,
            "total_avg_cost": 0,
            "summary": "Нет изображений для анализа",
            "currency": "RUB",
            "error": "Не предоставлены пути к изображениям",
        }

    try:
        with _make_giga() as giga:
            if len(image_paths) == 1:
                # Анализ одиночного фото
                result = analyze_damage(giga, image_paths[0], vehicle_info)
                return {
                    "success": True,
                    "analysis": {"individual": [result]},
                    "total_min_cost": result.get("min_cost", 0),
                    "total_max_cost": result.get("max_cost", 0),
                    "total_avg_cost": result.get("avg_cost", 0),
                    "summary": result.get("description", ""),
                    "currency": result.get("currency", "RUB"),
                    "error": None,
                }
            else:
                # Анализ множественных фото
                result = analyze_multiple_damages(giga, image_paths, vehicle_info)
                return {
                    "success": True,
                    "analysis": result,
                    "total_min_cost": result.get("total_min_cost", 0),
                    "total_max_cost": result.get("total_max_cost", 0),
                    "total_avg_cost": result.get("total_avg_cost", 0),
                    "summary": result.get("summary", ""),
                    "currency": result.get("currency", "RUB"),
                    "error": None,
                }

    except FileNotFoundError as e:
        logger.error(f"[core] process_photo_damage_analysis error: файл не найден - {e}")
        return {
            "success": False,
            "analysis": {},
            "total_min_cost": 0,
            "total_max_cost": 0,
            "total_avg_cost": 0,
            "summary": "",
            "currency": "RUB",
            "error": f"Файл изображения не найден: {e}",
        }

    except ValueError as e:
        logger.error(f"[core] process_photo_damage_analysis error: неверный формат - {e}")
        return {
            "success": False,
            "analysis": {},
            "total_min_cost": 0,
            "total_max_cost": 0,
            "total_avg_cost": 0,
            "summary": "",
            "currency": "RUB",
            "error": f"Неподдерживаемый формат файла: {e}",
        }

    except Exception as e:
        logger.error(f"[core] process_photo_damage_analysis error: {e}")
        return {
            "success": False,
            "analysis": {},
            "total_min_cost": 0,
            "total_max_cost": 0,
            "total_avg_cost": 0,
            "summary": "",
            "currency": "RUB",
            "error": f"Произошла техническая ошибка при анализе фото: {e}",
        }