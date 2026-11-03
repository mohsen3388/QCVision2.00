from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from visionqc.core.database import connect, initialize_database
from visionqc.core.settings import APP_VERSION, load_settings


@dataclass(frozen=True)
class ReportFilter:
    date_from: str | None = None
    date_to: str | None = None
    product_name: str | None = None
    production_line: str | None = None
    operator_name: str | None = None


@dataclass
class ExecutiveSnapshot:
    generated_at: str
    filters: dict[str, Any]
    total_batches: int
    accepted_batches: int
    rejected_batches: int
    acceptance_rate: float
    open_quality_events: int
    critical_quality_events: int
    average_quality_score: float | None
    average_oee: float | None
    corrective_action_effectiveness: float | None
    repeat_defect_rate: float | None
    camera_availability: float | None
    by_day: list[dict[str, Any]]
    by_shift: list[dict[str, Any]]
    by_line: list[dict[str, Any]]
    top_defects: list[dict[str, Any]]
    top_root_causes: list[dict[str, Any]]
    top_downtime_reasons: list[dict[str, Any]]
    active_runtime_events: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _table_exists(conn, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _where(filters: ReportFilter, alias: str = "b") -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if filters.date_from:
        clauses.append(f"date({alias}.started_at)>=date(?)"); params.append(filters.date_from)
    if filters.date_to:
        clauses.append(f"date({alias}.started_at)<=date(?)"); params.append(filters.date_to)
    if filters.product_name:
        clauses.append(f"{alias}.product_name=?"); params.append(filters.product_name)
    if filters.production_line:
        clauses.append(f"{alias}.production_line=?"); params.append(filters.production_line)
    if filters.operator_name:
        clauses.append(f"{alias}.operator_name=?"); params.append(filters.operator_name)
    return ((" WHERE " + " AND ".join(clauses)) if clauses else ""), params


def _accepted(value: str | None) -> bool:
    return (value or "").strip().lower() in {"accepted", "accept", "pass", "approved", "ok"}


def _rejected(value: str | None) -> bool:
    return (value or "").strip().lower() in {"rejected", "reject", "fail", "failed", "not ok"}


def build_executive_snapshot(filters: ReportFilter | None = None) -> ExecutiveSnapshot:
    initialize_database(); filters = filters or ReportFilter()
    with connect() as conn:
        where, params = _where(filters)
        batches = [dict(r) for r in conn.execute(f"SELECT * FROM batches b{where} ORDER BY started_at", params).fetchall()]
        ids = [int(b["id"]) for b in batches]
        process_events: list[dict[str, Any]] = []
        measurements: list[dict[str, Any]] = []
        if ids:
            ph = ",".join("?" for _ in ids)
            process_events = [dict(r) for r in conn.execute(f"SELECT * FROM process_events WHERE batch_id IN ({ph})", ids).fetchall()]
            if _table_exists(conn, "quality_measurements"):
                measurements = [dict(r) for r in conn.execute(f"SELECT * FROM quality_measurements WHERE batch_id IN ({ph})", ids).fetchall()]

        runtime_events = []
        if _table_exists(conn, "vqc3_runtime_events"):
            runtime_events = [dict(r) for r in conn.execute("SELECT * FROM vqc3_runtime_events WHERE state IN ('OPEN','ACKNOWLEDGED') ORDER BY opened_at DESC LIMIT 100").fetchall()]

        defects = []
        causes = []
        actions = []
        if _table_exists(conn, "factory_memory_defects"):
            defects = [dict(r) for r in conn.execute("SELECT d.* FROM factory_memory_defects d JOIN factory_memory_cases c ON c.id=d.case_id").fetchall()]
        if _table_exists(conn, "factory_memory_cases"):
            causes = [dict(r) for r in conn.execute("SELECT confirmed_cause,shift_name,production_line,status,passed FROM factory_memory_cases").fetchall()]
        if _table_exists(conn, "factory_memory_actions"):
            actions = [dict(r) for r in conn.execute("SELECT status,result,verified_at FROM factory_memory_actions").fetchall()]

        runs = []
        downtime = []
        if _table_exists(conn, "production_runs"):
            runs = [dict(r) for r in conn.execute("SELECT * FROM production_runs").fetchall()]
        if _table_exists(conn, "downtime_events"):
            downtime = [dict(r) for r in conn.execute("SELECT * FROM downtime_events").fetchall()]

        camera_health = []
        for candidate in ("vqc_edge_camera_health", "edge_camera_health", "camera_health"):
            if _table_exists(conn, candidate):
                camera_health = [dict(r) for r in conn.execute(f"SELECT * FROM {candidate}").fetchall()]; break

    total = len(batches)
    accepted = sum(_accepted(b.get("qc_outcome")) for b in batches)
    rejected = sum(_rejected(b.get("qc_outcome")) for b in batches)
    decided = accepted + rejected

    scores = []
    for m in measurements:
        for key in ("value", "score", "measurement"):
            if m.get(key) is not None:
                try: scores.append(float(m[key]))
                except (TypeError, ValueError): pass
                break

    day = defaultdict(lambda: {"total":0,"accepted":0,"rejected":0,"events":0})
    for b in batches:
        key=(b.get("started_at") or "")[:10] or "Unknown"; day[key]["total"] += 1
        if _accepted(b.get("qc_outcome")): day[key]["accepted"] += 1
        if _rejected(b.get("qc_outcome")): day[key]["rejected"] += 1
    batch_day={int(b["id"]):(b.get("started_at") or "")[:10] or "Unknown" for b in batches}
    for e in process_events:
        if int(e.get("batch_id") or 0) in batch_day: day[batch_day[int(e["batch_id"]) ]]["events"] += 1
    by_day=[]
    for key,val in sorted(day.items()):
        d=val["accepted"]+val["rejected"]
        by_day.append({"date":key,**val,"acceptance_rate":round(val["accepted"]/d*100,2) if d else 0.0})

    shift_counter=Counter((c.get("shift_name") or "Unspecified") for c in causes)
    line_counter=Counter((b.get("production_line") or "Unspecified") for b in batches)
    defect_counter=Counter((d.get("defect_type") or "Unspecified") for d in defects)
    cause_counter=Counter((c.get("confirmed_cause") or "").strip() for c in causes if (c.get("confirmed_cause") or "").strip())
    downtime_counter=Counter()
    for d in downtime:
        try: downtime_counter[d.get("reason") or "Unspecified"] += float(d.get("duration_minutes") or 0)
        except (TypeError, ValueError): pass

    oees=[]
    for r in runs:
        try:
            planned=float(r.get("planned_minutes") or 0); good=float(r.get("good_units") or 0); total_units=float(r.get("total_units") or 0); ideal=float(r.get("ideal_cycle_seconds") or 0)
            if planned>0 and total_units>0:
                availability=max(0.0,min(1.0,1.0-sum(float(d.get("duration_minutes") or 0) for d in downtime if d.get("run_id")==r.get("id"))/planned))
                performance=max(0.0,min(1.0,(ideal*total_units)/(planned*60))) if ideal>0 else 0
                quality=max(0.0,min(1.0,good/total_units))
                oees.append(availability*performance*quality*100)
        except (TypeError, ValueError): pass

    verified=[a for a in actions if a.get("verified_at") or a.get("result")]
    effective=sum(1 for a in verified if str(a.get("result") or a.get("status") or "").lower() in {"effective","موثر","resolved","successful","success"})
    failed_cases=sum(1 for c in causes if not int(c.get("passed") or 0))
    repeated=sum(1 for c in causes if str(c.get("status") or "").lower() in {"reopened","repeated","recurring"})

    availability=None
    if camera_health:
        healthy=sum(1 for c in camera_health if str(c.get("state") or c.get("status") or "").upper() in {"RUNNING","ONLINE","HEALTHY"})
        availability=round(healthy/len(camera_health)*100,2)

    return ExecutiveSnapshot(
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"), filters=asdict(filters),
        total_batches=total, accepted_batches=accepted, rejected_batches=rejected,
        acceptance_rate=round(accepted/decided*100,2) if decided else 0.0,
        open_quality_events=sum(1 for e in runtime_events if e.get("state") in {"OPEN","ACKNOWLEDGED"}) + sum(1 for e in process_events if not int(e.get("acknowledged") or 0)),
        critical_quality_events=sum(1 for e in runtime_events if str(e.get("severity") or "").lower() in {"critical","disaster"}) + sum(1 for e in process_events if str(e.get("severity") or "").lower() in {"critical","disaster"}),
        average_quality_score=round(sum(scores)/len(scores),2) if scores else None,
        average_oee=round(sum(oees)/len(oees),2) if oees else None,
        corrective_action_effectiveness=round(effective/len(verified)*100,2) if verified else None,
        repeat_defect_rate=round(repeated/failed_cases*100,2) if failed_cases else None,
        camera_availability=availability,
        by_day=by_day,
        by_shift=[{"shift":k,"count":v} for k,v in shift_counter.most_common()],
        by_line=[{"line":k,"count":v} for k,v in line_counter.most_common()],
        top_defects=[{"defect":k,"count":v} for k,v in defect_counter.most_common(10)],
        top_root_causes=[{"cause":k,"count":v} for k,v in cause_counter.most_common(10)],
        top_downtime_reasons=[{"reason":k,"minutes":round(v,2)} for k,v in downtime_counter.most_common(10)],
        active_runtime_events=[{k:r.get(k) for k in ("camera_id","severity","state","problem_text","opened_at")} for r in runtime_events[:20]],
    )


def export_executive_json(snapshot: ExecutiveSnapshot, path: str | Path) -> Path:
    target=Path(path); target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(snapshot.to_dict(),ensure_ascii=False,indent=2),encoding="utf-8")
    return target


