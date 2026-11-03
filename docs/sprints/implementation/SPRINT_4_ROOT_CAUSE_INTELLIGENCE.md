# VisionQC 2.0 — Sprint 4: Root Cause Intelligence

## Goal
Provide offline-first, explainable root-cause decision support grounded in QC-verified Factory Memory.

## Delivered
- Evidence-weighted hypothesis ranking
- Confidence bands and normalized scores
- QC-verified similar-case evidence
- Process-deviation evidence against accepted-case references
- Controlled defect checklists when verified history is insufficient
- Recommended checks/actions from effective historical actions
- Explicit limitations and safety note
- Persistence of analysis inside the Factory Memory case metadata
- Domain event: `root_cause.analysis_completed`
- New Root Cause Intelligence UI page
- Voice AI integration for “why/root cause/what should I check” questions

## Safety boundary
VisionQC never automatically confirms a root cause. Final confirmation remains a qualified QC/process-engineering action.
