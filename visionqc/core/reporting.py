from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from visionqc.core.database import connect, utc_now
from visionqc.core.settings import APP_VERSION, load_settings


@dataclass(frozen=True)
class ReportResult:
    report_id: int
    path: Path
    qr_payload: str


def _safe(value: Any) -> str:
    return "—" if value in (None, "") else str(value)


def get_batch_record(batch_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
        return dict(row) if row else None


def get_batch_timeline(batch_id: int) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT created_at,event_type,'Information' AS severity,'Batch Workspace' AS source,message
            FROM batch_events WHERE batch_id=?
            UNION ALL
            SELECT created_at,event_type,severity,source,message
            FROM process_events WHERE batch_id=?
            ORDER BY created_at ASC
            """,
            (batch_id, batch_id),
        ).fetchall()
        return [dict(r) for r in rows]


def build_qr_payload(batch: dict[str, Any], report_code: str) -> str:
    payload = {
        "schema": "visionqc-report-v1",
        "report_code": report_code,
        "batch_id": batch["id"],
        "batch_code": batch["batch_code"],
        "product": batch["product_name"],
        "qc_outcome": batch.get("qc_outcome"),
        "generated_by": f"VisionQC {APP_VERSION}",
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _qr_drawing(payload: str, size: float = 35 * mm) -> Drawing:
    widget = qr.QrCodeWidget(payload)
    bounds = widget.getBounds()
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    drawing = Drawing(size, size, transform=[size / width, 0, 0, size / height, 0, 0])
    drawing.add(widget)
    return drawing


def generate_batch_pdf(batch_id: int, output_path: str | Path | None = None, *, include_timeline: bool = True) -> ReportResult:
    batch = get_batch_record(batch_id)
    if not batch:
        raise ValueError(f"Batch {batch_id} does not exist")
    settings = load_settings()
    report_code = f"VQC-{batch['id']:06d}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    if output_path is None:
        safe_code = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in batch["batch_code"])
        output_path = Path(settings["reports_directory"]) / f"VisionQC_Report_{safe_code}_{report_code}.pdf"
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_qr_payload(batch, report_code)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CenterSmall", parent=styles["BodyText"], alignment=TA_CENTER, fontSize=8, leading=10))
    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=16*mm, leftMargin=16*mm, topMargin=15*mm, bottomMargin=15*mm,
                            title=f"VisionQC Batch Report {batch['batch_code']}", author="VisionQC")
    story = []
    header = Table([
        [Paragraph(f"<b>VisionQC Quality Report</b><br/><font size='9'>{_safe(settings.get('factory_name'))}</font>", styles["Title"]), _qr_drawing(payload)],
        [Paragraph(f"Report code: <b>{report_code}</b><br/>Generated: {datetime.now().isoformat(timespec='seconds')}<br/>Software: VisionQC {APP_VERSION}", styles["BodyText"]), Paragraph("Scan to verify report identity and batch summary", styles["CenterSmall"])],
    ], colWidths=[130*mm, 40*mm])
    header.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("BOX",(0,0),(-1,-1),0.8,colors.HexColor("#334155")),("INNERGRID",(0,0),(-1,-1),0.25,colors.HexColor("#cbd5e1")),("BACKGROUND",(0,0),(-1,0),colors.HexColor("#eef2ff")),("PADDING",(0,0),(-1,-1),7)]))
    story += [header, Spacer(1, 8*mm), Paragraph("Batch Summary", styles["Heading2"])]
    fields = [
        ("Batch code", batch["batch_code"]), ("Product / recipe", batch["product_name"]),
        ("Production line", batch.get("production_line")), ("Operator", batch.get("operator_name")),
        ("Process stage", batch.get("process_stage")), ("Status", batch.get("status")),
        ("QC outcome", batch.get("qc_outcome")), ("Started", batch.get("started_at")),
        ("Ended", batch.get("ended_at")), ("Notes", batch.get("notes")),
    ]
    data = [[Paragraph(f"<b>{label}</b>", styles["BodyText"]), Paragraph(_safe(value), styles["BodyText"])] for label, value in fields]
    summary = Table(data, colWidths=[47*mm, 123*mm], repeatRows=0)
    summary.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.35,colors.HexColor("#cbd5e1")),("BACKGROUND",(0,0),(0,-1),colors.HexColor("#f8fafc")),("VALIGN",(0,0),(-1,-1),"TOP"),("PADDING",(0,0),(-1,-1),6)]))
    story += [summary, Spacer(1, 7*mm)]

    if include_timeline:
        timeline = get_batch_timeline(batch_id)
        story.append(Paragraph("Auditable Event Timeline", styles["Heading2"]))
        rows = [["Time", "Severity", "Source", "Event", "Description"]]
        for e in timeline:
            rows.append([_safe(e.get("created_at")), _safe(e.get("severity")), _safe(e.get("source")), _safe(e.get("event_type")), _safe(e.get("message"))])
        if len(rows) == 1:
            rows.append(["—", "—", "—", "—", "No events recorded."])
        table = Table(rows, colWidths=[35*mm, 22*mm, 27*mm, 34*mm, 52*mm], repeatRows=1)
        table.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#cbd5e1")),("BACKGROUND",(0,0),(-1,0),colors.HexColor("#1e293b")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),7.5),("VALIGN",(0,0),(-1,-1),"TOP"),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f8fafc")]),("PADDING",(0,0),(-1,-1),4)]))
        story += [table, Spacer(1, 6*mm)]

    story += [Paragraph("Decision-support notice", styles["Heading3"]), Paragraph("VisionQC provides explainable visual quality decision support. This report does not replace laboratory testing, food-safety procedures, qualified quality-control approval, or applicable regulatory requirements.", styles["BodyText"])]
    doc.build(story)

    with connect() as conn:
        cur = conn.execute("INSERT INTO generated_reports(batch_id,report_code,file_path,qr_payload,created_at) VALUES(?,?,?,?,?)", (batch_id, report_code, str(path), payload, utc_now()))
        report_id = int(cur.lastrowid)
    return ReportResult(report_id=report_id, path=path, qr_payload=payload)


def list_reports(batch_id: int | None = None) -> list[dict[str, Any]]:
    sql = "SELECT r.*, b.batch_code, b.product_name FROM generated_reports r JOIN batches b ON b.id=r.batch_id"
    params: tuple[Any, ...] = ()
    if batch_id is not None:
        sql += " WHERE r.batch_id=?"; params = (batch_id,)
    sql += " ORDER BY r.id DESC"
    with connect() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
