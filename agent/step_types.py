"""
Общие типы для шагового режима агента.
Используются в core.py, step1_stateless.py, step2_europrotocol.py.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Step(str, Enum):
    """Допустимые значения текущего шага."""
    GENERAL   = "general"    # Общие вопросы по ДТП/ОСАГО
    STEP1     = "step1"      # Сбор фактов
    STEP2     = "step2"      # Заполнение Европротокола
    DONE      = "done"       # Оформление завершено
    CALL_GIBDD = "call_gibdd" # Стоп-фактор, нужна ГИБДД


@dataclass
class StepResponse:
    """
    Единый формат ответа для шагового режима.
    Возвращается из _run_step1() и _run_step2() в core.py.
    Бэкенд сохраняет и передаёт поля slots и collected_fields
    при следующем запросе.
    """
    answer: str
    step_completed: bool
    next_step: Step
    slots: dict[str, Any] = field(default_factory=dict)
    collected_fields: dict[str, Any] = field(default_factory=dict)
    final_json: dict[str, Any] | None = None