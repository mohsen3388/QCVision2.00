from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum


class OperationalPriority(StrEnum):
    ROUTINE = "Routine"
    ATTENTION = "Attention"
    URGENT = "Urgent"
    HOLD_AND_VERIFY = "Hold and verify"


@dataclass(frozen=True, slots=True)
class EngineerAction:
    priority: int
    title: str
    rationale: str
    owner_role: str
    verification: str
    source: str
    requires_approval: bool = True


@dataclass(frozen=True, slots=True)
class FactoryEngineerBriefing:
    scope: str
    priority: OperationalPriority
    executive_summary: str
    quality_status: str
    forecast_summary: str
    root_cause_summary: str
    actions: tuple[EngineerAction, ...] = ()
    evidence: tuple[str, ...] = ()
    decision_gates: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    selected_case_id: int | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
