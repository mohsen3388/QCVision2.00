from __future__ import annotations

import csv
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, stdev

from visionqc.core.database import connect, initialize_database


@dataclass(frozen=True)
class Measurement:
    id: int
    batch_id: int | None
    metric_name: str
    metric_group: str
    value: float
    unit: str
    product_name: str | None
    production_line: str | None
    operator_name: str | None
    target: float | None
    lsl: float | None
    usl: float | None
    captured_at: str
    source: str
    notes: str


@dataclass
class SPCSnapshot:
    metric_name: str
    count: int
    mean: float | None
    sigma: float | None
    center_line: float | None
    ucl: float | None
    lcl: float | None
    target: float | None
    lsl: float | None
    usl: float | None
    cp: float | None
    cpk: float | None
    out_of_control: int
    out_of_spec: int
    trend_warnings: int
    measurements: list[dict]

    def to_dict(self) -> dict:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def add_measurement(*, metric_name: str, value: float, metric_group: str = "Quality", unit: str = "", batch_id: int | None = None,
                    product_name: str | None = None, production_line: str | None = None, operator_name: str | None = None,
                    target: float | None = None, lsl: float | None = None, usl: float | None = None,
                    captured_at: str | None = None, source: str = "Manual", notes: str = "") -> int:
    initialize_database()
    if not metric_name.strip():
        raise ValueError("metric_name is required")
    if not math.isfinite(float(value)):
        raise ValueError("value must be finite")
    if lsl is not None and usl is not None and lsl >= usl:
        raise ValueError("LSL must be lower than USL")
    with connect() as conn:
        cur = conn.execute("""
            INSERT INTO quality_measurements(batch_id,metric_name,metric_group,value,unit,product_name,production_line,operator_name,target,lsl,usl,captured_at,source,notes)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (batch_id, metric_name.strip(), metric_group.strip() or "Quality", float(value), unit.strip(), product_name, production_line,
              operator_name, target, lsl, usl, captured_at or _now(), source, notes))
        return int(cur.lastrowid)


def list_metric_names() -> list[str]:
    initialize_database()
    with connect() as conn:
        return [r[0] for r in conn.execute("SELECT DISTINCT metric_name FROM quality_measurements ORDER BY metric_name")]


def list_measurements(metric_name: str, limit: int = 500, product_name: str | None = None, production_line: str | None = None) -> list[Measurement]:
    initialize_database()
    parts = ["metric_name=?"]
    params: list[object] = [metric_name]
    if product_name:
        parts.append("product_name=?"); params.append(product_name)
    if production_line:
        parts.append("production_line=?"); params.append(production_line)
    params.append(limit)
    sql = f"SELECT * FROM quality_measurements WHERE {' AND '.join(parts)} ORDER BY captured_at,id LIMIT ?"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [Measurement(**dict(r)) for r in rows]


def _trend_warnings(values: list[float], center: float) -> int:
    warnings = 0
    # Western Electric-inspired, explainable lightweight checks.
    for i in range(6, len(values)):
        window = values[i-6:i+1]
        if all(window[j] < window[j+1] for j in range(6)) or all(window[j] > window[j+1] for j in range(6)):
            warnings += 1
    for i in range(7, len(values)):
        window = values[i-7:i+1]
        if all(v > center for v in window) or all(v < center for v in window):
            warnings += 1
    return warnings


def build_spc(metric_name: str, *, product_name: str | None = None, production_line: str | None = None, limit: int = 500) -> SPCSnapshot:
    rows = list_measurements(metric_name, limit, product_name, production_line)
    values = [r.value for r in rows]
    if not values:
        return SPCSnapshot(metric_name, 0, None, None, None, None, None, None, None, None, None, None, 0, 0, 0, [])
    avg = mean(values)
    sigma = stdev(values) if len(values) >= 2 else 0.0
    ucl = avg + 3 * sigma
    lcl = avg - 3 * sigma
    latest = rows[-1]
    target, lsl, usl = latest.target, latest.lsl, latest.usl
    cp = ((usl - lsl) / (6 * sigma)) if sigma > 0 and lsl is not None and usl is not None else None
    cpk = (min((usl - avg), (avg - lsl)) / (3 * sigma)) if sigma > 0 and lsl is not None and usl is not None else None
    out_control = sum(1 for v in values if v > ucl or v < lcl) if sigma > 0 else 0
    out_spec = sum(1 for v in values if (lsl is not None and v < lsl) or (usl is not None and v > usl))
    points=[]
    for index,row in enumerate(rows, start=1):
        status=[]
        if sigma > 0 and (row.value > ucl or row.value < lcl): status.append("Out of control")
        if (lsl is not None and row.value < lsl) or (usl is not None and row.value > usl): status.append("Out of specification")
        points.append({**asdict(row), "sequence": index, "status": "; ".join(status) or "In control"})
    return SPCSnapshot(metric_name, len(values), round(avg,6), round(sigma,6), round(avg,6), round(ucl,6), round(lcl,6), target, lsl, usl,
                       None if cp is None else round(cp,4), None if cpk is None else round(cpk,4), out_control, out_spec,
                       _trend_warnings(values, avg), points)


def export_spc_csv(snapshot: SPCSnapshot, path: str | Path) -> Path:
    target=Path(path); target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8-sig") as f:
        w=csv.writer(f)
        w.writerow(["VisionQC SPC Report", snapshot.metric_name])
        w.writerow(["Metric","Value"])
        for key in ("count","mean","sigma","ucl","lcl","target","lsl","usl","cp","cpk","out_of_control","out_of_spec","trend_warnings"):
            w.writerow([key,getattr(snapshot,key)])
        w.writerow([]); w.writerow(["Sequence","Captured At","Value","Batch ID","Product","Line","Source","Status","Notes"])
        for r in snapshot.measurements:
            w.writerow([r["sequence"],r["captured_at"],r["value"],r["batch_id"],r["product_name"],r["production_line"],r["source"],r["status"],r["notes"]])
    return target
