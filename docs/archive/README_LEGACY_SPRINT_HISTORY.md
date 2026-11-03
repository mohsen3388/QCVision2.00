# Legacy README (historical sprint notes)

This is the README supplied in the source export, retained for history. The current product overview is [here](../../README.md).

---


## VisionQC 2.0 Architecture Foundation

Sprint 1 introduces a backward-compatible layered architecture with a composition root, application context, domain events, dependency injection, repository ports, SQLite/settings adapters, rotating logs and a plugin manager. See [`ARCHITECTURE_SPRINT_1.md`](../../docs/architecture/ARCHITECTURE_SPRINT_1.md) and [`SPRINT_1_ACCEPTANCE.md`](../../docs/sprints/acceptance/SPRINT_1_ACCEPTANCE.md).

# VisionQC

## Version 1.1.0 — Visual Inspection Designer
Create offline inspection projects, image datasets, ROIs, no-code OpenCV pipelines, explainable decision rules and batch tests.
 1.1.0 — Sprint 5 Management Intelligence

VisionQC is an offline-first Windows desktop application for industrial visual quality control. Sprint 5 introduces the first management intelligence layer while preserving the explainable, local and auditable product architecture.

## Sprint 5 additions

- Management Dashboard available from the sidebar and ☰ ALL FEATURES.
- KPI cards for total, accepted, rejected and open batches.
- Acceptance rate and average completed-batch duration.
- Warning, critical and unacknowledged process-event indicators.
- Filters by date, product, production line and operator.
- Daily production trend and product/line/event breakdowns.
- Offline CSV and JSON export for management review.
- Analytics tests covering KPIs, filters and exports.

## Development

Run `SETUP_DEV_ENV.bat`, then `RUN_VISIONQC.bat`.

Run tests with `RUN_TESTS.bat` or `pytest`.

Build the Windows release with `BUILD_RELEASE.bat`. The expected installer is `VisionQC_Setup_0.5.0.exe`.

## Safety boundary

VisionQC is decision-support software. Dashboard indicators do not replace laboratory testing, qualified QC judgement or approved factory release procedures.


## Sprint 6 — Statistical Process Control

VisionQC 1.1.0 adds shift definitions, production-run tracking, downtime categorization and explainable Overall Equipment Effectiveness (OEE) analytics.


## Sprint 7 — Production Operations & OEE

- Configurable production shifts and planned breaks
- Production-run records with line, product, operator, ideal cycle time and quantities
- Planned/unplanned downtime events with reason categories
- Availability, Performance, Quality and OEE calculation
- CSV and JSON OEE export


## Clean Windows installation (Sprint 8)
The final installer is designed for a 64-bit Windows 10/11 computer with no Python or specialist development software installed. It contains the packaged Python runtime and all application libraries. The build process also embeds the Microsoft Visual C++ 2015-2022 x64 runtime, so the destination computer does not need internet access during installation.

Build the complete offline installer with `BUILD_RELEASE.bat`. The expected output is `installer\VisionQC_Setup_1.0.0_Offline.exe`. Camera hardware may still require a manufacturer driver if Windows does not already provide one.


## VisionQC 2.0 Sprint 7 — AI Factory Engineer

The AI Factory Engineer coordinates Factory Memory, Root Cause Intelligence,
Factory Knowledge Graph and Predictive Quality into one operational briefing.
It produces prioritized actions, proposed owner roles, verification criteria,
evidence and mandatory human decision gates. It does not autonomously control
factory equipment or alter approved process parameters.

## VisionQC 2.0 Release Candidate

Open **Navigate → Quality → Release Candidate** before deployment. Run the release assessment, resolve required failures, export the readiness report, and retain the automatically generated validated backup. A Ready result is a software readiness gate and does not replace factory SAT/UAT or regulated validation activities.

## VisionQC 2.0 Sprint 9 — Enterprise Integration

Open **Navigate → Configuration → Enterprise Integration** to review connector health, start the secured local REST API and manage API keys. See [`SPRINT_9_ENTERPRISE_INTEGRATION.md`](../../docs/sprints/implementation/SPRINT_9_ENTERPRISE_INTEGRATION.md) for endpoints and commissioning boundaries.

## VisionQC 2.0 Sprint 10 — Industrial Automation

Added fail-safe event rules, approval gates, operational task creation, execution history, audited webhook actions, and schema migration 4.

## VisionQC 2.0 Commercial Edition
Sprint 11 completes the Version 2 roadmap with offline licensing, verified offline update manifests, structured crash reporting, diagnostics bundles, and product operations. Commercial activation does not replace factory acceptance, cybersecurity, calibration, food-safety, or qualified QC validation.


## Hybrid Deep Analysis restoration

`Analyze Deeply` now runs the local VisionQC engine first and automatically requests a Gemini review with the image and local measurements when `GEMINI_API_KEY` is configured. The UI and JSON export retain both results.


Video Temporal Analysis also performs an automatic Gemini review using a representative sampled frame plus the complete local timeline context.
