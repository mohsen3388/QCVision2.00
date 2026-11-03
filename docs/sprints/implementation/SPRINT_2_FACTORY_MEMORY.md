# VisionQC 2.0 — Sprint 2: Factory Memory Foundation

## Goal
Convert every inspection from a disposable result into a durable, auditable and searchable factory knowledge case.

## Delivered
- Rich `FactoryMemoryCase` domain model.
- Production context: batch, line, shift, operator, machine, recipe, supplier, stage, SKU and lot.
- Process snapshot: temperature, humidity, pressure, vacuum, line speed, dough temperature, weight and custom sensor values.
- Structured defect observations with severity, confidence, location and measurement.
- Evidence references for image, video, audio, documents and sensor exports.
- Suspected and confirmed root causes.
- Corrective action lifecycle and QC verification.
- Normalized SQLite persistence with indexes and foreign keys.
- Event publication for capture, corrective action and verification.
- Offline similarity search to retrieve related historical cases.
- Conversion helper from the existing `InspectionCase` model.
- Dependency registration in the Sprint 1 composition root.

## Deliberate boundary
Sprint 2 stores and retrieves factory knowledge. It does not claim automatic root-cause diagnosis. That intelligence will be built on top of verified Factory Memory cases in a later sprint.

## Primary services
- `factory_memory_service.capture(case)`
- `factory_memory_service.find_similar(case)`
- `factory_memory_service.add_corrective_action(case_id, action)`
- `factory_memory_service.confirm_root_cause(case_id, cause, qc_user=...)`

## Acceptance
- Existing VisionQC tests remain green.
- New Factory Memory data survives a complete SQLite round trip.
- QC verification is auditable.
- Similar cases are ranked using product, defect, equipment, recipe, supplier, stage and numeric process signals.
