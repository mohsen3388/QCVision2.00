# VisionQC 2.0.0-sprint1

- Added layered Domain / Application / Infrastructure / Platform architecture.
- Added application composition root and runtime context.
- Added thread-safe Event Bus and lightweight dependency injection.
- Added repository ports and SQLite inspection adapter.
- Added centralized rotating logging.
- Added external plugin contract and loader.
- Preserved all existing UI and legacy module compatibility.
- Added architecture acceptance tests; full suite: 40 passed.

## 1.1.0
- Added Visual Inspection Designer, ROI/project storage, pipeline execution, measurements, decision rules, batch testing and project export.

# Changelog

## 0.4.2 — Sprint 4.1

- Activated Golden Batch in the sidebar and complete ALL FEATURES menu.
- Added approved profile creation from one or more known-good samples.
- Added statistical reference aggregation with metric-specific tolerances.
- Added weighted production-to-Golden comparison.
- Added Match, Review and Mismatch decision-support states.
- Added per-metric deviation traceability and strongest-deviation summary.
- Added SQLite persistence for Golden profiles, metrics, samples and comparisons.
- Added profile deactivation while preserving historical records.
- Added JSON comparison export and automated Golden Batch tests.

## 0.2.4 — Sprint 2.4

- Added first-run setup, local batch workspace, history, diagnostics and Windows packaging improvements.

## 0.4.3 — Sprint 4.3
- Added professional batch PDF reporting.
- Added embedded QR report identity payload.
- Added generated report registry and operational reports UI.
- Upgraded History & Replay with chronological event replay.

## 0.4.4 — Sprint 4.4
- Added Dark and High Contrast themes with persistent appearance settings.
- Added UI scaling preference.
- Added System Health checks for database, storage, and settings.
- Added safe offline backup and restore with validation and safety copy.
- Added global local crash logging.
- Hardened release and installer metadata for the 0.4.4 release candidate.


## 0.5.0 — Sprint 5

- Added offline Management Dashboard.
- Added batch outcome, duration and event KPIs.
- Added date, product, line and operator filters.
- Added daily trend and operational breakdowns.
- Added CSV and JSON dashboard exports.

## 0.6.0 — Sprint 6
- Added offline Statistical Process Control workspace.
- Added persistent quality measurements with batch/product/line context.
- Added control chart, UCL/LCL, specification limits, Cp/Cpk and trend alerts.
- Added SPC CSV export and automated tests.


## 0.7.0 — Sprint 7
- Added production shift management.
- Added production runs and downtime reason tracking.
- Added explainable Availability, Performance, Quality and OEE calculations.
- Added OEE CSV/JSON export and Operations dashboard.

## 0.8.0 — Sprint 8
- Added clean-PC offline deployment workflow.
- Added embedded Microsoft Visual C++ runtime prerequisite.
- Added standalone release verification.
- Added Deployment Readiness diagnostics and export.
- Updated Windows installer to a full offline installer.


## 0.9.0 — Sprint 9
- Added Automation Center for importing analysis JSON directly into SPC.
- Added reusable metric profiles with target, LSL and USL.
- Triggered findings now create auditable process events.
- Added persistent import history and automated integration tests.

## 1.0.0 — Sprint 10
- Added secure offline synchronization packages (`.vqcsync`).
- Added HMAC-SHA256 signatures, SHA-256 integrity checks and key fingerprints.
- Added synchronization queue, package audit history and idempotent import receipts.
- Added optional allow-listed snapshot import and conflict accounting.
- Promoted Secure Synchronization to AVAILABLE in ☰ ALL FEATURES.

## VisionQC 2.0 Sprint 7
- Added AI Factory Engineer orchestration, operational briefings, voice integration, approval gates and escalation events.

## VisionQC 2.0 — Sprint 8

- Added Release Candidate and Production Readiness page.
- Added versioned SQLite migration manager.
- Added append-only operational audit trail.
- Added consolidated release gates, validated backup and report export.
- Added `release_candidate.assessment_completed` domain event.
- Added Sprint 8 automated tests; full suite: 56 passed.

## VisionQC 2.0 Sprint 9
- Added Enterprise Integration Hub, connector registry and health model.
- Added secured localhost REST API, API keys and RBAC.
- Added MQTT, OPC-UA, webhook and secure file-exchange adapters.
- Added enterprise integration audit events and schema migration 3.
- Added Sprint 9 UI, documentation and tests.

## Sprint 10
- Added Industrial Automation service, persistence, UI, safety allow-list, approvals, tasks and audited execution history.
- Fixed Sprint 9 bootstrap audit repository construction.

## 2.0.0 — Sprint 11 Commercial Edition
- Added offline commercial licensing and machine identity.
- Added license integrity, expiry, and machine-mismatch validation.
- Added offline update manifests with SHA-256 package verification.
- Added structured crash reports and expanded support bundles.
- Added Commercial Edition UI, persistence migration 5, audit events, and tests.
- Finalized VisionQC 2.0 product version.


## Hybrid Deep Analysis restoration

`Analyze Deeply` now runs the local VisionQC engine first and automatically requests a Gemini review with the image and local measurements when `GEMINI_API_KEY` is configured. The UI and JSON export retain both results.


Video Temporal Analysis also performs an automatic Gemini review using a representative sampled frame plus the complete local timeline context.
