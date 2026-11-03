from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime
import math

from visionqc.application.ports.event_bus import EventBus
from visionqc.application.services.factory_memory_service import FactoryMemoryService
from visionqc.domain.events import DomainEvent
from visionqc.domain.predictive_quality import QualityForecast, RiskBand, RiskDriver


class PredictiveQualityService:
    """Offline, explainable early-warning engine based on Factory Memory.

    This is conservative decision support. It forecasts short-horizon quality
    risk from recent reject momentum, repeated defects, process deviations and
    context concentration. It does not claim equipment failure prediction.
    """

    def __init__(self, memory: FactoryMemoryService, event_bus: EventBus, knowledge_graph=None) -> None:
        self._memory = memory
        self._event_bus = event_bus
        self._knowledge_graph = knowledge_graph

    def forecast(self, *, product_name: str | None = None, line: str | None = None,
                 machine: str | None = None, recent_window: int = 20,
                 baseline_window: int = 80) -> QualityForecast:
        cases = self._memory.list_recent(max(200, baseline_window + recent_window), product_name=product_name)
        cases = [c for c in cases if (not line or c.production.production_line.casefold() == line.casefold())
                 and (not machine or c.production.machine_name.casefold() == machine.casefold())]
        scope_parts = [product_name or "All products"]
        if line: scope_parts.append(f"Line {line}")
        if machine: scope_parts.append(f"Machine {machine}")
        scope = " / ".join(scope_parts)
        if not cases:
            return QualityForecast(scope, 0.0, RiskBand.LOW, 0.0, 0.0, 0.0, "insufficient data", .15,
                "next production window", 0, limitations=("No Factory Memory cases match this scope.",))

        recent = cases[:min(recent_window, len(cases))]
        older = cases[len(recent):len(recent)+baseline_window]
        baseline_source = older or cases
        current_rate = self._reject_rate(recent)
        baseline_rate = self._reject_rate(baseline_source)
        momentum = current_rate - baseline_rate
        drivers: list[RiskDriver] = []
        raw = 0.0

        # Reject momentum is the strongest transparent signal.
        if momentum > 0:
            contribution = min(.42, momentum * 1.25)
            raw += contribution
            drivers.append(RiskDriver("Reject momentum", contribution,
                f"Recent reject rate {current_rate*100:.1f}% versus baseline {baseline_rate*100:.1f}%.", len(recent)))
        elif current_rate >= .25:
            contribution = min(.22, current_rate * .45)
            raw += contribution
            drivers.append(RiskDriver("Sustained reject level", contribution,
                f"Recent reject rate remains {current_rate*100:.1f}%.", len(recent)))

        # Recency-weighted streak signal.
        streak = 0
        for case in recent:
            if case.passed: break
            streak += 1
        if streak >= 2:
            contribution = min(.2, .05 * streak)
            raw += contribution
            drivers.append(RiskDriver("Consecutive rejects", contribution,
                f"{streak} latest comparable cases were rejected.", streak))

        # Defect concentration and growth.
        recent_defects = Counter(d.defect_type.casefold() for c in recent for d in c.defects)
        older_defects = Counter(d.defect_type.casefold() for c in baseline_source for d in c.defects)
        for defect, count in recent_defects.most_common(3):
            recent_share = count / max(1, len(recent))
            old_share = older_defects.get(defect, 0) / max(1, len(baseline_source))
            growth = recent_share - old_share
            if count >= 2 and growth > .05:
                contribution = min(.18, .06 + growth * .35)
                raw += contribution
                drivers.append(RiskDriver(f"Repeated defect: {defect}", contribution,
                    f"Observed in {count} recent cases; frequency increased versus baseline.", count))

        # Numeric process drift relative to accepted baseline cases.
        accepted = [c for c in baseline_source if c.passed]
        refs: dict[str, list[float]] = defaultdict(list)
        for c in accepted:
            for key, value in c.all_numeric_features().items(): refs[key].append(value)
        recent_values: dict[str, list[float]] = defaultdict(list)
        for c in recent:
            for key, value in c.all_numeric_features().items(): recent_values[key].append(value)
        for key, values in recent_values.items():
            reference = refs.get(key, [])
            if len(reference) < 4 or len(values) < 2: continue
            mean = sum(reference)/len(reference)
            sd = math.sqrt(sum((x-mean)**2 for x in reference)/len(reference))
            if sd <= 1e-9: continue
            current_mean = sum(values)/len(values)
            z = abs(current_mean-mean)/sd
            if z >= 1.25:
                contribution = min(.2, .045*z)
                raw += contribution
                drivers.append(RiskDriver(f"Process drift: {key}", contribution,
                    f"Recent mean {current_mean:.3g}; accepted baseline {mean:.3g}; {z:.1f} standard deviations apart.", len(values)))

        # Low evidence prevents overconfidence.
        evidence_factor = min(1.0, len(cases)/40)
        risk = max(0.0, min(.99, raw * (.55 + .45*evidence_factor) + current_rate*.28))
        predicted = max(0.0, min(.99, current_rate + max(0.0, momentum)*.45 + raw*.12))
        if risk >= .78: band = RiskBand.CRITICAL
        elif risk >= .55: band = RiskBand.HIGH
        elif risk >= .3: band = RiskBand.GUARDED
        else: band = RiskBand.LOW
        trend = "rising" if momentum > .05 else "falling" if momentum < -.05 else "stable"
        confidence = min(.92, .28 + evidence_factor*.5 + min(.14, len(drivers)*.025))
        actions = self._actions(drivers, band)
        limitations=[]
        if len(cases) < 20: limitations.append("Fewer than 20 comparable cases are available; confidence is limited.")
        if not older: limitations.append("A separate historical baseline was unavailable; all available cases were used.")
        limitations.append("Forecast is short-horizon decision support and must be confirmed by QC/process personnel.")
        forecast = QualityForecast(scope, round(risk,4), band, round(predicted,4), round(current_rate,4),
            round(baseline_rate,4), trend, round(confidence,4), "next comparable production window", len(cases),
            tuple(sorted(drivers,key=lambda d:d.contribution,reverse=True)[:8]), tuple(actions), tuple(limitations))
        self._event_bus.publish(DomainEvent(name="predictive_quality.forecast_generated", source="predictive_quality_service",
            payload={"scope":scope,"risk_score":forecast.risk_score,"risk_band":forecast.risk_band.value,
                     "predicted_reject_rate":forecast.predicted_reject_rate,"alert_required":forecast.alert_required}))
        if forecast.alert_required:
            self._event_bus.publish(DomainEvent(name="predictive_quality.early_warning", source="predictive_quality_service",
                payload={"scope":scope,"risk_band":forecast.risk_band.value,"risk_score":forecast.risk_score,
                         "top_driver":forecast.drivers[0].name if forecast.drivers else ""}))
        return forecast

    def available_scopes(self) -> dict[str, list[str]]:
        cases=self._memory.list_recent(1000)
        return {"products":sorted({c.product_name for c in cases if c.product_name}),
                "lines":sorted({c.production.production_line for c in cases if c.production.production_line}),
                "machines":sorted({c.production.machine_name for c in cases if c.production.machine_name})}

    @staticmethod
    def _reject_rate(cases) -> float:
        return sum(1 for c in cases if not c.passed)/max(1,len(cases))

    @staticmethod
    def _actions(drivers: list[RiskDriver], band: RiskBand) -> list[str]:
        actions=[]
        names=" ".join(d.name.casefold() for d in drivers)
        if "process drift" in names: actions += ["Verify current process measurements against the approved recipe and golden batch.", "Check sensor calibration before changing process settings."]
        if "repeated defect" in names: actions += ["Inspect the dominant defect at the line and review its verified root-cause history."]
        if "consecutive rejects" in names or band in {RiskBand.HIGH,RiskBand.CRITICAL}: actions += ["Start a controlled QC hold or increased sampling according to factory procedure.", "Ask Root Cause Intelligence for evidence-backed checks before intervention."]
        if not actions: actions=["Continue normal inspection and collect comparable process measurements."]
        return list(dict.fromkeys(actions))[:5]
