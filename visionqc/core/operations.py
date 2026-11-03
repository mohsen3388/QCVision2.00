from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from visionqc.core.database import connect, utc_now


@dataclass
class OEESnapshot:
    run_id: int
    shift_name: str
    production_line: str
    product_name: str
    planned_minutes: float
    downtime_minutes: float
    operating_minutes: float
    total_units: int
    good_units: int
    rejected_units: int
    ideal_cycle_seconds: float
    availability: float
    performance: float
    quality: float
    oee: float
    downtime_by_reason: list[dict]


def create_shift(name: str, start_time: str, end_time: str, planned_break_minutes: int = 0, enabled: bool = True) -> int:
    name = name.strip()
    if not name:
        raise ValueError("Shift name is required.")
    if planned_break_minutes < 0:
        raise ValueError("Planned break cannot be negative.")
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO production_shifts(name,start_time,end_time,planned_break_minutes,enabled,created_at) VALUES(?,?,?,?,?,?)",
            (name, start_time, end_time, planned_break_minutes, 1 if enabled else 0, utc_now()),
        )
        return int(cur.lastrowid)


def list_shifts(enabled_only: bool = False) -> list[dict]:
    sql = "SELECT * FROM production_shifts"
    params: tuple = ()
    if enabled_only:
        sql += " WHERE enabled=1"
    sql += " ORDER BY name"
    with connect() as conn:
        return [dict(r) for r in conn.execute(sql, params)]


def set_shift_enabled(shift_id: int, enabled: bool) -> None:
    with connect() as conn:
        conn.execute("UPDATE production_shifts SET enabled=? WHERE id=?", (1 if enabled else 0, shift_id))


def create_production_run(*, shift_id: int, production_line: str, product_name: str, planned_minutes: float,
                          ideal_cycle_seconds: float, total_units: int = 0, good_units: int = 0,
                          batch_id: int | None = None, operator_name: str = "", notes: str = "") -> int:
    if planned_minutes <= 0:
        raise ValueError("Planned production minutes must be greater than zero.")
    if ideal_cycle_seconds <= 0:
        raise ValueError("Ideal cycle time must be greater than zero.")
    if total_units < 0 or good_units < 0 or good_units > total_units:
        raise ValueError("Unit counts are invalid.")
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO production_runs(batch_id,shift_id,production_line,product_name,operator_name,
               planned_minutes,ideal_cycle_seconds,total_units,good_units,status,started_at,notes)
               VALUES(?,?,?,?,?,?,?,?,?,'Open',?,?)""",
            (batch_id, shift_id, production_line.strip(), product_name.strip(), operator_name.strip(),
             float(planned_minutes), float(ideal_cycle_seconds), int(total_units), int(good_units), utc_now(), notes.strip()),
        )
        return int(cur.lastrowid)


def update_run_counts(run_id: int, total_units: int, good_units: int, finish: bool = False) -> None:
    if total_units < 0 or good_units < 0 or good_units > total_units:
        raise ValueError("Good units must be between zero and total units.")
    with connect() as conn:
        conn.execute(
            "UPDATE production_runs SET total_units=?,good_units=?,status=?,ended_at=? WHERE id=?",
            (total_units, good_units, "Finished" if finish else "Open", utc_now() if finish else None, run_id),
        )


def add_downtime(run_id: int, reason: str, duration_minutes: float, category: str = "Unplanned", notes: str = "") -> int:
    if duration_minutes <= 0:
        raise ValueError("Downtime duration must be greater than zero.")
    if not reason.strip():
        raise ValueError("Downtime reason is required.")
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO downtime_events(run_id,reason,category,duration_minutes,notes,created_at) VALUES(?,?,?,?,?,?)",
            (run_id, reason.strip(), category.strip() or "Unplanned", float(duration_minutes), notes.strip(), utc_now()),
        )
        return int(cur.lastrowid)


def list_runs(limit: int = 250) -> list[dict]:
    with connect() as conn:
        return [dict(r) for r in conn.execute(
            """SELECT r.*,s.name AS shift_name FROM production_runs r
               JOIN production_shifts s ON s.id=r.shift_id ORDER BY r.id DESC LIMIT ?""", (limit,))]


def calculate_oee(run_id: int) -> OEESnapshot:
    with connect() as conn:
        run = conn.execute(
            """SELECT r.*,s.name AS shift_name,s.planned_break_minutes FROM production_runs r
               JOIN production_shifts s ON s.id=r.shift_id WHERE r.id=?""", (run_id,)).fetchone()
        if run is None:
            raise ValueError("Production run was not found.")
        events = [dict(r) for r in conn.execute(
            "SELECT reason,category,duration_minutes FROM downtime_events WHERE run_id=? ORDER BY id", (run_id,))]
    planned = max(0.0, float(run["planned_minutes"]) - float(run["planned_break_minutes"] or 0))
    downtime = sum(float(e["duration_minutes"]) for e in events)
    operating = max(0.0, planned - downtime)
    availability = operating / planned if planned else 0.0
    total = int(run["total_units"] or 0)
    good = int(run["good_units"] or 0)
    rejected = max(0, total - good)
    performance = ((float(run["ideal_cycle_seconds"]) * total) / (operating * 60.0)) if operating else 0.0
    performance = min(max(performance, 0.0), 1.0)
    quality = good / total if total else 0.0
    oee = availability * performance * quality
    reasons: dict[tuple[str, str], float] = {}
    for e in events:
        key = (e["reason"], e["category"])
        reasons[key] = reasons.get(key, 0.0) + float(e["duration_minutes"])
    grouped = [{"reason": k[0], "category": k[1], "minutes": round(v, 3)} for k, v in sorted(reasons.items(), key=lambda x: -x[1])]
    return OEESnapshot(
        run_id=run_id, shift_name=run["shift_name"], production_line=run["production_line"], product_name=run["product_name"],
        planned_minutes=round(planned, 3), downtime_minutes=round(downtime, 3), operating_minutes=round(operating, 3),
        total_units=total, good_units=good, rejected_units=rejected, ideal_cycle_seconds=float(run["ideal_cycle_seconds"]),
        availability=availability, performance=performance, quality=quality, oee=oee, downtime_by_reason=grouped,
    )


def export_oee(snapshot: OEESnapshot, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(asdict(snapshot), indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["VisionQC OEE Export"])
            for k, v in asdict(snapshot).items():
                if k != "downtime_by_reason": w.writerow([k, v])
            w.writerow([]); w.writerow(["Downtime reason", "Category", "Minutes"])
            for item in snapshot.downtime_by_reason: w.writerow([item["reason"], item["category"], item["minutes"]])
    return path
