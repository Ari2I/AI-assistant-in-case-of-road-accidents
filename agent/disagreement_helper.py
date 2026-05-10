"""
Подрежим помощи при разногласиях в рамках Step 1.

Сценарий:
1. Агент объясняет, что при неразрешённых разногласиях Европротокол невозможен
2. Анализирует ситуацию на основе ПДД и законов, пытается определить виновного
3. Если участники приходят к согласию → disagreement=False, сбор данных продолжается
4. Если согласия нет → CONSULTANT_ONLY (вызов ГИБДД)
"""

import json
import re

from gigachat.models import Chat, Messages, MessagesRole

from agent.step_types import Step, StepResponse
from agent.history import build_history

# Системный промпт для анализа разногласий
_ANALYSIS_PROMPT = """\
Ты — консультант по ДТП. Пользователь попал в аварию, и между участниками \
есть разногласия по вопросу вины.

Контекст из базы знаний (ПДД и законы):
{context}

История диалога:
{history}

ТВОЯ ЗАДАЧА:
1. Выслушай описание ситуации от пользователя
2. На основании ПДД и законов объясни, кто, скорее всего, виновен и почему
3. Помоги участникам прийти к взаимному согласию
4. Напомни: при неразрешённых разногласиях Европротокол возможен ТОЛЬКО \
с фиксацией через приложение (лимит 200 000 руб.), без приложения — \
необходим вызов ГИБДД (102)

ВАЖНЫЕ ПРАВИЛА:
- Ссылайся только на нормы из контекста, не выдумывай статьи
- Если ситуация неоднозначна — скажи об этом прямо
- В конце ответа ВСЕГДА спрашивай: удалось ли прийти к согласию?

После анализа верни ответ СТРОГО в формате JSON (без markdown, без пояснений):
{{
    "answer": "текст ответа пользователю",
    "resolution_detected": true/false,
    "resolution_type": "agreed" / "disagreed" / "unclear"
}}

Значения resolution_type:
- "agreed"    — пользователь явно говорит, что согласие достигнуто
- "disagreed" — пользователь явно говорит, что согласие невозможно
- "unclear"   — ещё обсуждают, нужно продолжить диалог
"""

_FALLBACK_INTRO = (
    "При наличии неразрешённых разногласий Европротокол возможен только "
    "с фиксацией через приложение «Помощник ОСАГО» или «Госуслуги.Авто» "
    "(лимит 200 000 руб.). Без приложения — необходим вызов ГИБДД (102).\n\n"
    "Расскажите подробнее об обстоятельствах ДТП — я постараюсь помочь "
    "разобраться, кто виновен согласно ПДД."
)


def run_disagreement_help(
    giga,
    query: str,
    history: list,
    slots: dict,
    disagreement_db,
) -> StepResponse:
    """
    Обрабатывает запрос в подрежиме помощи при разногласиях.

    Возможные исходы:
    - resolution_type="agreed"    → disagreement=False, продолжаем step1
    - resolution_type="disagreed" → CONSULTANT_ONLY (вызов ГИБДД)
    - resolution_type="unclear"   → продолжаем диалог в подрежиме
    """
    context = _get_context(disagreement_db, query)
    history_text = build_history(history, component="classifier")

    result = _analyze_with_llm(giga, query, context, history_text)

    resolution_type = result.get("resolution_type", "unclear")
    answer = result.get("answer", _FALLBACK_INTRO)

    if resolution_type == "agreed":
        # Согласие достигнуто — сбрасываем разногласие и продолжаем step1
        updated_slots = {
            **slots,
            "disagreement": False,
            "disagreement_help_active": False,
        }
        return StepResponse(
            answer=(
                f"{answer}\n\n"
                "Отлично, рад, что удалось разобраться! "
                "Продолжаем оформление. "
                "У всех участников ДТП есть действующие полисы ОСАГО?"
            ),
            step_completed=False,
            next_step=Step.STEP1,
            slots=updated_slots,
        )

    if resolution_type == "disagreed":
        # Согласие недостижимо — вызов ГИБДД, режим консультанта
        updated_slots = {**slots, "disagreement_help_active": False}
        return StepResponse(
            answer=(
                f"{answer}\n\n"
                "К сожалению, при неразрешённых разногласиях "
                "оформление Европротокола невозможно. "
                "Вам необходимо вызвать ГИБДД (102). "
                "Я продолжу работать в режиме консультанта — "
                "задавайте любые вопросы по ДТП."
            ),
            step_completed=True,
            next_step=Step.CONSULTANT_ONLY,
            slots=updated_slots,
        )

    # unclear — продолжаем диалог
    return StepResponse(
        answer=answer,
        step_completed=False,
        next_step=Step.STEP1,
        slots=slots,
    )


def _get_context(disagreement_db, query: str) -> str:
    if not disagreement_db:
        return "База знаний по разногласиям недоступна."
    try:
        docs = disagreement_db.similarity_search(query, k=4)
        return "\n\n---\n\n".join(d.page_content for d in docs)
    except Exception as e:
        print(f"[disagreement_helper] RAG error: {e}")
        return "База знаний временно недоступна."


def _analyze_with_llm(
    giga,
    query: str,
    context: str,
    history_text: str,
) -> dict:
    """
    Вызывает LLM для анализа разногласий.
    Возвращает dict с полями answer, resolution_detected, resolution_type.
    При ошибке парсинга — возвращает безопасный fallback.
    """
    payload = Chat(
        messages=[
            Messages(
                role=MessagesRole.SYSTEM,
                content=_ANALYSIS_PROMPT.format(
                    context=context,
                    history=history_text or "(начало диалога)",
                ),
            ),
            Messages(role=MessagesRole.USER, content=query),
        ],
        temperature=0.1,
    )

    try:
        response = giga.chat(payload)
        content = response.choices[0].message.content.strip()

        # Убираем markdown если есть
        if "```" in content:
            parts = content.split("```")
            for part in parts:
                stripped = part.strip()
                if stripped.startswith("{"):
                    content = stripped
                    break

        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return _fallback_result(content)

        data = json.loads(match.group(0))

        if "answer" not in data or not data["answer"].strip():
            data["answer"] = _FALLBACK_INTRO

        if data.get("resolution_type") not in ("agreed", "disagreed", "unclear"):
            data["resolution_type"] = "unclear"

        return data

    except (json.JSONDecodeError, AttributeError, IndexError) as e:
        print(f"[disagreement_helper] LLM parse error: {e}")
        return _fallback_result("")


def _fallback_result(raw_answer: str) -> dict:
    return {
        "answer": raw_answer if raw_answer else _FALLBACK_INTRO,
        "resolution_detected": False,
        "resolution_type": "unclear",
    }