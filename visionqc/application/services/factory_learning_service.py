from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime

from visionqc.application.services.factory_memory_service import FactoryMemoryService
from visionqc.domain.factory_learning import (
    ActionInsight, FactoryLearningSummary, LearnedRecommendation, RankedInsight,
)
from visionqc.domain.factory_memory import FactoryMemoryCase


_EFFECTIVE = {"effective", "verified", "successful", "resolved", "completed"}
_INEFFECTIVE = {"ineffective", "failed", "not effective", "unsuccessful"}


class FactoryLearningService:
    """Aggregate QC-verified Factory Memory into explainable operational learning.

    This service intentionally avoids claiming causality. It reports associations
    from recorded and QC-verified cases and exposes data sufficiency limitations.
    """

    def __init__(self, memory: FactoryMemoryService) -> None:
        self._memory = memory

    def summarize(self, *, product_name: str | None = None, limit: int = 5000) -> FactoryLearningSummary:
        cases = self._memory.list_recent(limit, product_name=product_name)
        rejected = [c for c in cases if not c.passed]
        verified = [c for c in cases if c.qc_approved and c.confirmed_cause.strip()]
        resolved = [c for c in cases if c.status.value in {"Resolved", "Verified"}]

        cause_counter = Counter(c.confirmed_cause.strip() for c in verified if c.confirmed_cause.strip())
        defect_counter = Counter(d.defect_type.strip() for c in rejected for d in c.defects if d.defect_type.strip())
        machine_counter = Counter(c.production.machine_name.strip() for c in rejected if c.production.machine_name.strip())
        shift_counter = Counter(c.production.shift_name.strip() for c in rejected if c.production.shift_name.strip())

        action_groups: dict[str, dict] = defaultdict(lambda: {"attempts": 0, "effective": 0, "ineffective": 0, "last": ""})
        for case in cases:
            for action in case.corrective_actions:
                key = (action.action_type or action.description or "Unclassified action").strip()
                row = action_groups[key]
                row["attempts"] += 1
                result = (action.result or action.status or "").strip()
                row["last"] = result
                normalized = result.casefold()
                if normalized in _INEFFECTIVE or any(token in normalized for token in ("ineffective", "ناموثر", "failed")):
                    row["ineffective"] += 1
                elif normalized in _EFFECTIVE or any(token in normalized for token in ("effective", "موثر", "رفع شد", "successful")):
                    row["effective"] += 1

        judged = sum(v["effective"] + v["ineffective"] for v in action_groups.values())
        effective = sum(v["effective"] for v in action_groups.values())
        action_rate = round(100.0 * effective / judged, 1) if judged else 0.0
        recurrence_rate = self._recurrence_rate(rejected)
        limitations = []
        if len(cases) < 30:
            limitations.append("Fewer than 30 memory cases are available; trends are preliminary.")
        if len(verified) < 10:
            limitations.append("Fewer than 10 QC-verified root causes are available; cause ranking is low confidence.")
        if judged < 10:
            limitations.append("Fewer than 10 corrective actions have an effectiveness outcome.")

        return FactoryLearningSummary(
            total_cases=len(cases), rejected_cases=len(rejected), verified_cases=len(verified),
            resolved_cases=len(resolved), verification_rate=self._pct(len(verified), len(rejected)),
            recurrence_rate=recurrence_rate, action_effectiveness_rate=action_rate,
            top_causes=self._rank(cause_counter, max(len(verified), 1)),
            top_defects=self._rank(defect_counter, max(len(rejected), 1)),
            machine_hotspots=self._rank(machine_counter, max(len(rejected), 1)),
            shift_hotspots=self._rank(shift_counter, max(len(rejected), 1)),
            action_insights=tuple(sorted((ActionInsight(
                action_type=k, attempts=v["attempts"], effective=v["effective"], ineffective=v["ineffective"],
                effectiveness_rate=self._pct(v["effective"], v["effective"] + v["ineffective"]), last_result=v["last"],
            ) for k, v in action_groups.items()), key=lambda x: (x.effectiveness_rate, x.attempts), reverse=True)),
            limitations=tuple(limitations),
        )

    def recommend_actions(self, case_id: int, *, limit: int = 5) -> list[LearnedRecommendation]:
        current = self._memory.get(case_id)
        if current is None:
            raise KeyError(f"Factory memory case {case_id} was not found")
        similar = self._memory.find_similar(current, limit=100, minimum_similarity=0.20)
        groups: dict[tuple[str, str], dict] = defaultdict(lambda: {"support": 0, "effective": 0, "judged": 0, "weighted": 0.0, "evidence": []})
        for item in similar:
            case = item.case
            if not case.qc_approved:
                continue
            for action in case.corrective_actions:
                key = ((action.action_type or "Corrective action").strip(), action.description.strip())
                row = groups[key]
                row["support"] += 1
                row["weighted"] += item.similarity
                result = (action.result or action.status or "").casefold()
                if result:
                    if any(token in result for token in ("ineffective", "failed", "ناموثر")):
                        row["judged"] += 1
                    elif any(token in result for token in ("effective", "verified", "successful", "موثر", "رفع شد")):
                        row["effective"] += 1; row["judged"] += 1
                row["evidence"].append(f"similarity {item.similarity:.0%}; batch {case.production.batch_code or '-'}")
        results = []
        for (action_type, description), row in groups.items():
            effectiveness = row["effective"] / row["judged"] if row["judged"] else 0.0
            similarity = row["weighted"] / row["support"] if row["support"] else 0.0
            confidence = min(0.95, 0.55 * similarity + 0.30 * effectiveness + 0.15 * min(1.0, row["support"] / 5.0))
            results.append(LearnedRecommendation(
                action_type=action_type, description=description, support_count=row["support"],
                effectiveness_rate=round(effectiveness * 100, 1), confidence=round(confidence * 100, 1),
                evidence=tuple(row["evidence"][:4]),
            ))
        results.sort(key=lambda r: (r.confidence, r.effectiveness_rate, r.support_count), reverse=True)
        return results[:limit]

    @staticmethod
    def _rank(counter: Counter, denominator: int, limit: int = 10) -> tuple[RankedInsight, ...]:
        return tuple(RankedInsight(label=k, count=v, percentage=round(100.0 * v / denominator, 1)) for k, v in counter.most_common(limit))

    @staticmethod
    def _pct(numerator: int, denominator: int) -> float:
        return round(100.0 * numerator / denominator, 1) if denominator else 0.0

    @staticmethod
    def _recurrence_rate(cases: list[FactoryMemoryCase]) -> float:
        """Percentage of rejected cases whose primary defect occurred previously on same product/machine."""
        ordered = sorted(cases, key=lambda c: c.created_at)
        seen: set[tuple[str, str, str]] = set()
        recurrent = 0; eligible = 0
        for case in ordered:
            machine = case.production.machine_name.casefold().strip()
            product = case.product_name.casefold().strip()
            for defect in case.defects:
                key = (product, machine, defect.defect_type.casefold().strip())
                eligible += 1
                if key in seen:
                    recurrent += 1
                seen.add(key)
        return round(100.0 * recurrent / eligible, 1) if eligible else 0.0
