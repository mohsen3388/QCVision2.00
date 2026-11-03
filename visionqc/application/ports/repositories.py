from __future__ import annotations

from typing import Protocol

from visionqc.domain.models import InspectionCase


class InspectionRepository(Protocol):
    def save(self, case: InspectionCase) -> int: ...
