# VisionQC 2.0 — Sprint 8: Release Candidate & Production Readiness

Sprint 8 turns the integrated VisionQC intelligence stack into a controlled release candidate for factory deployment.

## Delivered

- Versioned, idempotent SQLite migrations (`schema_migrations`)
- Append-only operational audit trail
- Release readiness orchestration service
- Required versus advisory release gates
- Automatic validated pre-release backup
- SQLite integrity and schema-version checks
- Deployment and health checks consolidated into one report
- JSON readiness report export
- Release Candidate UI page with readiness and audit tabs
- Domain event: `release_candidate.assessment_completed`

## Release gate policy

A release is **Blocked** when a required check fails. It is **Attention** when all required checks pass but one or more advisory checks need review. It is **Ready** only when all checks pass.

The assessment does not claim that a workstation has passed factory SAT/UAT. It verifies the software and local workstation prerequisites that VisionQC can evaluate automatically.
