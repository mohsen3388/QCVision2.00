# VisionQC Sprint 4.1 Acceptance

Version: 0.4.1

## Delivered

- Offline Operator Assistant using deterministic, explainable responses.
- Analysis JSON context loading.
- Questions for quality drop, abnormal metrics, bubble candidates and recommended actions.
- Evidence, confidence and safety note in every assistant answer.
- No-code single-condition Factory Rule Builder.
- Rule operators: >, >=, <, <=, ==, != and between.
- Optional product and process-stage scope.
- Local SQLite persistence, enable/disable and deletion.
- Runtime evaluation of saved factory rules against loaded analysis metrics.
- Operator Assistant available from ALL FEATURES and main navigation.

## Safety boundary

The assistant does not use a cloud LLM and does not control production equipment. It provides visual decision support only. Recommendations must be confirmed by qualified production/QC personnel.

## Deferred

- Voice input/output.
- Multi-condition visual editor in the desktop UI (the core engine already supports AND/OR lists).
- Direct live-context handoff from camera/video pages.
- Factory-specific validated thresholds and laboratory correlation.
