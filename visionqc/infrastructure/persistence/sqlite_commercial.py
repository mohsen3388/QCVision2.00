from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

from visionqc.core.database import connect


class SqliteCommercialRepository:
    def initialize(self) -> None:
        with connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS commercial_license(
                    singleton_id INTEGER PRIMARY KEY CHECK(singleton_id=1),
                    license_json TEXT NOT NULL,
                    imported_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS commercial_update_history(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    current_version TEXT NOT NULL,
                    available_version TEXT,
                    channel TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    details_json TEXT NOT NULL DEFAULT '{}',
                    checked_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_commercial_update_checked
                    ON commercial_update_history(checked_at);
                """
            )

    def save_license(self, payload: dict[str, Any]) -> None:
        self.initialize()
        with connect() as conn:
            conn.execute(
                """INSERT INTO commercial_license(singleton_id,license_json,imported_at)
                   VALUES(1,?,?)
                   ON CONFLICT(singleton_id) DO UPDATE SET
                   license_json=excluded.license_json, imported_at=excluded.imported_at""",
                (json.dumps(payload, ensure_ascii=False, sort_keys=True), datetime.now(timezone.utc).isoformat()),
            )

    def load_license(self) -> dict[str, Any] | None:
        self.initialize()
        with connect() as conn:
            row = conn.execute("SELECT license_json FROM commercial_license WHERE singleton_id=1").fetchone()
        if not row:
            return None
        try:
            return json.loads(row[0])
        except Exception:
            return None

    def clear_license(self) -> None:
        self.initialize()
        with connect() as conn:
            conn.execute("DELETE FROM commercial_license WHERE singleton_id=1")

    def record_update(self, current_version: str, available_version: str | None, channel: str, outcome: str, details: dict[str, Any]) -> None:
        self.initialize()
        with connect() as conn:
            conn.execute(
                "INSERT INTO commercial_update_history(current_version,available_version,channel,outcome,details_json,checked_at) VALUES(?,?,?,?,?,?)",
                (current_version, available_version, channel, outcome, json.dumps(details, ensure_ascii=False, default=str), datetime.now(timezone.utc).isoformat()),
            )
