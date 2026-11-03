from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from visionqc.core.database import connect
from .models import CalibrationSample, ValidationSummary

SCHEMA = """
CREATE TABLE IF NOT EXISTS vqc4_calibration_samples(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 template_key TEXT NOT NULL,
 source_path TEXT NOT NULL,
 expert_label TEXT NOT NULL,
 expert_name TEXT NOT NULL DEFAULT '',
 notes TEXT NOT NULL DEFAULT '',
 batch_code TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL,
 UNIQUE(template_key, source_path)
);
CREATE INDEX IF NOT EXISTS idx_vqc4_calibration_samples_template ON vqc4_calibration_samples(template_key, expert_label);
CREATE TABLE IF NOT EXISTS vqc4_validation_runs(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 template_key TEXT NOT NULL,
 template_version TEXT NOT NULL,
 sample_count INTEGER NOT NULL,
 production_ready INTEGER NOT NULL DEFAULT 0,
 summary_json TEXT NOT NULL,
 approved_by TEXT NOT NULL DEFAULT '',
 approved_at TEXT,
 created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_vqc4_validation_runs_template ON vqc4_validation_runs(template_key, created_at DESC);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CalibrationRepository:
    def __init__(self) -> None:
        with connect() as c:
            c.executescript(SCHEMA)

    def add_sample(self, sample: CalibrationSample) -> int:
        created = sample.created_at or now()
        with connect() as c:
            cur = c.execute(
                """INSERT INTO vqc4_calibration_samples(template_key,source_path,expert_label,expert_name,notes,batch_code,created_at)
                VALUES(?,?,?,?,?,?,?) ON CONFLICT(template_key,source_path) DO UPDATE SET
                expert_label=excluded.expert_label,expert_name=excluded.expert_name,notes=excluded.notes,batch_code=excluded.batch_code""",
                (sample.template_key, sample.source_path, sample.expert_label, sample.expert_name, sample.notes, sample.batch_code, created),
            )
            row = c.execute("SELECT id FROM vqc4_calibration_samples WHERE template_key=? AND source_path=?", (sample.template_key, sample.source_path)).fetchone()
            return int(row[0])

    def list_samples(self, template_key: str) -> list[CalibrationSample]:
        with connect() as c:
            rows = c.execute(
                "SELECT id,template_key,source_path,expert_label,expert_name,notes,batch_code,created_at FROM vqc4_calibration_samples WHERE template_key=? ORDER BY created_at,id",
                (template_key,),
            ).fetchall()
        return [CalibrationSample(*row) for row in rows]

    def delete_sample(self, sample_id: int) -> None:
        with connect() as c:
            c.execute("DELETE FROM vqc4_calibration_samples WHERE id=?", (int(sample_id),))

    def save_validation(self, summary: ValidationSummary) -> int:
        created = summary.created_at or now()
        payload = json.dumps(summary.to_dict(), ensure_ascii=False)
        with connect() as c:
            cur = c.execute(
                "INSERT INTO vqc4_validation_runs(template_key,template_version,sample_count,production_ready,summary_json,created_at) VALUES(?,?,?,?,?,?)",
                (summary.template_key, summary.template_version, summary.sample_count, 1 if summary.production_ready else 0, payload, created),
            )
            return int(cur.lastrowid)

    def approve_run(self, run_id: int, approved_by: str) -> None:
        if not approved_by.strip():
            raise ValueError("نام تأییدکننده QC الزامی است.")
        with connect() as c:
            row = c.execute("SELECT production_ready FROM vqc4_validation_runs WHERE id=?", (int(run_id),)).fetchone()
            if not row:
                raise ValueError("اجرای اعتبارسنجی یافت نشد.")
            if not bool(row[0]):
                raise ValueError("این اعتبارسنجی معیارهای Production Gate را پاس نکرده است.")
            c.execute("UPDATE vqc4_validation_runs SET approved_by=?,approved_at=? WHERE id=?", (approved_by.strip(), now(), int(run_id)))


    def has_approved_validation(self, template_key: str, template_version: str) -> bool:
        with connect() as c:
            row = c.execute(
                "SELECT 1 FROM vqc4_validation_runs WHERE template_key=? AND template_version=? AND production_ready=1 AND approved_at IS NOT NULL ORDER BY id DESC LIMIT 1",
                (template_key, template_version),
            ).fetchone()
        return bool(row)

    def latest_run(self, template_key: str) -> dict[str, Any] | None:
        with connect() as c:
            row = c.execute(
                "SELECT id,summary_json,approved_by,approved_at,created_at FROM vqc4_validation_runs WHERE template_key=? ORDER BY id DESC LIMIT 1",
                (template_key,),
            ).fetchone()
        if not row:
            return None
        data = json.loads(row[1]); data.update({"run_id": row[0], "approved_by": row[2], "approved_at": row[3], "stored_at": row[4]})
        return data
