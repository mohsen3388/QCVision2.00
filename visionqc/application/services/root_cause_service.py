from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
import math

from visionqc.application.ports.event_bus import EventBus
from visionqc.application.services.factory_memory_service import FactoryMemoryService
from visionqc.domain.events import DomainEvent
from visionqc.domain.factory_memory import FactoryMemoryCase
from visionqc.domain.root_cause import CauseEvidence, CauseHypothesis, ConfidenceBand, RootCauseAnalysis
from visionqc.domain.knowledge_graph import NodeType


class RootCauseIntelligenceService:
    """Explainable, offline-first root-cause decision support.

    Scores causes from QC-verified similar cases, matching defects and process
    conditions. It never marks a cause as confirmed automatically.
    """

    FALLBACKS: dict[str, list[tuple[str, list[str]]]] = {
        "casing tear": [("Casing tension or handling instability", ["Check casing tension and alignment", "Inspect stuffing horn and clipping path"]), ("Worn or damaged cutting component", ["Inspect cutter and contact surfaces", "Compare defect rate before and after blade change"])],
        "wrinkle": [("Insufficient filling pressure or vacuum", ["Verify filling pressure and vacuum", "Check trapped air and emulsion consistency"])],
        "diameter": [("Filling pressure or portioning instability", ["Check filler calibration", "Verify line speed and recipe viscosity"])],
        "color": [("Recipe, temperature or mixing deviation", ["Verify recipe identity and ingredient lot", "Check dough temperature and mixing time"])],
        "seal": [("Sealing temperature, pressure or contamination", ["Inspect seal surface", "Verify temperature and dwell time"])],
    }

    def __init__(self, memory: FactoryMemoryService, event_bus: EventBus, knowledge_graph=None) -> None:
        self._memory = memory
        self._event_bus = event_bus
        self._knowledge_graph = knowledge_graph

    def analyze(self, case_id: int, *, limit: int = 5) -> RootCauseAnalysis:
        current = self._memory.get(case_id)
        if current is None:
            raise KeyError(f"Factory memory case {case_id} was not found")
        similar = self._memory.find_similar(current, limit=30, minimum_similarity=0.12)
        buckets: dict[str, dict] = defaultdict(lambda: {"score": 0.0, "evidence": [], "actions": [], "verified": 0})

        for item in similar:
            historical = item.case
            if not historical.qc_approved or not historical.confirmed_cause.strip():
                continue
            cause = historical.confirmed_cause.strip()
            if self._knowledge_graph is not None:
                cause = self._knowledge_graph.canonicalize(NodeType.CAUSE, cause)
            verification_weight = 1.15 if historical.status.value == "Verified" else 1.0
            effectiveness = 1.0
            effective_actions = []
            for action in historical.corrective_actions:
                if action.result or action.status.casefold() in {"completed", "verified", "effective"}:
                    effectiveness += 0.08
                    effective_actions.append(action.description)
            contribution = item.similarity * verification_weight * min(effectiveness, 1.35)
            bucket = buckets[cause]
            bucket["score"] += contribution
            bucket["verified"] += 1
            bucket["actions"].extend(effective_actions)
            bucket["evidence"].append(CauseEvidence(
                signal=f"QC-verified similar case ({item.similarity*100:.0f}% similarity)",
                contribution=round(contribution, 4),
                explanation=", ".join(item.matching_signals) or "similar product and process context",
                source_case_uuid=historical.case_uuid,
            ))

        if self._knowledge_graph is not None:
            try:
                if self._knowledge_graph.summary().node_count == 0:
                    self._knowledge_graph.rebuild_from_factory_memory()
                defect_nodes = {n.canonical_name: n for n in self._knowledge_graph.nodes(NodeType.DEFECT, 1000)}
                for defect in current.defects:
                    canonical_defect = self._knowledge_graph.canonicalize(NodeType.DEFECT, defect.defect_type)
                    node = defect_nodes.get(canonical_defect)
                    if node is None:
                        continue
                    for path in self._knowledge_graph.find_paths(node.node_id, NodeType.CAUSE, max_depth=2, limit=5):
                        cause_node = path.nodes[-1]
                        data = buckets[cause_node.display_name]
                        contribution = min(.32, .08 + .04 * path.score)
                        data["score"] += contribution
                        data["verified"] += sum(e.verified_count for e in path.edges)
                        data["evidence"].append(CauseEvidence(
                            signal="Factory Knowledge Graph path", contribution=round(contribution,4),
                            explanation=path.explanation))
                        for action_path in self._knowledge_graph.find_paths(cause_node.node_id, NodeType.ACTION, max_depth=1, limit=4):
                            data["actions"].append(action_path.nodes[-1].display_name)
            except Exception:
                pass

        self._add_process_deviation_evidence(current, similar, buckets)
        self._add_controlled_fallbacks(current, buckets)

        if not buckets:
            buckets["Insufficient verified factory evidence"] = {
                "score": .12,
                "evidence": [CauseEvidence("No verified analogue", .12, "Factory Memory needs confirmed cases and corrective-action outcomes")],
                "actions": ["Validate camera and lighting", "Record process measurements", "Escalate to QC/process engineering"],
                "verified": 0,
            }

        maximum = max(float(v["score"]) for v in buckets.values()) or 1.0
        hypotheses: list[CauseHypothesis] = []
        for cause, data in buckets.items():
            normalized = min(0.99, float(data["score"]) / maximum * (0.88 if data["verified"] else 0.52))
            band = ConfidenceBand.HIGH if normalized >= .72 and data["verified"] >= 2 else ConfidenceBand.MEDIUM if normalized >= .42 else ConfidenceBand.LOW
            opposing = []
            if not data["verified"]:
                opposing.append("No QC-verified historical case supports this hypothesis yet")
            if len(current.defects) == 0:
                opposing.append("No structured defect observation is stored for the current case")
            actions = list(dict.fromkeys(a for a in data["actions"] if a.strip()))[:5]
            hypotheses.append(CauseHypothesis(cause, round(normalized, 4), band, data["evidence"][:8], opposing, actions, int(data["verified"])))
        hypotheses.sort(key=lambda h: (h.score, h.verified_case_count), reverse=True)
        analysis = RootCauseAnalysis(case_id, current.case_uuid, hypotheses[:limit])
        self._memory.attach_root_cause_analysis(case_id, asdict(analysis))
        self._event_bus.publish(DomainEvent(name="root_cause.analysis_completed", source="root_cause_service", payload={"case_id": case_id, "top_cause": analysis.top_hypothesis.cause if analysis.top_hypothesis else "", "hypothesis_count": len(analysis.hypotheses)}))
        return analysis

    @staticmethod
    def _add_process_deviation_evidence(current: FactoryMemoryCase, similar, buckets: dict) -> None:
        current_values = current.all_numeric_features()
        if not current_values:
            return
        references: dict[str, list[float]] = defaultdict(list)
        for item in similar:
            if item.case.passed:
                for key, value in item.case.all_numeric_features().items():
                    references[key].append(value)
        deviations = []
        for key, value in current_values.items():
            vals = references.get(key, [])
            if len(vals) < 3:
                continue
            mean = sum(vals) / len(vals)
            variance = sum((v-mean)**2 for v in vals) / len(vals)
            sd = math.sqrt(variance)
            if sd > 1e-9:
                z = abs(value-mean)/sd
                if z >= 1.5:
                    deviations.append((key, value, mean, z))
        for cause, data in buckets.items():
            for key, value, mean, z in deviations[:4]:
                contribution = min(.18, .04*z)
                data["score"] += contribution
                data["evidence"].append(CauseEvidence(f"Process deviation: {key}", round(contribution,4), f"Current {value:.3g}; accepted-case mean {mean:.3g}; deviation {z:.1f} standard deviations"))

    def _add_controlled_fallbacks(self, current: FactoryMemoryCase, buckets: dict) -> None:
        for defect in current.defects:
            name = defect.defect_type.casefold()
            for keyword, candidates in self.FALLBACKS.items():
                if keyword in name:
                    for cause, actions in candidates:
                        data = buckets[cause]
                        base = .18 + (.08 if defect.severity.casefold() in {"reject", "critical"} else 0)
                        data["score"] += base
                        data["actions"].extend(actions)
                        data["evidence"].append(CauseEvidence(f"Controlled defect rule: {defect.defect_type}", base, "Industry-oriented inspection checklist; requires local validation"))
