# VisionQC Sprint 5 Acceptance — Version 0.5.0

## Goal
Deliver an offline management dashboard that converts locally stored batch and event records into auditable operational KPIs without cloud dependencies.

## Accepted scope

- Management Dashboard is directly available in the sidebar and ☰ ALL FEATURES.
- KPI calculation for total, finished, open, accepted, rejected and undecided batches.
- Acceptance rate based on decided batches only.
- Average duration based only on batches with valid start and end timestamps.
- Warning, critical and unacknowledged event indicators.
- Filtering by date range, product, line and operator.
- Daily trend, product distribution, line distribution and top event types.
- CSV and JSON export.
- No network connection required.

## Explicitly deferred

- Shift-calendar configuration.
- OEE and machine telemetry.
- Statistical process control charts and configurable control limits.
- Multi-site synchronization and remote web dashboard.
- Role-based access control.

## Validation

Automated tests cover KPI calculations, filtering and export file creation. All legacy tests must remain green.
