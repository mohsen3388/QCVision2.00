from pathlib import Path
from visionqc.core.deployment import deployment_readiness, export_deployment_report, runtime_inventory

def test_runtime_inventory_contains_core_modules():
    names={x['module'] for x in runtime_inventory()}
    assert {'PySide6','cv2','numpy','sqlalchemy','reportlab'} <= names

def test_deployment_report_export(tmp_path: Path):
    report=deployment_readiness()
    assert report['visionqc_version']=='4.7.0'
    assert 'checks' in report and 'inventory' in report
    out=export_deployment_report(tmp_path/'deployment.json')
    assert out.exists() and '4.7.0' in out.read_text()
