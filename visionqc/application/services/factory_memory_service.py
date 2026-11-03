from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import math

from visionqc.application.ports.event_bus import EventBus
from visionqc.application.ports.factory_memory import FactoryMemoryRepository
from visionqc.domain.events import DomainEvent
from visionqc.domain.factory_memory import CorrectiveAction, FactoryMemoryCase, MemoryStatus, SimilarMemoryCase


class FactoryMemoryService:
    """Use cases for capturing, reviewing and retrieving factory knowledge."""

    def __init__(self, repository: FactoryMemoryRepository, event_bus: EventBus) -> None:
        self._repository = repository
        self._event_bus = event_bus

    def capture(self, case: FactoryMemoryCase) -> int:
        case.validate()
        case_id = self._repository.save(case)
        self._event_bus.publish(DomainEvent(
            name="factory_memory.case_captured",
            source="factory_memory_service",
            payload={
                "case_id": case_id,
                "case_uuid": case.case_uuid,
                "product_name": case.product_name,
                "passed": case.passed,
                "defects": [d.defect_type for d in case.defects],
            },
        ))
        return case_id

    def add_corrective_action(self, case_id: int, action: CorrectiveAction) -> FactoryMemoryCase:
        case = self._require(case_id)
        case.corrective_actions.append(action)
        case.status = MemoryStatus.UNDER_REVIEW
        case.updated_at = self._now()
        self._repository.update(case_id, case)
        self._event_bus.publish(DomainEvent(
            name="factory_memory.corrective_action_added",
            source="factory_memory_service",
            payload={"case_id": case_id, "action_type": action.action_type, "owner": action.owner},
        ))
        return case

    def confirm_root_cause(self, case_id: int, cause: str, *, qc_user: str, notes: str = "") -> FactoryMemoryCase:
        if not cause.strip():
            raise ValueError("cause is required")
        case = self._require(case_id)
        case.confirmed_cause = cause.strip()
        case.qc_notes = notes
        case.qc_approved = True
        case.qc_approved_by = qc_user
        case.status = MemoryStatus.VERIFIED
        case.updated_at = self._now()
        self._repository.update(case_id, case)
        self._event_bus.publish(DomainEvent(
            name="factory_memory.case_verified",
            source="factory_memory_service",
            payload={"case_id": case_id, "confirmed_cause": case.confirmed_cause, "qc_user": qc_user},
        ))
        return case

    def find_similar(self, query: FactoryMemoryCase, *, limit: int = 5, minimum_similarity: float = 0.25) -> list[SimilarMemoryCase]:
        candidates = self._repository.list_recent(max(100, limit * 20), product_name=query.product_name)
        ranked: list[SimilarMemoryCase] = []
        for candidate in candidates:
            if candidate.case_uuid == query.case_uuid:
                continue
            score, signals = self._similarity(query, candidate)
            if score >= minimum_similarity:
                ranked.append(SimilarMemoryCase(candidate, round(score, 4), tuple(signals)))
        ranked.sort(key=lambda item: item.similarity, reverse=True)
        return ranked[:limit]


    def record_action_outcome(self, case_id: int, action_index: int, *, result: str, verified_by: str, effective: bool) -> FactoryMemoryCase:
        case = self._require(case_id)
        if action_index < 0 or action_index >= len(case.corrective_actions):
            raise IndexError("corrective action index is out of range")
        if not verified_by.strip():
            raise ValueError("verified_by is required")
        action = case.corrective_actions[action_index]
        action.result = result.strip() or ("Effective" if effective else "Ineffective")
        action.status = "Effective" if effective else "Ineffective"
        action.verified_by = verified_by.strip()
        action.verified_at = self._now()
        case.status = MemoryStatus.RESOLVED if effective else MemoryStatus.UNDER_REVIEW
        case.updated_at = self._now()
        self._repository.update(case_id, case)
        self._event_bus.publish(DomainEvent(
            name="factory_memory.action_outcome_recorded", source="factory_memory_service",
            payload={"case_id": case_id, "action_index": action_index, "effective": effective, "verified_by": verified_by},
        ))
        return case

    def close_case(self, case_id: int, *, qc_user: str, notes: str = "") -> FactoryMemoryCase:
        case = self._require(case_id)
        if not qc_user.strip():
            raise ValueError("qc_user is required")
        case.status = MemoryStatus.VERIFIED
        case.qc_approved = True
        case.qc_approved_by = qc_user.strip()
        if notes.strip():
            case.qc_notes = notes.strip()
        case.updated_at = self._now()
        self._repository.update(case_id, case)
        self._event_bus.publish(DomainEvent(
            name="factory_memory.case_closed", source="factory_memory_service",
            payload={"case_id": case_id, "qc_user": qc_user},
        ))
        return case

    def attach_root_cause_analysis(self, case_id: int, analysis: dict) -> FactoryMemoryCase:
        case = self._require(case_id)
        case.metadata["root_cause_analysis"] = analysis
        case.updated_at = self._now()
        self._repository.update(case_id, case)
        return case

    def attach_factory_engineer_briefing(self, case_id: int, briefing: dict) -> FactoryMemoryCase:
        case = self._require(case_id)
        case.metadata["factory_engineer_briefing"] = briefing
        case.updated_at = self._now()
        self._repository.update(case_id, case)
        return case

    def get(self, case_id: int) -> FactoryMemoryCase | None:
        return self._repository.get(case_id)

    def list_recent(self, limit: int = 100, *, product_name: str | None = None) -> list[FactoryMemoryCase]:
        return self._repository.list_recent(limit, product_name=product_name)

    def _require(self, case_id: int) -> FactoryMemoryCase:
        case = self._repository.get(case_id)
        if case is None:
            raise KeyError(f"Factory memory case {case_id} was not found")
        return case

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    @staticmethod
    def _similarity(a: FactoryMemoryCase, b: FactoryMemoryCase) -> tuple[float, list[str]]:
        weighted = 0.0
        total = 0.0
        signals: list[str] = []

        def categorical(label: str, av: str, bv: str, weight: float) -> None:
            nonlocal weighted, total
            if not av or not bv:
                return
            total += weight
            if av.casefold() == bv.casefold():
                weighted += weight
                signals.append(label)

        categorical("same product", a.product_name, b.product_name, 3.0)
        categorical("same line", a.production.production_line, b.production.production_line, 1.2)
        categorical("same machine", a.production.machine_name, b.production.machine_name, 1.5)
        categorical("same recipe", a.production.recipe_name, b.production.recipe_name, 1.5)
        categorical("same supplier", a.production.supplier_name, b.production.supplier_name, 0.8)
        categorical("same process stage", a.production.process_stage, b.production.process_stage, 1.0)
        categorical("same shift", a.production.shift_name, b.production.shift_name, 0.5)

        a_defects = {d.defect_type.casefold() for d in a.defects}
        b_defects = {d.defect_type.casefold() for d in b.defects}
        if a_defects or b_defects:
            total += 3.0
            union = a_defects | b_defects
            overlap = a_defects & b_defects
            if union:
                defect_score = len(overlap) / len(union)
                weighted += 3.0 * defect_score
                if overlap:
                    signals.append("matching defects: " + ", ".join(sorted(overlap)))

        av = a.all_numeric_features(); bv = b.all_numeric_features()
        shared = set(av) & set(bv)
        if shared:
            feature_scores = []
            for key in shared:
                x, y = av[key], bv[key]
                scale = max(abs(x), abs(y), 1.0)
                feature_scores.append(max(0.0, 1.0 - abs(x-y)/scale))
            numeric_score = sum(feature_scores) / len(feature_scores)
            total += 2.5
            weighted += 2.5 * numeric_score
            if numeric_score >= .75:
                signals.append("similar process measurements")

        if total == 0:
            return 0.0, []
        return max(0.0, min(1.0, weighted / total)), signals
