from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Immutable message exchanged between VisionQC modules."""

    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    source: str = "visionqc"
    event_id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: str = field(default_factory=_utc_now)
    correlation_id: str | None = None
