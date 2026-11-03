from __future__ import annotations

from pathlib import Path

from visionqc.domain.factory_memory import (
    DefectObservation, EvidenceReference, EvidenceType, FactoryMemoryCase,
    ProcessSnapshot, ProductionContext,
)
from visionqc.domain.models import InspectionCase


def factory_memory_from_inspection(
    inspection: InspectionCase,
    *,
    production: ProductionContext | None = None,
    process: ProcessSnapshot | None = None,
    suspected_causes: list[str] | None = None,
    operator_notes: str = "",
) -> FactoryMemoryCase:
    """Convert legacy/current inspection output into a rich memory case."""
    defects = [DefectObservation(defect_type=reason, severity="Reject" if not inspection.passed else "Information") for reason in inspection.reasons]
    evidence = []
    if inspection.image_path:
        evidence.append(EvidenceReference(file_path=inspection.image_path, evidence_type=EvidenceType.IMAGE, caption=Path(inspection.image_path).name))
    return FactoryMemoryCase(
        inspection_id=inspection.metadata.get("inspection_id"),
        project_id=inspection.metadata.get("project_id"),
        product_name=inspection.product_name,
        passed=inspection.passed,
        production=production or ProductionContext(batch_code=str(inspection.batch_id or "")),
        process=process or ProcessSnapshot(),
        defects=defects,
        measurements=dict(inspection.measurements),
        evidence=evidence,
        suspected_causes=list(suspected_causes or []),
        operator_notes=operator_notes,
        metadata=dict(inspection.metadata),
    )
