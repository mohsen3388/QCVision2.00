from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

from visionqc.core.database import connect


class SqliteAuditTrailRepository:
    """Append-only operational audit trail.

    Application code only receives append/read methods. No update/delete method is
    exposed, reducing the risk of silently rewriting operational history.
    """

    def initialize(self) -> None:
        with connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS audit_trail (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    entity_type TEXT,
                    entity_id TEXT,
                    outcome TEXT NOT NULL,
                    details_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_audit_trail_created_at
                    ON audit_trail(created_at);
                CREATE INDEX IF NOT EXISTS idx_audit_trail_entity
                    ON audit_trail(entity_type, entity_id, created_at);
                """
            )

    def append(
        self,
        event_type: str,
        actor: str = "VisionQC",
        entity_type: str | None = None,
        entity_id: str | None = None,
        outcome: str = "Success",
        details: dict[str, Any] | None = None,
    ) -> int:
        self.initialize()
        with connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO audit_trail(
                    event_type, actor, entity_type, entity_id,
                    outcome, details_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_type,
                    actor,
                    entity_type,
                    entity_id,
                    outcome,
                    json.dumps(details or {}, ensure_ascii=False, default=str),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            return int(cursor.lastrowid)

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        self.initialize()
        with connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM audit_trail ORDER BY id DESC LIMIT ?", (max(1, int(limit)),)
            )
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row) if hasattr(row, "keys") else dict(zip(columns, row))
            try:
                item["details"] = json.loads(item.pop("details_json"))
            except Exception:
                item["details"] = {}
                item.pop("details_json", None)
            result.append(item)
        return result
