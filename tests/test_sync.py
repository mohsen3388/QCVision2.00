import sqlite3
from pathlib import Path
from visionqc.core import settings
from visionqc.core.database import initialize_database
from visionqc.core.sync import generate_sync_key,fingerprint,queue_change,queue_summary,create_sync_package,validate_sync_package,import_sync_package,list_packages

def setup_db(tmp_path,monkeypatch):
 monkeypatch.setattr(settings,'app_data_dir',lambda:tmp_path)
 monkeypatch.setattr(settings,'settings_path',lambda:tmp_path/'settings.json')
 settings.save_settings({'data_directory':str(tmp_path/'data'),'reports_directory':str(tmp_path/'reports')})
 initialize_database()

def test_signed_sync_roundtrip(tmp_path,monkeypatch):
 setup_db(tmp_path,monkeypatch);key=generate_sync_key();assert len(key)==64 and len(fingerprint(key))==16
 queue_change('batches',7,'UPSERT',{'status':'Finished'});assert queue_summary()['Pending']==1
 out=tmp_path/'site.vqcsync';result=create_sync_package(out,key,'SITE-A',False)
 assert out.exists() and result['items']==1 and queue_summary()['Exported']==1
 assert validate_sync_package(out,key)['valid'] is True
 imported=import_sync_package(out,key);assert imported['applied']==1
 imported2=import_sync_package(out,key);assert imported2['applied']==0
 assert len(list_packages())==3

def test_invalid_key_rejected(tmp_path,monkeypatch):
 setup_db(tmp_path,monkeypatch);key=generate_sync_key();queue_change('batches',1);out=tmp_path/'x.vqcsync';create_sync_package(out,key,'A',False)
 assert validate_sync_package(out,'x'*32)['valid'] is False
 try: import_sync_package(out,'x'*32); assert False
 except ValueError: pass
