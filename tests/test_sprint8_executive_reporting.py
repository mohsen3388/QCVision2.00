from pathlib import Path

from visionqc.core.executive_reporting import ReportFilter, build_executive_snapshot, export_executive_csv, export_executive_json, export_executive_xlsx


def test_build_executive_snapshot_is_safe_on_empty_database():
    snapshot=build_executive_snapshot(ReportFilter())
    assert snapshot.total_batches >= 0
    assert 0 <= snapshot.acceptance_rate <= 100
    assert isinstance(snapshot.by_day,list)


def test_export_executive_formats(tmp_path: Path):
    snapshot=build_executive_snapshot()
    assert export_executive_json(snapshot,tmp_path/'r.json').exists()
    assert export_executive_csv(snapshot,tmp_path/'r.csv').exists()
    assert export_executive_xlsx(snapshot,tmp_path/'r.xlsx').exists()
