from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ReadinessLevel(str, Enum):
    READY = "Ready"
    ATTENTION = "Attention"
    BLOCKED = "Blocked"


@dataclass(slots=True, frozen=True)
class ReadinessCheck:
    name: str
    category: str
    ok: bool
    required: bool
    message: str
    remediation: str = ""


@dataclass(slots=True)
class ReleaseReadinessReport:
    level: ReadinessLevel
    checks: list[ReadinessCheck]
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def required_failures(self) -> list[ReadinessCheck]:
        return [check for check in self.checks if check.required and not check.ok]

    @property
    def warnings(self) -> list[ReadinessCheck]:
        return [check for check in self.checks if not check.required and not check.ok]

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level.value,
            "generated_at": self.generated_at.isoformat(),
            "metadata": self.metadata,
            "checks": [
                {
                    "name": c.name,
                    "category": c.category,
                    "ok": c.ok,
                    "required": c.required,
                    "message": c.message,
                    "remediation": c.remediation,
                }
                for c in self.checks
            ],
        }
