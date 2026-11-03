from pathlib import Path

from visionqc.core.database import create_batch, initialize_database, update_batch
from visionqc.core.reporting import build_qr_payload, generate_batch_pdf, get_batch_timeline, list_reports


def test_pdf_report_and_qr_payload(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    initialize_database()
    batch_id=create_batch("B-4301","Emulsion A","Line 1","Operator","Mixing","Initial note")
    update_batch(batch_id,"Finished","Completed",status="Finished",qc_outcome="Accepted")
    output=tmp_path / "report.pdf"
    result=generate_batch_pdf(batch_id, output)
    assert result.path.exists()
    assert result.path.stat().st_size > 1000
    assert '"schema":"visionqc-report-v1"' in result.qr_payload
    reports=list_reports(batch_id)
    assert len(reports)==1
    assert reports[0]["report_code"].startswith("VQC-")


def test_timeline_contains_batch_start(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    initialize_database()
    batch_id=create_batch("B-4302","Emulsion B","Line 2","Operator","Preparation")
    timeline=get_batch_timeline(batch_id)
    assert timeline
    assert timeline[0]["event_type"]=="BATCH_STARTED"
