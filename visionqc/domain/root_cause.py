from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum


class ConfidenceBand(StrEnum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


@dataclass(frozen=True, slots=True)
class CauseEvidence:
    signal: str
    contribution: float
    explanation: str
    source_case_uuid: str = ""


@dataclass(slots=True)
class CauseHypothesis:
    cause: str
    score: float
    confidence: ConfidenceBand
    supporting_evidence: list[CauseEvidence] = field(default_factory=list)
    opposing_evidence: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    verified_case_count: int = 0


@dataclass(slots=True)
class RootCauseAnalysis:
    case_id: int
    case_uuid: str
    hypotheses: list[CauseHypothesis]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    method: str = "VisionQC explainable evidence-weighted RCA v1"
    safety_note: str = "Decision support only. A qualified QC or process engineer must verify the root cause before machine or recipe changes."

    @property
    def top_hypothesis(self) -> CauseHypothesis | None:
        return self.hypotheses[0] if self.hypotheses else None
