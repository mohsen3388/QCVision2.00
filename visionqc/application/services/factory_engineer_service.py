from __future__ import annotations

from dataclasses import asdict

from visionqc.application.ports.event_bus import EventBus
from visionqc.application.services.factory_memory_service import FactoryMemoryService
from visionqc.domain.events import DomainEvent
from visionqc.domain.factory_engineer import EngineerAction, FactoryEngineerBriefing, OperationalPriority
from visionqc.domain.predictive_quality import RiskBand


class AIFactoryEngineerService:
    """Coordinates VisionQC intelligence into one evidence-backed operational briefing.

    The service does not autonomously change process parameters or stop equipment.
    It converts inspection history, predictive risk, root-cause hypotheses and
    factory knowledge into a prioritized plan with explicit human approval gates.
    """

    def __init__(self, memory: FactoryMemoryService, predictive_quality, root_cause,
                 knowledge_graph, event_bus: EventBus) -> None:
        self._memory = memory
        self._predictive = predictive_quality
        self._root_cause = root_cause
        self._knowledge_graph = knowledge_graph
        self._event_bus = event_bus

    def generate_briefing(self, *, case_id: int | None = None, product_name: str | None = None,
                          line: str | None = None, machine: str | None = None) -> FactoryEngineerBriefing:
        selected = self._memory.get(case_id) if case_id is not None else None
        if case_id is not None and selected is None:
            raise KeyError(f"Factory memory case {case_id} was not found")
        if selected is not None:
            product_name = product_name or selected.product_name
            line = line or selected.production.production_line or None
            machine = machine or selected.production.machine_name or None

        forecast = self._predictive.forecast(product_name=product_name, line=line, machine=machine)
        analysis = self._root_cause.analyze(case_id, limit=3) if case_id is not None and selected and not selected.passed else None
        top = analysis.top_hypothesis if analysis is not None else None
        recent = self._memory.list_recent(50, product_name=product_name)
        rejected = [c for c in recent if not c.passed]
        reject_rate = len(rejected) / len(recent) if recent else 0.0

        priority = self._priority(forecast.risk_band, selected)
        scope = forecast.scope
        quality_status = (
            f"Selected case is {'accepted' if selected.passed else 'rejected'}; "
            f"{len(selected.defects)} structured defect(s) recorded."
            if selected else
            f"{len(recent)} recent comparable cases; reject rate {reject_rate*100:.1f}%."
        )
        forecast_summary = (
            f"{forecast.risk_band.value} risk ({forecast.risk_score*100:.0f}% score), "
            f"predicted reject rate {forecast.predicted_reject_rate*100:.1f}% "
            f"for the {forecast.horizon}; trend {forecast.trend}."
        )
        root_summary = (
            f"Leading hypothesis: {top.cause} — {top.confidence.value} confidence "
            f"({top.score*100:.0f}%). Not confirmed until QC verification."
            if top else
            "No case-specific root-cause hypothesis was generated."
        )

        actions: list[EngineerAction] = []
        if selected is not None and not selected.passed:
            actions.append(EngineerAction(1, "Contain and verify the affected production",
                "The selected inspection is rejected; prevent unverified material from progressing.",
                "QC supervisor", "Confirm hold/segregation status and identify affected batch boundaries.",
                "Inspection + Factory Memory"))
        if top is not None:
            for item in top.recommended_actions[:3]:
                actions.append(EngineerAction(len(actions)+1, item,
                    f"Supports verification of leading hypothesis: {top.cause}.",
                    "Process engineer / maintenance", "Record before-and-after evidence and obtain QC sign-off.",
                    "Root Cause Intelligence"))
        for item in forecast.recommended_actions:
            if len(actions) >= 6:
                break
            if not any(a.title.casefold() == item.casefold() for a in actions):
                actions.append(EngineerAction(len(actions)+1, item,
                    "Reduces or validates a detected predictive-quality risk driver.",
                    "Production + QC", "Re-run inspection and compare reject rate against baseline.",
                    "Predictive Quality"))
        if not actions:
            actions.append(EngineerAction(1, "Continue controlled production and sampling",
                "No strong risk or case-specific failure signal is currently present.",
                "Production + QC", "Maintain approved sampling frequency and record outcomes.",
                "Factory Engineer"))

        evidence: list[str] = [d.explanation for d in forecast.drivers[:4]]
        if top is not None:
            evidence.extend(e.explanation for e in top.supporting_evidence[:4])
        try:
            summary = self._knowledge_graph.summary()
            evidence.append(f"Knowledge Graph: {summary.node_count} nodes and {summary.edge_count} relationships available.")
        except Exception:
            evidence.append("Knowledge Graph summary was unavailable; briefing used other evidence sources.")

        gates = [
            "Do not change recipe, pressure, temperature, speed or machine settings without authorized approval.",
            "Confirm the suspected cause with QC/process evidence before marking the case resolved.",
            "After intervention, inspect a defined verification sample and record the outcome in Factory Memory.",
        ]
        if priority == OperationalPriority.HOLD_AND_VERIFY:
            gates = ("Verify segregation/hold status before continuation.",) + tuple(gates)

        summary_text = self._executive_summary(priority, selected, forecast, top)
        limitations = list(forecast.limitations)
        limitations.append("This briefing coordinates decision support; it does not autonomously control factory equipment.")
        briefing = FactoryEngineerBriefing(scope, priority, summary_text, quality_status,
            forecast_summary, root_summary, tuple(actions), tuple(dict.fromkeys(evidence)),
            tuple(gates), tuple(dict.fromkeys(limitations)), case_id)

        if case_id is not None:
            self._memory.attach_factory_engineer_briefing(case_id, asdict(briefing))
        self._event_bus.publish(DomainEvent(name="factory_engineer.briefing_generated",
            source="ai_factory_engineer_service", payload={"case_id": case_id, "scope": scope,
            "priority": priority.value, "action_count": len(actions)}))
        if priority in {OperationalPriority.URGENT, OperationalPriority.HOLD_AND_VERIFY}:
            self._event_bus.publish(DomainEvent(name="factory_engineer.escalation_recommended",
                source="ai_factory_engineer_service", payload={"case_id": case_id,
                "scope": scope, "priority": priority.value}))
        return briefing

    @staticmethod
    def _priority(risk_band: RiskBand, selected) -> OperationalPriority:
        if selected is not None and not selected.passed and risk_band in {RiskBand.HIGH, RiskBand.CRITICAL}:
            return OperationalPriority.HOLD_AND_VERIFY
        if risk_band == RiskBand.CRITICAL:
            return OperationalPriority.URGENT
        if risk_band == RiskBand.HIGH or (selected is not None and not selected.passed):
            return OperationalPriority.ATTENTION
        return OperationalPriority.ROUTINE

    @staticmethod
    def _executive_summary(priority, selected, forecast, top) -> str:
        case_text = "No individual case selected."
        if selected is not None:
            case_text = f"The selected {selected.product_name} case is {'accepted' if selected.passed else 'rejected'}."
        cause_text = f" The leading hypothesis is {top.cause}, pending verification." if top else ""
        return (f"{priority.value}: {case_text} Predictive Quality reports {forecast.risk_band.value} "
                f"risk with a {forecast.predicted_reject_rate*100:.1f}% predicted reject rate.{cause_text}")
