from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4


class MemoryStatus(StrEnum):
    OPEN = "Open"
    UNDER_REVIEW = "Under Review"
    RESOLVED = "Resolved"
    VERIFIED = "Verified"


class EvidenceType(StrEnum):
    IMAGE = "Image"
    VIDEO = "Video"
    AUDIO = "Audio"
    DOCUMENT = "Document"
    SENSOR_EXPORT = "Sensor Export"


@dataclass(slots=True)
class ProductionContext:
    batch_code: str = ""
    production_line: str = ""
    shift_name: str = ""
    operator_name: str = ""
    machine_name: str = ""
    recipe_name: str = ""
    supplier_name: str = ""
    process_stage: str = ""
    sku: str = ""
    lot_code: str = ""


@dataclass(slots=True)
class ProcessSnapshot:
    temperature_c: float | None = None
    humidity_pct: float | None = None
    pressure_bar: float | None = None
    vacuum_bar: float | None = None
    line_speed: float | None = None
    dough_temperature_c: float | None = None
    product_weight_g: float | None = None
    custom_values: dict[str, float | str | bool | None] = field(default_factory=dict)

    def numeric_values(self) -> dict[str, float]:
        result: dict[str, float] = {}
        for name in (
            "temperature_c", "humidity_pct", "pressure_bar", "vacuum_bar",
            "line_speed", "dough_temperature_c", "product_weight_g",
        ):
            value = getattr(self, name)
            if value is not None:
                result[name] = float(value)
        for key, value in self.custom_values.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                result[f"custom.{key}"] = float(value)
        return result


@dataclass(slots=True)
class DefectObservation:
    defect_type: str
    severity: str = "Warning"
    confidence: float | None = None
    location: str = ""
    measurement: float | None = None
    unit: str = ""
    description: str = ""


@dataclass(slots=True)
class EvidenceReference:
    file_path: str
    evidence_type: EvidenceType = EvidenceType.IMAGE
    caption: str = ""
    sha256: str = ""


@dataclass(slots=True)
class CorrectiveAction:
    action_type: str
    description: str
    owner: str = ""
    status: str = "Proposed"
    result: str = ""
    performed_at: str | None = None
    verified_by: str = ""
    verified_at: str | None = None


@dataclass(slots=True)
class FactoryMemoryCase:
    product_name: str
    passed: bool
    case_uuid: str = field(default_factory=lambda: str(uuid4()))
    inspection_id: int | None = None
    project_id: int | None = None
    production: ProductionContext = field(default_factory=ProductionContext)
    process: ProcessSnapshot = field(default_factory=ProcessSnapshot)
    defects: list[DefectObservation] = field(default_factory=list)
    measurements: dict[str, float] = field(default_factory=dict)
    evidence: list[EvidenceReference] = field(default_factory=list)
    suspected_causes: list[str] = field(default_factory=list)
    confirmed_cause: str = ""
    corrective_actions: list[CorrectiveAction] = field(default_factory=list)
    operator_notes: str = ""
    qc_notes: str = ""
    qc_approved: bool = False
    qc_approved_by: str = ""
    status: MemoryStatus = MemoryStatus.OPEN
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.product_name.strip():
            raise ValueError("product_name is required")
        if not 0 <= sum(1 for _ in self.defects):
            raise ValueError("invalid defects")
        for defect in self.defects:
            if defect.confidence is not None and not 0 <= defect.confidence <= 1:
                raise ValueError("defect confidence must be between 0 and 1")
        if self.passed and self.defects and any(d.severity.lower() in {"critical", "reject"} for d in self.defects):
            raise ValueError("passed case cannot contain a critical/reject defect")

    def all_numeric_features(self) -> dict[str, float]:
        values = dict(self.measurements)
        values.update(self.process.numeric_values())
        return values


@dataclass(frozen=True, slots=True)
class SimilarMemoryCase:
    case: FactoryMemoryCase
    similarity: float
    matching_signals: tuple[str, ...] = ()
