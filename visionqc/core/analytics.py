from __future__ import annotations

import csv
import json
import sqlite3
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from visionqc.core.database import connect, initialize_database


@dataclass(frozen=True)
class DashboardFilter:
    date_from: str | None = None
    date_to: str | None = None
    product_name: str | None = None
    production_line: str | None = None
    operator_name: str | None = None


@dataclass
class DashboardSnapshot:
    generated_at: str
    filters: dict
    total_batches: int
    finished_batches: int
    open_batches: int
    accepted_batches: int
    rejected_batches: int
    undecided_batches: int
    acceptance_rate: float
    average_duration_minutes: float | None
    warning_events: int
    critical_events: int
    unacknowledged_events: int
    by_day: list[dict]
    by_product: list[dict]
    by_line: list[dict]
    by_operator: list[dict]
    by_outcome: list[dict]
    top_event_types: list[dict]

    def to_dict(self) -> dict:
        return asdict(self)


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _where(filters: DashboardFilter) -> tuple[str, list[object]]:
    parts: list[str] = []
    params: list[object] = []
    if filters.date_from:
        parts.append("date(b.started_at) >= date(?)"); params.append(filters.date_from)
    if filters.date_to:
        parts.append("date(b.started_at) <= date(?)"); params.append(filters.date_to)
    if filters.product_name:
        parts.append("b.product_name = ?"); params.append(filters.product_name)
    if filters.production_line:
        parts.append("b.production_line = ?"); params.append(filters.production_line)
    if filters.operator_name:
        parts.append("b.operator_name = ?"); params.append(filters.operator_name)
    return (" WHERE " + " AND ".join(parts)) if parts else "", params


def _rows(conn: sqlite3.Connection, filters: DashboardFilter) -> list[sqlite3.Row]:
    where, params = _where(filters)
    return list(conn.execute(f"SELECT b.* FROM batches b{where} ORDER BY b.started_at", params))


def _series(counter: Counter, total: int, key_name: str) -> list[dict]:
    result=[]
    for key, count in sorted(counter.items(), key=lambda item: (-item[1], str(item[0]))):
        result.append({key_name: key or "Unspecified", "count": count, "percent": round((count / total * 100) if total else 0.0, 2)})
    return result


def build_dashboard(filters: DashboardFilter | None = None) -> DashboardSnapshot:
    initialize_database()
    filters = filters or DashboardFilter()
    with connect() as conn:
        batches = _rows(conn, filters)
        ids = [int(r["id"]) for r in batches]
        events: list[sqlite3.Row] = []
        if ids:
            placeholders = ",".join("?" for _ in ids)
            events = list(conn.execute(f"SELECT * FROM process_events WHERE batch_id IN ({placeholders})", ids))

    total = len(batches)
    accepted = sum(1 for b in batches if (b["qc_outcome"] or "").lower() in {"accepted", "accept", "pass", "approved"})
    rejected = sum(1 for b in batches if (b["qc_outcome"] or "").lower() in {"rejected", "reject", "fail", "failed"})
    finished = sum(1 for b in batches if b["status"] == "Finished" or b["ended_at"])
    durations=[]
    day_data=defaultdict(lambda: {"total":0,"accepted":0,"rejected":0})
    for b in batches:
        day=(b["started_at"] or "")[:10] or "Unknown"
        day_data[day]["total"] += 1
        outcome=(b["qc_outcome"] or "").lower()
        if outcome in {"accepted","accept","pass","approved"}: day_data[day]["accepted"] += 1
        if outcome in {"rejected","reject","fail","failed"}: day_data[day]["rejected"] += 1
        start,end=_parse(b["started_at"]),_parse(b["ended_at"])
        if start and end and end >= start: durations.append((end-start).total_seconds()/60)

    by_day=[]
    for day, values in sorted(day_data.items()):
        decided=values["accepted"]+values["rejected"]
        by_day.append({"date":day, **values, "acceptance_rate":round(values["accepted"]/decided*100,2) if decided else 0.0})
    severity=Counter((e["severity"] or "Information") for e in events)
    event_types=Counter((e["event_type"] or "Unknown") for e in events)
    decided=accepted+rejected
    return DashboardSnapshot(
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        filters=asdict(filters), total_batches=total, finished_batches=finished,
        open_batches=total-finished, accepted_batches=accepted, rejected_batches=rejected,
        undecided_batches=max(0,total-decided), acceptance_rate=round(accepted/decided*100,2) if decided else 0.0,
        average_duration_minutes=round(sum(durations)/len(durations),2) if durations else None,
        warning_events=severity.get("Warning",0), critical_events=severity.get("Critical",0),
        unacknowledged_events=sum(1 for e in events if not int(e["acknowledged"] or 0)),
        by_day=by_day,
        by_product=_series(Counter(b["product_name"] for b in batches), total, "product"),
        by_line=_series(Counter(b["production_line"] for b in batches), total, "line"),
        by_operator=_series(Counter(b["operator_name"] for b in batches), total, "operator"),
        by_outcome=_series(Counter(b["qc_outcome"] or "Undecided" for b in batches), total, "outcome"),
        top_event_types=[{"event_type":k,"count":v} for k,v in event_types.most_common(10)],
    )


def distinct_filter_values() -> dict[str, list[str]]:
    initialize_database()
    with connect() as conn:
        result={}
        for col,key in (("product_name","products"),("production_line","lines"),("operator_name","operators")):
            result[key]=[r[0] for r in conn.execute(f"SELECT DISTINCT {col} FROM batches WHERE {col} IS NOT NULL AND trim({col})<>'' ORDER BY {col}")]
        return result


def export_dashboard_json(snapshot: DashboardSnapshot, path: str | Path) -> Path:
    target=Path(path); target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(snapshot.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def export_dashboard_csv(snapshot: DashboardSnapshot, path: str | Path) -> Path:
    target=Path(path); target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8-sig") as f:
        writer=csv.writer(f)
        writer.writerow(["VisionQC Management Dashboard", snapshot.generated_at])
        writer.writerow(["Metric","Value"])
        for key in ("total_batches","finished_batches","open_batches","accepted_batches","rejected_batches","undecided_batches","acceptance_rate","average_duration_minutes","warning_events","critical_events","unacknowledged_events"):
            writer.writerow([key, getattr(snapshot,key)])
        writer.writerow([]); writer.writerow(["Date","Total","Accepted","Rejected","Acceptance Rate"])
        for row in snapshot.by_day: writer.writerow([row["date"],row["total"],row["accepted"],row["rejected"],row["acceptance_rate"]])
    return target
