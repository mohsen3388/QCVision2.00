from __future__ import annotations
from datetime import datetime
from pathlib import Path
import json, shutil, sqlite3, zipfile
from visionqc.core.database import database_path
from visionqc.core.settings import APP_VERSION, settings_path


def create_backup(destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S')
    target=destination/f'VisionQC_Backup_{stamp}.zip'
    db=database_path()
    temp=destination/f'.visionqc_backup_{stamp}.db'
    if db.exists():
        src=sqlite3.connect(db); dst=sqlite3.connect(temp)
        try:
            src.backup(dst); dst.commit()
        finally:
            dst.close(); src.close()
    manifest={"format":1,"visionqc_version":APP_VERSION,"created_at":datetime.now().isoformat(timespec='seconds')}
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('manifest.json',json.dumps(manifest,indent=2))
        if temp.exists(): z.write(temp,'visionqc.db')
        if settings_path().exists(): z.write(settings_path(),'settings.json')
    temp.unlink(missing_ok=True)
    return target


def validate_backup(source: Path) -> dict:
    with zipfile.ZipFile(source) as z:
        names=set(z.namelist())
        if 'manifest.json' not in names: raise ValueError('Backup manifest is missing.')
        manifest=json.loads(z.read('manifest.json'))
        if manifest.get('format') != 1: raise ValueError('Unsupported backup format.')
        return {"manifest":manifest,"has_database":'visionqc.db' in names,"has_settings":'settings.json' in names}


def restore_backup(source: Path, restore_settings: bool=True) -> dict:
    info=validate_backup(source)
    db=database_path(); db.parent.mkdir(parents=True,exist_ok=True)
    safety=db.with_suffix('.pre_restore.bak')
    if db.exists(): shutil.copy2(db,safety)
    with zipfile.ZipFile(source) as z:
        if info['has_database']:
            temp=db.with_suffix('.restore.tmp'); temp.write_bytes(z.read('visionqc.db'))
            conn=sqlite3.connect(temp)
            try:
                result=conn.execute('PRAGMA integrity_check').fetchone()
                if not result or result[0] != 'ok': raise ValueError('Backup database integrity check failed.')
            finally:
                conn.close()
            if db.exists(): db.unlink()
            temp.replace(db)
        if restore_settings and info['has_settings']:
            settings_path().write_bytes(z.read('settings.json'))
    return {**info,"safety_copy":str(safety) if safety.exists() else None}
