from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

QUALITY_CLASSES = ("سالم", "انحراف جزئی", "هشدار متوسط", "هشدار سطح بالا", "بحرانی")


def class_from_score(score: float) -> str:
    value = float(score)
    if value >= 90:
        return "سالم"
    if value >= 80:
        return "انحراف جزئی"
    if value >= 70:
        return "هشدار متوسط"
    if value >= 50:
        return "هشدار سطح بالا"
    return "بحرانی"


@dataclass(slots=True)
class CalibrationSample:
    id: int | None
    template_key: str
    source_path: str
    expert_label: str
    expert_name: str = ""
    notes: str = ""
    batch_code: str = ""
    created_at: str = ""


@dataclass(slots=True)
class SampleEvaluation:
    sample_id: int
    source_path: str
    expert_label: str
    predicted_label: str
    final_score: float
    product_health: float
    process_health: float
    correct: bool
    result: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MetricCalibrationResult:
    metric_key: str
    metric_name: str
    class_medians: dict[str, float | None]
    suggested_warning_threshold: float | None
    suggested_high_threshold: float | None
    direction_consistency: float
    class_separation: float
    quality: str


@dataclass(slots=True)
class ValidationSummary:
    run_id: int | None
    template_key: str
    template_version: str
    sample_count: int
    class_counts: dict[str, int]
    accuracy: float
    precision: float
    recall: float
    specificity: float
    f1: float
    false_positive_rate: float
    false_negative_rate: float
    expert_agreement: float
    confusion_matrix: dict[str, dict[str, int]]
    per_class_recall: dict[str, float]
    metric_results: list[MetricCalibrationResult]
    sample_results: list[SampleEvaluation]
    production_ready: bool
    gate_reasons: list[str]
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
