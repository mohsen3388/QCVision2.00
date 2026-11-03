# VisionQC Sprint 4.2 Acceptance — Version 0.4.2

## Delivered
- Local Factory Knowledge Engine with product/stage scope and optional metric windows.
- Knowledge CRUD, enable/disable and explainable relevance matching.
- Auditable Event Engine with severity, source, JSON details and acknowledgement.
- Event Timeline UI, filters and JSON export.
- Persistent SQLite tables: `knowledge_entries` and `process_events`.
- Navigation from the permanent ALL FEATURES menu and sidebar.

## Safety boundary
Knowledge entries and events are decision-support evidence. VisionQC does not autonomously change production equipment or replace qualified QC approval.

## Deferred
Automatic knowledge learning from accepted batches, media-linked replay, voice notes, PDF reports and PLC/SCADA integration.
