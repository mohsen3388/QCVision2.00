from pathlib import Path
from visionqc.core.analytics import DashboardFilter, build_dashboard, export_dashboard_csv, export_dashboard_json
from visionqc.core.database import create_batch, update_batch, connect, initialize_database


def test_dashboard_kpis_and_filters(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    initialize_database()
    a=create_batch("S5-A","Emulsion A","Line 1","Alice","Mixing")
    b=create_batch("S5-B","Emulsion B","Line 2","Bob","Filling")
    update_batch(a,"Finished","",status="Finished",qc_outcome="Accepted")
    update_batch(b,"Finished","",status="Finished",qc_outcome="Rejected")
    with connect() as c:
        c.execute("INSERT INTO process_events(batch_id,event_type,severity,source,message,created_at) VALUES(?,?,?,?,?,datetime('now'))",(b,"QUALITY_WARNING","Critical","Test","Rejected"))
    s=build_dashboard(); assert s.total_batches==2; assert s.acceptance_rate==50.0; assert s.critical_events==1
    filtered=build_dashboard(DashboardFilter(product_name="Emulsion A")); assert filtered.total_batches==1; assert filtered.accepted_batches==1


def test_dashboard_exports(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path/"data")); initialize_database(); create_batch("S5-C","Product","L1","Op","Stage")
    s=build_dashboard(); j=export_dashboard_json(s,tmp_path/"dashboard.json"); c=export_dashboard_csv(s,tmp_path/"dashboard.csv")
    assert j.exists() and '"total_batches": 1' in j.read_text(encoding="utf-8")
    assert c.exists() and "VisionQC Management Dashboard" in c.read_text(encoding="utf-8-sig")
