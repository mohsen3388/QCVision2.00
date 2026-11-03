# VisionQC 2.0 — Sprint 1 Architecture Foundation

## Objective
Separate orchestration, domain concepts, infrastructure, platform services and UI without breaking the existing desktop application.

## New layers

- `visionqc/domain`: technology-neutral events and quality-inspection entities.
- `visionqc/application`: use cases and ports (interfaces) used by the business workflow.
- `visionqc/infrastructure`: SQLite and JSON adapters.
- `visionqc/platform`: dependency injection, event bus and logging.
- `visionqc/plugins`: safe extension contract and external plugin loader.
- `visionqc/bootstrap.py`: composition root that wires the application once.
- `visionqc/runtime.py`: controlled access to the active application context.
- `visionqc/ui`: presentation layer; remains compatible with current pages.
- `visionqc/core`, `visionqc/analysis`, `visionqc/ai`, `visionqc/capture`: legacy-compatible modules to be migrated incrementally in later sprints.

## Runtime flow

1. `main.py` creates Qt.
2. `bootstrap_application()` configures rotating logs, initializes storage, creates the container and loads plugins.
3. `ApplicationContext` is supplied to `MainWindow`.
4. New use cases publish domain events rather than coupling modules directly.

## Registered services

- `settings_provider`
- `settings`
- `event_bus`
- `inspection_repository`
- `inspection_service`
- `plugin_manager`

## Event convention
Use lowercase dotted names, for example:

- `camera.frame_captured`
- `inspection.started`
- `inspection.completed`
- `quality.alert_raised`
- `batch.closed`

## Compatibility rule
Existing imports remain valid. New development must target application ports and services; direct UI-to-database dependencies should be removed incrementally.