def export_executive_csv(snapshot: ExecutiveSnapshot, path: str | Path) -> Path:
    target=Path(path); target.parent.mkdir(parents=True,exist_ok=True)
    with target.open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f); w.writerow(["VisionQC Executive Quality Report",snapshot.generated_at]); w.writerow(["KPI","Value"])
        for key in ("total_batches","accepted_batches","rejected_batches","acceptance_rate","open_quality_events","critical_quality_events","average_quality_score","average_oee","corrective_action_effectiveness","repeat_defect_rate","camera_availability"):
            w.writerow([key,getattr(snapshot,key)])
        w.writerow([]); w.writerow(["Date","Total","Accepted","Rejected","Acceptance Rate","Events"])
        for r in snapshot.by_day: w.writerow([r["date"],r["total"],r["accepted"],r["rejected"],r["acceptance_rate"],r["events"]])
    return target


def export_executive_xlsx(snapshot: ExecutiveSnapshot, path: str | Path) -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    target=Path(path); target.parent.mkdir(parents=True,exist_ok=True)
    wb=Workbook(); ws=wb.active; ws.title="Executive KPIs"
    ws.append(["VisionQC Executive Quality Report", snapshot.generated_at]); ws["A1"].font=Font(bold=True,size=14)
    ws.append(["KPI","Value"])
    for key in ("total_batches","accepted_batches","rejected_batches","acceptance_rate","open_quality_events","critical_quality_events","average_quality_score","average_oee","corrective_action_effectiveness","repeat_defect_rate","camera_availability"):
        ws.append([key,getattr(snapshot,key)])
    ws2=wb.create_sheet("Daily Trend"); ws2.append(["Date","Total","Accepted","Rejected","Acceptance Rate","Events"])
    for r in snapshot.by_day: ws2.append([r["date"],r["total"],r["accepted"],r["rejected"],r["acceptance_rate"],r["events"]])
    ws3=wb.create_sheet("Root Causes"); ws3.append(["Cause","Count"])
    for r in snapshot.top_root_causes: ws3.append([r["cause"],r["count"]])
    ws4=wb.create_sheet("Defects"); ws4.append(["Defect","Count"])
    for r in snapshot.top_defects: ws4.append([r["defect"],r["count"]])
    for sheet in wb.worksheets:
        for cell in sheet[1]: cell.fill=PatternFill("solid",fgColor="D9EAF7"); cell.font=Font(bold=True)
        sheet.freeze_panes="A2"
        for col in sheet.columns:
            letter=col[0].column_letter; sheet.column_dimensions[letter].width=min(45,max(12,max(len(str(c.value or "")) for c in col)+2))
    wb.save(target); return target


