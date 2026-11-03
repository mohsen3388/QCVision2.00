
import numpy as np
from pathlib import Path
from visionqc.configuration.repository import ConfigurationRepository
from visionqc.configuration.runtime_repository import RuntimeRepository
from visionqc.configuration.production_runtime import ProductionRuntimeEngine
from visionqc.configuration.seed import sausage_batter_template
import visionqc.core.database as db

def setup_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'database_path', lambda: tmp_path/'phase3.db')

def test_assignment_and_runtime_sample(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch); cr=ConfigurationRepository(); rr=RuntimeRepository(); t=sausage_batter_template(); t.lifecycle='Production'
    for m in t.metrics:m.lifecycle='Production'
    for x in t.triggers:x.lifecycle='Production'; x.persistence_seconds=0
    for a in t.actions:a.lifecycle='Production'
    cr.save_template(t,'test_publish'); rr.assign('cam1','دیگ ۱','File','x.mp4',t.key,.5)
    e=ProductionRuntimeEngine(cr,rr); frame=np.full((240,320,3),128,dtype=np.uint8); r=e.process_frame('cam1',frame)
    assert r['template_key']==t.key and len(r['metrics'])==len(t.metrics)
    assert rr.metric_history('cam1',t.metrics[0].key)

def test_production_gate(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch); cr=ConfigurationRepository(); rr=RuntimeRepository(); t=sausage_batter_template(); t.lifecycle='Validated'; cr.save_template(t); rr.assign('cam1','دیگ','File','x',t.key)
    e=ProductionRuntimeEngine(cr,rr)
    try:e.process_frame('cam1',np.zeros((50,50,3),dtype=np.uint8)); assert False
    except ValueError as exc:assert 'Production' in str(exc)

def test_event_open_and_resolve(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch); cr=ConfigurationRepository(); rr=RuntimeRepository(); t=sausage_batter_template(); t.lifecycle='Production'
    for m in t.metrics:m.lifecycle='Production'
    # deterministic always true trigger on score below 101
    tr=t.triggers[0]; tr.lifecycle='Production'; tr.persistence_seconds=0; tr.conditions[0].function='last'; tr.conditions[0].operator='<'; tr.conditions[0].threshold=101
    for a in t.actions:a.lifecycle='Production'
    cr.save_template(t); rr.assign('cam1','دیگ','File','x',t.key)
    e=ProductionRuntimeEngine(cr,rr); e.process_frame('cam1',np.full((80,80,3),100,dtype=np.uint8)); assert rr.active_event('cam1',tr.key)
