from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from visionqc.core.database import connect, utc_now

SEVERITIES = ("Information", "Attention", "Warning", "Critical")

@dataclass(slots=True)
class ProcessEvent:
    event_type: str
    message: str
    severity: str = "Information"
    source: str = "VisionQC"
    batch_id: int | None = None
    details: dict[str, Any] = field(default_factory=dict)
    event_id: int | None = None
    created_at: str | None = None
    acknowledged: bool = False
    acknowledged_by: str = ""
    acknowledged_at: str | None = None


def record_event(event: ProcessEvent) -> int:
    if event.severity not in SEVERITIES:
        raise ValueError(f"Unsupported severity: {event.severity}")
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO process_events(batch_id,event_type,severity,source,message,details_json,created_at,acknowledged,acknowledged_by,acknowledged_at)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (event.batch_id, event.event_type, event.severity, event.source, event.message,
             json.dumps(event.details, ensure_ascii=False, sort_keys=True), event.created_at or utc_now(),
             int(event.acknowledged), event.acknowledged_by, event.acknowledged_at),
        )
        return int(cur.lastrowid)


def list_events(batch_id: int | None = None, severity: str | None = None, limit: int = 500) -> list[ProcessEvent]:
    clauses, params = [], []
    if batch_id is not None:
        clauses.append("batch_id=?"); params.append(batch_id)
    if severity:
        clauses.append("severity=?"); params.append(severity)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    params.append(limit)
    with connect() as conn:
        rows = conn.execute(f"SELECT * FROM process_events{where} ORDER BY id DESC LIMIT ?", params).fetchall()
    return [ProcessEvent(event_id=r["id"], batch_id=r["batch_id"], event_type=r["event_type"], severity=r["severity"], source=r["source"], message=r["message"], details=json.loads(r["details_json"] or "{}"), created_at=r["created_at"], acknowledged=bool(r["acknowledged"]), acknowledged_by=r["acknowledged_by"] or "", acknowledged_at=r["acknowledged_at"]) for r in rows]


def acknowledge_event(event_id: int, operator: str) -> None:
    operator = operator.strip()
    if not operator:
        raise ValueError("Operator name is required.")
    with connect() as conn:
        conn.execute("UPDATE process_events SET acknowledged=1, acknowledged_by=?, acknowledged_at=? WHERE id=?", (operator, utc_now(), event_id))


def events_to_timeline(events: list[ProcessEvent]) -> list[dict[str, Any]]:
    ordered = sorted(events, key=lambda e: e.created_at or "")
    return [{"time": e.created_at, "type": e.event_type, "severity": e.severity, "source": e.source, "message": e.message, "acknowledged": e.acknowledged} for e in ordered]
