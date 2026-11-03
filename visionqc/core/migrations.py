from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3
from typing import Callable

from visionqc.core.database import connect


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    apply: Callable[[sqlite3.Connection], None]


def _migration_1(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        );
        """
    )


def _migration_2(conn: sqlite3.Connection) -> None:
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
        CREATE INDEX IF NOT EXISTS idx_audit_trail_created_at ON audit_trail(created_at);
        CREATE INDEX IF NOT EXISTS idx_audit_trail_entity ON audit_trail(entity_type, entity_id, created_at);
        """
    )


def _migration_3(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS enterprise_api_keys(
            key_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            key_hash TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            last_used_at TEXT
        );
        CREATE TABLE IF NOT EXISTS integration_settings(
            connector_id TEXT PRIMARY KEY,
            settings_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )


def _migration_4(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS industrial_automation_rules(
          rule_id TEXT PRIMARY KEY,name TEXT NOT NULL,event_name TEXT NOT NULL,action_kind TEXT NOT NULL,
          action_config_json TEXT NOT NULL,conditions_json TEXT NOT NULL,requires_approval INTEGER NOT NULL,
          enabled INTEGER NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS industrial_automation_executions(
          execution_id TEXT PRIMARY KEY,rule_id TEXT NOT NULL,event_name TEXT NOT NULL,action_kind TEXT NOT NULL,
          status TEXT NOT NULL,payload_json TEXT NOT NULL,message TEXT NOT NULL,created_at TEXT NOT NULL,completed_at TEXT);
        CREATE TABLE IF NOT EXISTS industrial_automation_tasks(
          task_id TEXT PRIMARY KEY,title TEXT NOT NULL,owner_role TEXT NOT NULL,priority TEXT NOT NULL,
          source_event TEXT NOT NULL,details_json TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_automation_rules_event ON industrial_automation_rules(event_name,enabled);
        CREATE INDEX IF NOT EXISTS idx_automation_execution_created ON industrial_automation_executions(created_at);
        """
    )


def _migration_5(conn: sqlite3.Connection) -> None:
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


MIGRATIONS = (
    Migration(1, "migration registry", _migration_1),
    Migration(2, "release audit trail", _migration_2),
    Migration(3, "enterprise integration", _migration_3),
    Migration(4, "industrial automation", _migration_4),
    Migration(5, "commercial edition", _migration_5),
)


def current_schema_version() -> int:
    with connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        ).fetchone()
        if not exists:
            return 0
        row = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()
        return int(row[0])


def apply_pending_migrations() -> list[int]:
    applied: list[int] = []
    with connect() as conn:
        _migration_1(conn)
        known = {int(row[0]) for row in conn.execute("SELECT version FROM schema_migrations")}
        for migration in MIGRATIONS:
            if migration.version in known:
                continue
            migration.apply(conn)
            conn.execute(
                "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                (migration.version, migration.name, datetime.now(timezone.utc).isoformat()),
            )
            applied.append(migration.version)
    return applied


def latest_schema_version() -> int:
    return max(m.version for m in MIGRATIONS)
