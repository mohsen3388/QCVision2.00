from pathlib import Path

from visionqc.core import database
from visionqc.core.settings import default_settings
from visionqc.core.spc import add_measurement, build_spc, export_spc_csv


def _use_temp_db(tmp_path, monkeypatch):
    settings = default_settings(); settings['data_directory'] = str(tmp_path); settings['reports_directory'] = str(tmp_path)
    monkeypatch.setattr(database, 'load_settings', lambda: settings)
    database.initialize_database()


def test_spc_capability_and_limits(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    for value in [9.8, 10.0, 10.1, 9.9, 10.2, 10.0, 9.7, 10.1]:
        add_measurement(metric_name='Texture Uniformity', value=value, target=10, lsl=9, usl=11)
    result = build_spc('Texture Uniformity')
    assert result.count == 8
    assert result.mean is not None and 9.9 < result.mean < 10.1
    assert result.ucl > result.mean > result.lcl
    assert result.cp is not None and result.cp > 1
    assert result.cpk is not None and result.cpk > 1


def test_spc_detects_spec_violation_and_exports(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    for value in [5, 5.1, 4.9, 7.5]:
        add_measurement(metric_name='Bubble Index', value=value, lsl=4, usl=6, product_name='A')
    result = build_spc('Bubble Index')
    assert result.out_of_spec == 1
    assert any(p['status'] == 'Out of specification' or 'Out of specification' in p['status'] for p in result.measurements)
    path = export_spc_csv(result, tmp_path / 'spc.csv')
    assert path.exists()
    text = path.read_text(encoding='utf-8-sig')
    assert 'Bubble Index' in text and 'out_of_spec' in text


def test_spc_validates_specification_limits(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    try:
        add_measurement(metric_name='X', value=1, lsl=2, usl=1)
    except ValueError as exc:
        assert 'LSL' in str(exc)
    else:
        raise AssertionError('Expected invalid limits to fail')
