from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class RankedInsight:
    label: str
    count: int
    percentage: float
    context: str = ""


@dataclass(frozen=True, slots=True)
class ActionInsight:
    action_type: str
    attempts: int
    effective: int
    ineffective: int
    effectiveness_rate: float
    last_result: str = ""


@dataclass(frozen=True, slots=True)
class FactoryLearningSummary:
    total_cases: int
    rejected_cases: int
    verified_cases: int
    resolved_cases: int
    verification_rate: float
    recurrence_rate: float
    action_effectiveness_rate: float
    top_causes: tuple[RankedInsight, ...] = ()
    top_defects: tuple[RankedInsight, ...] = ()
    machine_hotspots: tuple[RankedInsight, ...] = ()
    shift_hotspots: tuple[RankedInsight, ...] = ()
    action_insights: tuple[ActionInsight, ...] = ()
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LearnedRecommendation:
    action_type: str
    description: str
    support_count: int
    effectiveness_rate: float
    confidence: float
    evidence: tuple[str, ...] = ()
