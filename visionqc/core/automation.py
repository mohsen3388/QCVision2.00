from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from visionqc.core.database import connect, initialize_database, utc_now
from visionqc.core.event_engine import ProcessEvent, record_event
from visionqc.core.spc import add_measurement


@dataclass
class MetricProfile:
    metric_name: str
    metric_group: str = "Quality"
    unit: str = ""
    target: float | None = None
    lsl: float | None = None
    usl: float | None = None
    enabled: bool = True


@dataclass
class ImportResult:
    source_path: str
    imported_metrics: int
    skipped_metrics: int
    generated_events: int
    batch_id: int | None
    imported_at: str
    metric_names: list[str]


def ensure_automation_schema() -> None:
    initialize_database()
    with connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS metric_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name TEXT NOT NULL UNIQUE,
            metric_group TEXT NOT NULL DEFAULT 'Quality',
            unit TEXT NOT NULL DEFAULT '',
            target REAL,
            lsl REAL,
            usl REAL,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS analysis_imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_path TEXT NOT NULL,
            batch_id INTEGER,
            imported_metrics INTEGER NOT NULL,
            skipped_metrics INTEGER NOT NULL,
            generated_events INTEGER NOT NULL,
            summary_json TEXT NOT NULL,
            imported_at TEXT NOT NULL,
            FOREIGN KEY(batch_id) REFERENCES batches(id)
        );
        CREATE INDEX IF NOT EXISTS idx_analysis_imports_time ON analysis_imports(imported_at);
        """)


def save_metric_profile(profile: MetricProfile) -> None:
    ensure_automation_schema()
    if not profile.metric_name.strip():
        raise ValueError("Metric name is required.")
    if profile.lsl is not None and profile.usl is not None and profile.lsl >= profile.usl:
        raise ValueError("LSL must be lower than USL.")
    now = utc_now()
    with connect() as conn:
        conn.execute("""
        INSERT INTO metric_profiles(metric_name,metric_group,unit,target,lsl,usl,enabled,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?)
        ON CONFLICT(metric_name) DO UPDATE SET metric_group=excluded.metric_group,unit=excluded.unit,
          target=excluded.target,lsl=excluded.lsl,usl=excluded.usl,enabled=excluded.enabled,updated_at=excluded.updated_at
        """, (profile.metric_name.strip(), profile.metric_group.strip() or "Quality", profile.unit.strip(), profile.target,
              profile.lsl, profile.usl, 1 if profile.enabled else 0, now, now))


def list_metric_profiles() -> list[MetricProfile]:
    ensure_automation_schema()
    with connect() as conn:
        rows = conn.execute("SELECT metric_name,metric_group,unit,target,lsl,usl,enabled FROM metric_profiles ORDER BY metric_group,metric_name").fetchall()
    return [MetricProfile(r["metric_name"], r["metric_group"], r["unit"], r["target"], r["lsl"], r["usl"], bool(r["enabled"])) for r in rows]


def _profile_map() -> dict[str, MetricProfile]:
    return {p.metric_name: p for p in list_metric_profiles()}


def _flatten_metrics(payload: dict[str, Any]) -> list[tuple[str, str, float]]:
    flattened: list[tuple[str, str, float]] = []
    for group, values in (payload.get("metrics") or {}).items():
        if not isinstance(values, dict):
            continue
        for name, value in values.items():
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                flattened.append((str(group), str(name), float(value)))
    return flattened


def import_analysis_payload(payload: dict[str, Any], *, source_path: str = "", batch_id: int | None = None,
                            product_name: str | None = None, production_line: str | None = None,
                            operator_name: str | None = None, import_unprofiled: bool = True,
                            create_finding_events: bool = True) -> ImportResult:
    ensure_automation_schema()
    profiles = _profile_map()
    imported = 0
    skipped = 0
    names: list[str] = []
    captured_at = payload.get("created_at") or payload.get("analyzed_at") or utc_now()
    source = source_path or str(payload.get("source_path") or "Analysis JSON")
    for group, name, value in _flatten_metrics(payload):
        profile = profiles.get(name)
        if profile is not None and not profile.enabled:
            skipped += 1
            continue
        if profile is None and not import_unprofiled:
            skipped += 1
            continue
        add_measurement(metric_name=name, metric_group=(profile.metric_group if profile else group), value=value,
                        unit=(profile.unit if profile else ""), batch_id=batch_id, product_name=product_name,
                        production_line=production_line, operator_name=operator_name,
                        target=(profile.target if profile else None), lsl=(profile.lsl if profile else None),
                        usl=(profile.usl if profile else None), captured_at=captured_at,
                        source="Automated Analysis Import", notes=f"Imported from {source}")
        imported += 1
        names.append(name)

    event_count = 0
    if create_finding_events:
        for finding in payload.get("findings") or []:
            if not isinstance(finding, dict) or not finding.get("triggered"):
                continue
            severity = str(finding.get("severity") or "Attention")
            if severity not in ("Information", "Attention", "Warning", "Critical"):
                severity = "Attention"
            record_event(ProcessEvent(
                batch_id=batch_id, event_type="ANALYSIS_FINDING", severity=severity,
                source="Automated Analysis Import", message=str(finding.get("title") or finding.get("reason") or "Analysis finding"),
                details={"rule_id": finding.get("rule_id"), "reason": finding.get("reason"),
                         "recommendation": finding.get("recommendation"), "evidence": finding.get("evidence", {}),
                         "analysis_source": source},
            ))
            event_count += 1

    result = ImportResult(source, imported, skipped, event_count, batch_id, utc_now(), names)
    with connect() as conn:
        conn.execute("""INSERT INTO analysis_imports(source_path,batch_id,imported_metrics,skipped_metrics,generated_events,summary_json,imported_at)
                        VALUES(?,?,?,?,?,?,?)""",
                     (source, batch_id, imported, skipped, event_count, json.dumps(asdict(result), ensure_ascii=False), result.imported_at))
    return result


def import_analysis_file(path: str | Path, **kwargs: Any) -> ImportResult:
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Analysis JSON must contain an object.")
    return import_analysis_payload(payload, source_path=str(path), **kwargs)


def list_imports(limit: int = 100) -> list[dict[str, Any]]:
    ensure_automation_schema()
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM analysis_imports ORDER BY id DESC LIMIT ?", (limit,))]
