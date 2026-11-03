from pathlib import Path
import sqlite3
from visionqc.core import backup
from visionqc.core.health import health_report


def test_backup_create_validate_restore(tmp_path, monkeypatch):
    data=tmp_path/'data'; data.mkdir(); db=data/'visionqc.db'
    with sqlite3.connect(db) as c:
        c.execute('create table sample(id integer primary key, value text)')
        c.execute("insert into sample(value) values ('original')")
    settings=tmp_path/'settings.json'; settings.write_text('{"theme":"Dark"}',encoding='utf-8')
    monkeypatch.setattr(backup,'database_path',lambda:db)
    monkeypatch.setattr(backup,'settings_path',lambda:settings)
    archive=backup.create_backup(tmp_path/'out')
    info=backup.validate_backup(archive)
    assert info['has_database'] and info['has_settings']
    with sqlite3.connect(db) as c:
        c.execute("update sample set value='changed'")
    backup.restore_backup(archive)
    with sqlite3.connect(db) as c:
        assert c.execute('select value from sample').fetchone()[0]=='original'


def test_health_report_has_core_checks():
    result=health_report()
    assert result['status'] in {'Healthy','Attention'}
    names={c['name'] for c in result['checks']}
    assert {'Database','Data directory','Reports directory','Settings'} <= names
