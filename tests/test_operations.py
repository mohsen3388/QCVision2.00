import pytest
from visionqc.core import database
from visionqc.core.settings import default_settings
from visionqc.core.operations import create_shift,create_production_run,add_downtime,calculate_oee,update_run_counts,export_oee


def setup_db(tmp_path,monkeypatch):
    s=default_settings(); s['data_directory']=str(tmp_path); s['reports_directory']=str(tmp_path)
    monkeypatch.setattr(database,'load_settings',lambda:s); database.initialize_database()


def test_oee_calculation(tmp_path,monkeypatch):
    setup_db(tmp_path,monkeypatch)
    sid=create_shift('Day','06:00','14:00',planned_break_minutes=30)
    rid=create_production_run(shift_id=sid,production_line='L1',product_name='P',planned_minutes=480,ideal_cycle_seconds=10,total_units=2400,good_units=2280)
    add_downtime(rid,'Cleaning',30,'Planned'); add_downtime(rid,'Jam',15,'Unplanned')
    s=calculate_oee(rid)
    assert s.planned_minutes==450
    assert s.operating_minutes==405
    assert s.availability==pytest.approx(.9)
    assert s.quality==pytest.approx(.95)
    assert 0 < s.performance <= 1
    assert s.oee==pytest.approx(s.availability*s.performance*s.quality)
    assert s.downtime_minutes==45


def test_counts_validation_and_export(tmp_path,monkeypatch):
    setup_db(tmp_path,monkeypatch)
    sid=create_shift('Night','22:00','06:00')
    rid=create_production_run(shift_id=sid,production_line='L2',product_name='X',planned_minutes=60,ideal_cycle_seconds=5)
    with pytest.raises(ValueError): update_run_counts(rid,10,11)
    update_run_counts(rid,600,590,True)
    snap=calculate_oee(rid)
    assert snap.rejected_units==10
    assert export_oee(snap,tmp_path/'oee.json').exists()
    assert export_oee(snap,tmp_path/'oee.csv').exists()
