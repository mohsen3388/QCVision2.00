from __future__ import annotations
import json
from datetime import datetime, timezone
from visionqc.core.database import connect
from .models import InspectionTemplate

SCHEMA="""
CREATE TABLE IF NOT EXISTS vqc3_templates(
 id INTEGER PRIMARY KEY AUTOINCREMENT,key TEXT NOT NULL UNIQUE,name_fa TEXT NOT NULL,version TEXT NOT NULL,
 lifecycle TEXT NOT NULL,process_stage TEXT,template_json TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS vqc3_assignments(
 id INTEGER PRIMARY KEY AUTOINCREMENT,camera_name TEXT NOT NULL,template_key TEXT NOT NULL,override_json TEXT NOT NULL DEFAULT '{}',enabled INTEGER NOT NULL DEFAULT 1,UNIQUE(camera_name,template_key));
CREATE TABLE IF NOT EXISTS vqc3_validation_runs(
 id INTEGER PRIMARY KEY AUTOINCREMENT,template_key TEXT NOT NULL,source_path TEXT,mode TEXT NOT NULL,result_json TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS vqc3_config_audit(
 id INTEGER PRIMARY KEY AUTOINCREMENT,entity_type TEXT NOT NULL,entity_key TEXT NOT NULL,operation TEXT NOT NULL,details_json TEXT NOT NULL,created_at TEXT NOT NULL);
"""

def now(): return datetime.now(timezone.utc).isoformat()
class ConfigurationRepository:
    def __init__(self):
        with connect() as c: c.executescript(SCHEMA)
    def save_template(self,t:InspectionTemplate,operation="save") -> None:
        ts=now()
        with connect() as c:
            c.execute("""INSERT INTO vqc3_templates(key,name_fa,version,lifecycle,process_stage,template_json,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET name_fa=excluded.name_fa,version=excluded.version,lifecycle=excluded.lifecycle,process_stage=excluded.process_stage,template_json=excluded.template_json,updated_at=excluded.updated_at""",
            (t.key,t.name_fa,t.version,t.lifecycle,t.process_stage,t.to_json(),ts,ts))
            c.execute("INSERT INTO vqc3_config_audit(entity_type,entity_key,operation,details_json,created_at) VALUES(?,?,?,?,?)",("template",t.key,operation,"{}",ts))
    def list_templates(self)->list[InspectionTemplate]:
        with connect() as c: rows=c.execute("SELECT template_json FROM vqc3_templates ORDER BY name_fa").fetchall()
        return [InspectionTemplate.from_dict(json.loads(r[0])) for r in rows]
    def get_template(self,key:str)->InspectionTemplate|None:
        with connect() as c: row=c.execute("SELECT template_json FROM vqc3_templates WHERE key=?",(key,)).fetchone()
        return None if not row else InspectionTemplate.from_dict(json.loads(row[0]))
    def delete_template(self,key:str)->None:
        with connect() as c: c.execute("DELETE FROM vqc3_templates WHERE key=?",(key,))
    def record_validation(self,key,path,mode,result):
        with connect() as c: c.execute("INSERT INTO vqc3_validation_runs(template_key,source_path,mode,result_json,created_at) VALUES(?,?,?,?,?)",(key,path,mode,json.dumps(result,ensure_ascii=False),now()))
