import json
from pathlib import Path

from visionqc.core.automation import MetricProfile, import_analysis_payload, list_imports, list_metric_profiles, save_metric_profile
from visionqc.core import database
from visionqc.core.database import connect, initialize_database
from visionqc.core.settings import default_settings


def test_analysis_import_to_spc_and_events(tmp_path, monkeypatch):
    settings=default_settings(); settings["data_directory"]=str(tmp_path); settings["reports_directory"]=str(tmp_path)
    monkeypatch.setattr(database,"load_settings",lambda:settings)
    initialize_database()
    save_metric_profile(MetricProfile("brightness", "Image Quality", "level", 100, 70, 200))
    payload={"source_path":"sample.png","metrics":{"Image Quality":{"brightness":120.5,"contrast":4.2},"Other":{"flag":True}},
             "findings":[{"triggered":True,"severity":"Warning","title":"Low focus","rule_id":"F1","reason":"blur"}]}
    result=import_analysis_payload(payload, product_name="Emulsion", production_line="L1")
    assert result.imported_metrics==2 and result.generated_events==1
    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM quality_measurements").fetchone()[0]==2
        row=conn.execute("SELECT * FROM quality_measurements WHERE metric_name='brightness'").fetchone()
        assert row['lsl']==70 and row['usl']==200 and row['source']=='Automated Analysis Import'
        assert conn.execute("SELECT COUNT(*) FROM process_events WHERE event_type='ANALYSIS_FINDING'").fetchone()[0]==1
    assert len(list_imports())==1


def test_disabled_or_profile_only_import(tmp_path, monkeypatch):
    settings=default_settings(); settings["data_directory"]=str(tmp_path); settings["reports_directory"]=str(tmp_path)
    monkeypatch.setattr(database,"load_settings",lambda:settings)
    initialize_database()
    save_metric_profile(MetricProfile("brightness", enabled=False))
    result=import_analysis_payload({"metrics":{"Image":{"brightness":1,"contrast":2}}}, import_unprofiled=False)
    assert result.imported_metrics==0 and result.skipped_metrics==2


def test_profile_validation(tmp_path, monkeypatch):
    settings=default_settings(); settings["data_directory"]=str(tmp_path); settings["reports_directory"]=str(tmp_path)
    monkeypatch.setattr(database,"load_settings",lambda:settings)
    initialize_database()
    try:
        save_metric_profile(MetricProfile("x", lsl=10, usl=5))
        assert False
    except ValueError:
        pass
