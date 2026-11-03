from __future__ import annotations
import hashlib, hmac, json, secrets, zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from visionqc.core.database import connect, utc_now

SYNC_TABLES=("batches","batch_events","process_events","quality_measurements","production_shifts","production_runs","downtime_events","metric_profiles","analysis_imports","knowledge_entries")

def _canon(obj:Any)->bytes:return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def generate_sync_key()->str:return secrets.token_hex(32)
def fingerprint(key:str)->str:return hashlib.sha256(key.encode()).hexdigest()[:16].upper()
def _sign(payload:dict,key:str)->str:return hmac.new(key.encode(),_canon(payload),hashlib.sha256).hexdigest()

def queue_change(entity_type:str,entity_id:int,operation:str="UPSERT",payload:dict|None=None)->int:
    with connect() as c:
        cur=c.execute("INSERT INTO sync_queue(entity_type,entity_id,operation,payload_json,status,created_at) VALUES(?,?,?,?,?,?)",(entity_type,int(entity_id),operation,json.dumps(payload or {},ensure_ascii=False),"Pending",utc_now()))
        return int(cur.lastrowid)

def queue_summary()->dict:
    with connect() as c:
        rows=c.execute("SELECT status,COUNT(*) n FROM sync_queue GROUP BY status").fetchall()
    out={"Pending":0,"Exported":0,"Applied":0,"Conflict":0};out.update({r['status']:r['n'] for r in rows});return out

def create_sync_package(path:str|Path,key:str,site_id:str,include_full_snapshot:bool=True)->dict:
    if len(key)<16:raise ValueError("Sync key must contain at least 16 characters.")
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    with connect() as c:
        queued=[dict(r) for r in c.execute("SELECT * FROM sync_queue WHERE status='Pending' ORDER BY id")]
        snapshot={}
        if include_full_snapshot:
            for t in SYNC_TABLES:snapshot[t]=[dict(r) for r in c.execute(f"SELECT * FROM {t}")]
    payload={"schema":1,"site_id":site_id.strip() or "LOCAL","created_at":utc_now(),"queue":queued,"snapshot":snapshot}
    manifest={"payload_sha256":hashlib.sha256(_canon(payload)).hexdigest(),"signature":_sign(payload,key),"key_fingerprint":fingerprint(key)}
    with zipfile.ZipFile(path,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr("payload.json",json.dumps(payload,ensure_ascii=False,indent=2));z.writestr("manifest.json",json.dumps(manifest,indent=2))
    with connect() as c:
        ids=[r['id'] for r in queued]
        if ids:c.executemany("UPDATE sync_queue SET status='Exported',exported_at=? WHERE id=?",[(utc_now(),i) for i in ids])
        c.execute("INSERT INTO sync_packages(direction,file_path,site_id,item_count,status,created_at) VALUES(?,?,?,?,?,?)",("Outbound",str(path),site_id,len(queued),"Created",utc_now()))
    return {"path":str(path),"items":len(queued),"fingerprint":manifest['key_fingerprint']}

def validate_sync_package(path:str|Path,key:str)->dict:
    with zipfile.ZipFile(path) as z:payload=json.loads(z.read("payload.json"));manifest=json.loads(z.read("manifest.json"))
    digest=hashlib.sha256(_canon(payload)).hexdigest(); valid=hmac.compare_digest(manifest.get("signature",""),_sign(payload,key)) and digest==manifest.get("payload_sha256")
    return {"valid":valid,"site_id":payload.get("site_id"),"created_at":payload.get("created_at"),"items":len(payload.get("queue",[])),"fingerprint":manifest.get("key_fingerprint")}

def import_sync_package(path:str|Path,key:str,apply_snapshot:bool=False)->dict:
    check=validate_sync_package(path,key)
    if not check['valid']:raise ValueError("Package signature or integrity validation failed.")
    with zipfile.ZipFile(path) as z:payload=json.loads(z.read("payload.json"))
    applied=conflicts=0
    with connect() as c:
        for q in payload.get('queue',[]):
            token=f"{payload.get('site_id')}:{q.get('id')}"
            exists=c.execute("SELECT 1 FROM sync_receipts WHERE remote_token=?",(token,)).fetchone()
            if exists:continue
            c.execute("INSERT INTO sync_receipts(remote_token,source_site,entity_type,entity_id,received_at) VALUES(?,?,?,?,?)",(token,payload.get('site_id'),q.get('entity_type'),q.get('entity_id'),utc_now()));applied+=1
        if apply_snapshot:
            for table,rows in payload.get('snapshot',{}).items():
                if table not in SYNC_TABLES:continue
                for row in rows:
                    cols=list(row); marks=','.join('?' for _ in cols)
                    try:c.execute(f"INSERT OR IGNORE INTO {table}({','.join(cols)}) VALUES({marks})",[row[x] for x in cols])
                    except Exception:conflicts+=1
        c.execute("INSERT INTO sync_packages(direction,file_path,site_id,item_count,status,created_at) VALUES(?,?,?,?,?,?)",("Inbound",str(path),payload.get('site_id'),applied,"Applied" if not conflicts else "Conflict",utc_now()))
    return {"applied":applied,"conflicts":conflicts,"site_id":payload.get('site_id')}

def list_packages(limit:int=100):
    with connect() as c:return [dict(r) for r in c.execute("SELECT * FROM sync_packages ORDER BY id DESC LIMIT ?",(limit,))]
