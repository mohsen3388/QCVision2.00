from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class InspectionCase:
    """Stable domain representation of one visual quality inspection."""

    product_name: str
    image_path: str
    passed: bool
    measurements: dict[str, float] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    batch_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    processing_ms: float = 0.0
