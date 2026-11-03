from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sqlite3
from typing import Any

from visionqc.core.backup import create_backup, validate_backup
from visionqc.core.database import database_path
from visionqc.core.deployment import deployment_readiness
from visionqc.core.health import health_report
from visionqc.core.settings import APP_VERSION, app_data_dir, load_settings
from visionqc.domain.release_candidate import ReadinessCheck, ReadinessLevel, ReleaseReadinessReport
from visionqc.domain.events import DomainEvent
from visionqc.core.migrations import current_schema_version, latest_schema_version


class ReleaseReadinessService:
    def __init__(self, audit_repository: Any, event_bus: Any | None = None) -> None:
        self.audit_repository = audit_repository
        self.event_bus = event_bus

    def assess(self) -> ReleaseReadinessReport:
        checks: list[ReadinessCheck] = []
        health = health_report()
        for row in health["checks"]:
            checks.append(ReadinessCheck(
                name=row["name"], category="Health", ok=bool(row["ok"]),
                required=row["name"] in {"Database", "Data directory", "Settings"},
                message=row["message"], remediation="Resolve this health check before release." if not row["ok"] else "",
            ))

        deployment = deployment_readiness()
        for row in deployment["checks"]:
            required = row["name"] in {"Bundled application runtime", "Data directory", "Reports directory", "Free disk space"}
            checks.append(ReadinessCheck(
                name=row["name"], category="Deployment", ok=bool(row["ok"]), required=required,
                message=row["message"], remediation="Correct deployment prerequisites and rerun the assessment." if not row["ok"] else "",
            ))

        db = database_path()
        backup_dir = app_data_dir() / "release_backups"
        backup_ok = False
        backup_message = "No release backup created."
        try:
            archive = create_backup(backup_dir)
            info = validate_backup(archive)
            backup_ok = bool(info.get("has_database"))
            backup_message = f"Validated backup: {archive.name}"
        except Exception as exc:
            backup_message = str(exc)
        checks.append(ReadinessCheck(
            "Validated release backup", "Recovery", backup_ok, True, backup_message,
            "Create and validate a backup before deployment." if not backup_ok else "",
        ))

        integrity_ok = False
        integrity_message = "Database is not available."
        try:
            with sqlite3.connect(db) as conn:
                integrity_message = str(conn.execute("PRAGMA quick_check").fetchone()[0])
                integrity_ok = integrity_message == "ok"
        except Exception as exc:
            integrity_message = str(exc)
        checks.append(ReadinessCheck(
            "SQLite quick check", "Data integrity", integrity_ok, True, integrity_message,
            "Repair or restore the database before release." if not integrity_ok else "",
        ))

        schema_current = current_schema_version()
        schema_latest = latest_schema_version()
        checks.append(ReadinessCheck(
            "Database schema version", "Data integrity", schema_current == schema_latest, True,
            f"Current {schema_current}; expected {schema_latest}",
            "Apply pending database migrations before release." if schema_current != schema_latest else "",
        ))

        settings = load_settings()
        free_gb = 0.0
        try:
            free_gb = shutil.disk_usage(Path(settings["data_directory"])).free / (1024 ** 3)
        except Exception:
            pass

        required_failures = [c for c in checks if c.required and not c.ok]
        warnings = [c for c in checks if not c.required and not c.ok]
        level = ReadinessLevel.BLOCKED if required_failures else (ReadinessLevel.ATTENTION if warnings else ReadinessLevel.READY)
        report = ReleaseReadinessReport(
            level=level,
            checks=checks,
            metadata={
                "visionqc_version": APP_VERSION,
                "database_path": str(db),
                "free_disk_gb": round(free_gb, 2),
                "required_failures": len(required_failures),
                "warnings": len(warnings),
            },
        )
        self.audit_repository.append(
            "release_candidate.assessment_completed",
            entity_type="release_candidate",
            entity_id=APP_VERSION,
            outcome=level.value,
            details=report.to_dict(),
        )
        if self.event_bus is not None:
            self.event_bus.publish(DomainEvent(
                name="release_candidate.assessment_completed",
                payload=report.to_dict(),
                source="release_readiness_service",
            ))
        return report

    def export_report(self, destination: Path, report: ReleaseReadinessReport | None = None) -> Path:
        report = report or self.assess()
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        self.audit_repository.append(
            "release_candidate.report_exported", entity_type="file", entity_id=str(destination),
            details={"level": report.level.value},
        )
        return destination

    def recent_audit(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.audit_repository.recent(limit)
