from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class RuleFinding:
    rule_id: str
    title: str
    severity: str
    triggered: bool
    confidence: float
    reason: str
    evidence: dict[str, Any]
    recommendation: str
    source: str = "Global Visual Knowledge"


@dataclass(slots=True)
class AnalysisResult:
    source_path: str
    width: int
    height: int
    roi: tuple[int, int, int, int] | None
    metrics: dict[str, dict[str, float]]
    findings: list[RuleFinding]
    visual_health_score: float
    analysis_confidence: float
    status: str
    distributions: dict[str, list[float]] = field(default_factory=dict)
    visualization_png: dict[str, bytes] = field(default_factory=dict, repr=False)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    engine_version: str = "0.4.1"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("visualization_png", None)
        return data


@dataclass(slots=True)
class TemporalSample:
    frame_index: int
    timestamp_seconds: float
    visual_health_score: float
    analysis_confidence: float
    status: str
    brightness: float
    color_uniformity: float
    texture_uniformity: float
    bubble_candidate_density: float
    oily_region_candidate_percent: float
    sharpness: float
    triggered_findings: int
    motion_stability: float = 100.0
    mixing_coverage: float = 100.0


@dataclass(slots=True)
class TemporalEvent:
    timestamp_seconds: float
    event_type: str
    severity: str
    message: str
    value: float | None = None


@dataclass(slots=True)
class VideoAnalysisResult:
    source_path: str
    duration_seconds: float
    source_fps: float
    frame_count: int
    sampling_interval_seconds: float
    analyzed_frames: int
    samples: list[TemporalSample]
    events: list[TemporalEvent]
    overall_health_score: float
    overall_confidence: float
    process_stability: float
    status: str
    snapshots_jpeg: dict[str, bytes] = field(default_factory=dict, repr=False)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    engine_version: str = "0.4.1"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("snapshots_jpeg", None)
        return data
