from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

class ConnectorKind(str, Enum):
    REST = "REST API"
    MQTT = "MQTT"
    OPC_UA = "OPC-UA"
    WEBHOOK = "Webhook"
    SQL = "SQL"
    FILE = "File Exchange"

class ConnectorState(str, Enum):
    READY = "Ready"
    DEGRADED = "Degraded"
    UNAVAILABLE = "Unavailable"
    DISABLED = "Disabled"
    NOT_CONFIGURED = "Not configured"

@dataclass(slots=True)
class ConnectorHealth:
    connector_id: str
    name: str
    kind: ConnectorKind
    state: ConnectorState
    message: str
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    latency_ms: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(slots=True)
class IntegrationMessage:
    source: str
    topic: str
    payload: dict[str, Any]
    correlation_id: str | None = None
    received_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

@dataclass(slots=True)
class ApiKeyRecord:
    key_id: str
    name: str
    key_hash: str
    role: str
    enabled: bool
    created_at: str
    last_used_at: str | None = None
