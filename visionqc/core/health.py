from __future__ import annotations
from pathlib import Path
import shutil, sqlite3
from visionqc.core.database import database_path
from visionqc.core.settings import load_settings, settings_path


def health_report() -> dict:
    s=load_settings(); checks=[]
    def add(name,ok,message): checks.append({"name":name,"ok":bool(ok),"message":message})
    try:
        db=database_path(); db.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(db) as c: result=c.execute('PRAGMA integrity_check').fetchone()[0]
        add('Database',result=='ok',f'Integrity: {result}')
    except Exception as e: add('Database',False,str(e))
    for label,key in [('Data directory','data_directory'),('Reports directory','reports_directory')]:
        try:
            p=Path(s[key]); p.mkdir(parents=True,exist_ok=True); test=p/'.visionqc_write_test'; test.write_text('ok'); test.unlink()
            free=shutil.disk_usage(p).free/(1024**3); add(label,free>=1,f'Writable; {free:.2f} GB free')
        except Exception as e: add(label,False,str(e))
    add('Settings',settings_path().exists(),'Settings file available' if settings_path().exists() else 'Using defaults')
    return {"status":"Healthy" if all(x['ok'] for x in checks) else "Attention","checks":checks}
