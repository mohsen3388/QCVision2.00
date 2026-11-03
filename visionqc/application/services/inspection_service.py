from __future__ import annotations

from visionqc.application.ports.event_bus import EventBus
from visionqc.application.ports.repositories import InspectionRepository
from visionqc.domain.events import DomainEvent
from visionqc.domain.models import InspectionCase


class InspectionApplicationService:
    """Application use case coordinating persistence and downstream modules."""

    def __init__(self, repository: InspectionRepository, event_bus: EventBus) -> None:
        self._repository = repository
        self._event_bus = event_bus

    def record(self, case: InspectionCase) -> int:
        result_id = self._repository.save(case)
        self._event_bus.publish(DomainEvent(
            name="inspection.completed",
            source="inspection_service",
            payload={
                "inspection_id": result_id,
                "batch_id": case.batch_id,
                "product_name": case.product_name,
                "passed": case.passed,
                "reasons": list(case.reasons),
            },
        ))
        return result_id
