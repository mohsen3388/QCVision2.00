from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

class AutomationStatus(str, Enum):
    ENABLED="Enabled"; DISABLED="Disabled"
class ExecutionStatus(str, Enum):
    PENDING_APPROVAL="Pending approval"; COMPLETED="Completed"; FAILED="Failed"; SKIPPED="Skipped"
class ActionKind(str, Enum):
    CREATE_TASK="Create task"; RECORD_ALERT="Record alert"; DELIVER_WEBHOOK="Deliver webhook"; REQUEST_APPROVAL="Request approval"

@dataclass(slots=True)
class AutomationRule:
    name: str
    event_name: str
    action_kind: ActionKind
    action_config: dict[str, Any] = field(default_factory=dict)
    conditions: dict[str, Any] = field(default_factory=dict)
    requires_approval: bool = True
    enabled: bool = True
    rule_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=utc_now)

@dataclass(slots=True)
class AutomationExecution:
    rule_id: str
    event_name: str
    action_kind: ActionKind
    status: ExecutionStatus
    payload: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    execution_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=utc_now)
    completed_at: str | None = None

@dataclass(slots=True)
class AutomationTask:
    title: str
    owner_role: str
    priority: str
    source_event: str
    details: dict[str, Any] = field(default_factory=dict)
    task_id: str = field(default_factory=lambda: str(uuid4()))
    status: str = "Open"
    created_at: str = field(default_factory=utc_now)
