from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class LicenseState(str, Enum):
    UNLICENSED = "Unlicensed"
    ACTIVE = "Active"
    EXPIRED = "Expired"
    INVALID = "Invalid"
    MACHINE_MISMATCH = "Machine mismatch"


@dataclass(slots=True)
class LicenseStatus:
    state: LicenseState
    customer: str = ""
    edition: str = "Commercial"
    expires_at: str | None = None
    features: list[str] = field(default_factory=list)
    machine_id: str = ""
    message: str = ""

    @property
    def usable(self) -> bool:
        return self.state is LicenseState.ACTIVE


@dataclass(slots=True)
class UpdateAssessment:
    current_version: str
    available_version: str | None
    channel: str
    update_available: bool
    package_path: str | None = None
    checksum_ok: bool | None = None
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CommercialReadiness:
    generated_at: str
    license_status: LicenseStatus
    update_assessment: UpdateAssessment
    support_bundle_ready: bool
    crash_reports: int
    checks: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def now(cls, **kwargs: Any) -> "CommercialReadiness":
        return cls(generated_at=datetime.now(timezone.utc).isoformat(), **kwargs)