def export_executive_pdf(snapshot: ExecutiveSnapshot, path: str | Path) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    target=Path(path); target.parent.mkdir(parents=True,exist_ok=True)
    styles=getSampleStyleSheet(); doc=SimpleDocTemplate(str(target),pagesize=A4,rightMargin=14*mm,leftMargin=14*mm,topMargin=14*mm,bottomMargin=14*mm,title="VisionQC Executive Quality Report",author="VisionQC")
    story=[Paragraph("VisionQC Executive Quality & KPI Report",styles["Title"]),Paragraph(f"Generated: {snapshot.generated_at} | VisionQC {APP_VERSION}",styles["BodyText"]),Spacer(1,5*mm)]
    kpis=[("Total batches",snapshot.total_batches),("Acceptance rate",f"{snapshot.acceptance_rate:.1f}%"),("Open events",snapshot.open_quality_events),("Critical events",snapshot.critical_quality_events),("Average quality score",snapshot.average_quality_score),("Average OEE",snapshot.average_oee),("Corrective action effectiveness",snapshot.corrective_action_effectiveness),("Repeat defect rate",snapshot.repeat_defect_rate),("Camera availability",snapshot.camera_availability)]
    table=Table([["KPI","Value"]]+[[k,"—" if v is None else v] for k,v in kpis],colWidths=[105*mm,55*mm])
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#1e293b")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#cbd5e1")),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f8fafc")]),("PADDING",(0,0),(-1,-1),6)])); story += [table,Spacer(1,5*mm)]
    for title, rows, cols in (("Top defects",snapshot.top_defects,("defect","count")),("Confirmed root causes",snapshot.top_root_causes,("cause","count")),("Downtime reasons",snapshot.top_downtime_reasons,("reason","minutes"))):
        story.append(Paragraph(title,styles["Heading2"])); data=[[cols[0].replace("_"," ").title(),cols[1].title()]]+[[r.get(cols[0]),r.get(cols[1])] for r in rows[:10]]
        if len(data)==1:data.append(["No data","—"])
        t=Table(data,colWidths=[120*mm,40*mm]); t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e2e8f0")),("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#cbd5e1")),("PADDING",(0,0),(-1,-1),5)])); story += [t,Spacer(1,4*mm)]
    story.append(Paragraph("Decision-support notice: these KPIs support management and QC review and do not replace laboratory tests, food-safety procedures, regulatory controls or qualified human approval.",styles["BodyText"]))
    doc.build(story); return target


def default_report_path(suffix: str) -> Path:
    settings=load_settings(); folder=Path(settings["reports_directory"]); folder.mkdir(parents=True,exist_ok=True)
    return folder/f"VisionQC_Executive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{suffix.lstrip('.')}"
