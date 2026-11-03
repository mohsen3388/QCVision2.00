from __future__ import annotations
from dataclasses import dataclass

ROLE_PERMISSIONS = {
    "Administrator": {"*"},
    "Factory Manager": {"dashboard.view", "reports.view", "events.view", "factory.view", "audit.view"},
    "QC Manager": {"dashboard.view", "reports.view", "events.view", "quality.configure", "quality.approve", "calibration.run", "audit.view"},
    "Operator": {"dashboard.view", "events.view", "events.ack", "camera.view", "assistant.use"},
}

@dataclass(slots=True)
class UserAccount:
    username: str
    display_name: str
    role: str
    active: bool = True
    must_change_password: bool = False
    last_login_at: str | None = None

@dataclass(slots=True)
class Session:
    username: str
    display_name: str
    role: str

    def can(self, permission: str) -> bool:
        allowed = ROLE_PERMISSIONS.get(self.role, set())
        return "*" in allowed or permission in allowed
