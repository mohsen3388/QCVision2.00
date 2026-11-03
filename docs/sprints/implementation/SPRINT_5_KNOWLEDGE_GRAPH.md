# VisionQC 2.0 — Sprint 5: Factory Knowledge Graph

## Goal
Turn Factory Memory records into an offline, explainable relationship graph connecting products, defects, confirmed causes, corrective actions, machines, lines, shifts, recipes, suppliers and process stages.

## Delivered
- SQLite-backed graph repository with replaceable port/adapter boundary.
- Canonical terminology and alias resolution for common factory cause variants.
- Graph rebuilding from Factory Memory without changing source records.
- Weighted and QC-verified relationships.
- Path search from defect to cause and from cause to corrective action.
- Root Cause Intelligence enrichment with graph evidence.
- Factory Knowledge Graph user interface with entity filters and relationship inspection.
- Domain events for graph rebuild completion.

## Safety boundary
The graph records relationships observed in factory history. It does not prove causality and never bypasses QC verification.
