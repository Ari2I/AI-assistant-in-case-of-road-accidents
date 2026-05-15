"""
Общие типы для шагового режима агента.
Используются в core.py, step1_stateless.py, step2_europrotocol.py.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Step(str, Enum):
    STEP1               = "step1"
    STEP2               = "step2"
    STEP3               = "step3"
    OFFER_EUROPROTOCOL  = "offer_europrotocol"
    OFFER_METHOD        = "offer_method"       # выбор способа заполнения протокола
    FILL_EXTERNAL       = "fill_external"      # пользователь заполняет сам (приложение/бумага)
    CONSULTANT_ONLY     = "consultant_only"
    DONE                = "done"
    CALL_GIBDD          = "call_gibdd"


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
    prefilled_fields: dict[str, Any] = field(default_factory=dict)