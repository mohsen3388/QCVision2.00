from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum


class RiskBand(StrEnum):
    LOW = "Low"
    GUARDED = "Guarded"
    HIGH = "High"
    CRITICAL = "Critical"


@dataclass(frozen=True, slots=True)
class RiskDriver:
    name: str
    contribution: float
    explanation: str
    evidence_count: int = 0


@dataclass(frozen=True, slots=True)
class QualityForecast:
    scope: str
    risk_score: float
    risk_band: RiskBand
    predicted_reject_rate: float
    current_reject_rate: float
    baseline_reject_rate: float
    trend: str
    confidence: float
    horizon: str
    sample_count: int
    drivers: tuple[RiskDriver, ...] = ()
    recommended_actions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))

    @property
    def alert_required(self) -> bool:
        return self.risk_band in {RiskBand.HIGH, RiskBand.CRITICAL}
