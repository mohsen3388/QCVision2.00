from __future__ import annotations

import json

from visionqc.core.database import connect, utc_now
from visionqc.domain.models import InspectionCase


class SqliteInspectionRepository:
    """SQLite adapter for inspection cases, independent from UI code."""

    def save(self, case: InspectionCase) -> int:
        project_id = case.metadata.get("project_id")
        if project_id is None:
            raise ValueError("InspectionCase.metadata['project_id'] is required")
        with connect() as conn:
            cur = conn.execute(
                """INSERT INTO inspection_results(project_id,image_path,passed,measurements_json,reasons_json,processing_ms,created_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (
                    int(project_id), case.image_path, int(case.passed),
                    json.dumps(case.measurements, ensure_ascii=False, sort_keys=True),
                    json.dumps(case.reasons, ensure_ascii=False), case.processing_ms, utc_now(),
                ),
            )
            return int(cur.lastrowid)
