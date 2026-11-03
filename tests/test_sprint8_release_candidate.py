from pathlib import Path
import sqlite3

from visionqc.application.services.release_readiness_service import ReleaseReadinessService
from visionqc.core import backup, database, health, deployment
from visionqc.core.migrations import apply_pending_migrations, current_schema_version, latest_schema_version
from visionqc.infrastructure.persistence.sqlite_audit import SqliteAuditTrailRepository


class DummyBus:
    def __init__(self): self.events=[]
    def publish(self,event): self.events.append(event)


def _redirect_storage(monkeypatch, tmp_path):
    db = tmp_path / 'visionqc.db'
    settings = tmp_path / 'settings.json'
    settings.write_text('{"factory_name":"Test","operator_name":"QC","data_directory":"%s","reports_directory":"%s","camera_index":0,"theme":"Factory Blue","ui_scale":100}' % (str(tmp_path).replace('\\','/'), str(tmp_path/'reports').replace('\\','/')), encoding='utf-8')
    monkeypatch.setattr(database, 'database_path', lambda: db)
    monkeypatch.setattr(backup, 'database_path', lambda: db)
    monkeypatch.setattr(backup, 'settings_path', lambda: settings)
    monkeypatch.setattr(health, 'database_path', lambda: db)
    monkeypatch.setattr(health, 'settings_path', lambda: settings)
    monkeypatch.setattr(health, 'load_settings', lambda: {"data_directory":str(tmp_path),"reports_directory":str(tmp_path/'reports')})
    monkeypatch.setattr(deployment, 'load_settings', lambda: {"data_directory":str(tmp_path),"reports_directory":str(tmp_path/'reports')})
    import visionqc.core.migrations as migrations
    import visionqc.infrastructure.persistence.sqlite_audit as audit_module
    import visionqc.application.services.release_readiness_service as release_module
    monkeypatch.setattr(migrations, 'connect', lambda: sqlite3.connect(db))
    monkeypatch.setattr(audit_module, 'connect', lambda: sqlite3.connect(db))
    monkeypatch.setattr(release_module, 'database_path', lambda: db)
    monkeypatch.setattr(release_module, 'app_data_dir', lambda: tmp_path)
    monkeypatch.setattr(release_module, 'load_settings', lambda: {"data_directory":str(tmp_path),"reports_directory":str(tmp_path/'reports')})
    database.initialize_database()
    return db


def test_sprint8_migrations_and_append_only_audit(monkeypatch, tmp_path):
    _redirect_storage(monkeypatch, tmp_path)
    apply_pending_migrations()
    assert current_schema_version() == latest_schema_version()
    repo = SqliteAuditTrailRepository()
    event_id = repo.append('test.event', actor='tester', entity_type='case', entity_id='42', details={'safe': True})
    assert event_id > 0
    rows = repo.recent()
    assert rows[0]['event_type'] == 'test.event'
    assert rows[0]['details']['safe'] is True


def test_sprint8_release_assessment_and_export(monkeypatch, tmp_path):
    _redirect_storage(monkeypatch, tmp_path)
    apply_pending_migrations()
    repo = SqliteAuditTrailRepository()
    bus = DummyBus()
    service = ReleaseReadinessService(repo, bus)
    report = service.assess()
    assert report.level.value in {'Ready','Attention','Blocked'}
    assert any(c.name == 'Validated release backup' and c.ok for c in report.checks)
    assert any(c.name == 'Database schema version' and c.ok for c in report.checks)
    target = service.export_report(tmp_path/'release.json', report)
    assert target.exists()
    assert bus.events and bus.events[0].name == 'release_candidate.assessment_completed'
    assert len(repo.recent()) >= 2
