
from __future__ import annotations
import json
from datetime import datetime, timezone
from visionqc.core.database import connect

SCHEMA = """
CREATE TABLE IF NOT EXISTS vqc3_runtime_assignments(
 camera_id TEXT PRIMARY KEY, camera_name TEXT NOT NULL, source_type TEXT NOT NULL, source_value TEXT,
 template_key TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, sampling_seconds REAL NOT NULL DEFAULT 2,
 overrides_json TEXT NOT NULL DEFAULT '{}', updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS vqc3_metric_samples(
 id INTEGER PRIMARY KEY AUTOINCREMENT, camera_id TEXT NOT NULL, template_key TEXT NOT NULL,
 metric_key TEXT NOT NULL, raw_value REAL, score REAL, sample_status TEXT NOT NULL,
 captured_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_vqc3_samples_camera_metric_time ON vqc3_metric_samples(camera_id,metric_key,captured_at);
CREATE TABLE IF NOT EXISTS vqc3_runtime_events(
 id INTEGER PRIMARY KEY AUTOINCREMENT, event_key TEXT NOT NULL UNIQUE, camera_id TEXT NOT NULL,
 template_key TEXT NOT NULL, trigger_key TEXT NOT NULL, severity TEXT NOT NULL, state TEXT NOT NULL,
 problem_text TEXT, opened_at TEXT NOT NULL, acknowledged_at TEXT, resolved_at TEXT,
 acknowledged_by TEXT, evidence_json TEXT NOT NULL DEFAULT '{}');
CREATE INDEX IF NOT EXISTS idx_vqc3_events_camera_state ON vqc3_runtime_events(camera_id,state);

CREATE TABLE IF NOT EXISTS vqc4_camera_health(
 camera_id TEXT PRIMARY KEY, state TEXT NOT NULL, message TEXT, source_type TEXT, backend TEXT,
 width INTEGER NOT NULL DEFAULT 0, height INTEGER NOT NULL DEFAULT 0, source_fps REAL NOT NULL DEFAULT 0,
 measured_fps REAL NOT NULL DEFAULT 0, last_frame_at TEXT, last_success_at TEXT, last_error_at TEXT,
 reconnect_count INTEGER NOT NULL DEFAULT 0, consecutive_failures INTEGER NOT NULL DEFAULT 0,
 frames_received INTEGER NOT NULL DEFAULT 0, frames_analyzed INTEGER NOT NULL DEFAULT 0,
 dropped_frames INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_vqc4_camera_health_state ON vqc4_camera_health(state,updated_at);
CREATE TABLE IF NOT EXISTS vqc3_action_executions(
 id INTEGER PRIMARY KEY AUTOINCREMENT,event_key TEXT NOT NULL,action_key TEXT NOT NULL,step_order INTEGER NOT NULL,
 action_type TEXT NOT NULL,target TEXT,message TEXT,status TEXT NOT NULL,details_json TEXT NOT NULL DEFAULT '{}',executed_at TEXT NOT NULL);
"""
def now(): return datetime.now(timezone.utc).isoformat()

class RuntimeRepository:
    def __init__(self):
        with connect() as c: c.executescript(SCHEMA)
    def assign(self,camera_id,camera_name,source_type,source_value,template_key,sampling_seconds=2.0,enabled=True,overrides=None):
        with connect() as c: c.execute("""INSERT INTO vqc3_runtime_assignments(camera_id,camera_name,source_type,source_value,template_key,enabled,sampling_seconds,overrides_json,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(camera_id) DO UPDATE SET camera_name=excluded.camera_name,source_type=excluded.source_type,source_value=excluded.source_value,template_key=excluded.template_key,enabled=excluded.enabled,sampling_seconds=excluded.sampling_seconds,overrides_json=excluded.overrides_json,updated_at=excluded.updated_at""",
        (camera_id,camera_name,source_type,source_value,template_key,1 if enabled else 0,float(sampling_seconds),json.dumps(overrides or {},ensure_ascii=False),now()))
    def unassign(self,camera_id):
        with connect() as c: c.execute('DELETE FROM vqc3_runtime_assignments WHERE camera_id=?',(camera_id,))
    def assignments(self):
        with connect() as c: rows=c.execute('SELECT camera_id,camera_name,source_type,source_value,template_key,enabled,sampling_seconds,overrides_json,updated_at FROM vqc3_runtime_assignments ORDER BY camera_name').fetchall()
        return [dict(camera_id=r[0],camera_name=r[1],source_type=r[2],source_value=r[3] or '',template_key=r[4],enabled=bool(r[5]),sampling_seconds=r[6],overrides=json.loads(r[7] or '{}'),updated_at=r[8]) for r in rows]
    def assignment(self,camera_id): return next((x for x in self.assignments() if x['camera_id']==camera_id),None)
    def add_samples(self,camera_id,template_key,metrics,captured_at=None):
        ts=captured_at or now()
        with connect() as c:
            c.executemany('INSERT INTO vqc3_metric_samples(camera_id,template_key,metric_key,raw_value,score,sample_status,captured_at) VALUES(?,?,?,?,?,?,?)',[(camera_id,template_key,m['key'],m.get('raw'),m.get('score'),m.get('status','OK'),ts) for m in metrics])
    def metric_history(self,camera_id,metric_key,limit=300):
        with connect() as c: rows=c.execute('SELECT score,captured_at FROM vqc3_metric_samples WHERE camera_id=? AND metric_key=? ORDER BY id DESC LIMIT ?',(camera_id,metric_key,int(limit))).fetchall()
        return list(reversed([(r[1],float(r[0])) for r in rows if r[0] is not None]))
    def open_event(self,event_key,camera_id,template_key,trigger,evidence):
        with connect() as c: c.execute("""INSERT OR IGNORE INTO vqc3_runtime_events(event_key,camera_id,template_key,trigger_key,severity,state,problem_text,opened_at,evidence_json) VALUES(?,?,?,?,?,'OPEN',?,?,?)""",(event_key,camera_id,template_key,trigger.key,trigger.severity,trigger.problem_text or trigger.name_fa,now(),json.dumps(evidence,ensure_ascii=False)))
    def resolve_event(self,event_key):
        with connect() as c: c.execute("UPDATE vqc3_runtime_events SET state='RESOLVED',resolved_at=? WHERE event_key=? AND state!='RESOLVED'",(now(),event_key))
    def acknowledge(self,event_key,user):
        with connect() as c: c.execute("UPDATE vqc3_runtime_events SET state='ACKNOWLEDGED',acknowledged_at=?,acknowledged_by=? WHERE event_key=? AND state='OPEN'",(now(),user,event_key))
    def active_event(self,camera_id,trigger_key):
        with connect() as c: r=c.execute("SELECT event_key FROM vqc3_runtime_events WHERE camera_id=? AND trigger_key=? AND state IN ('OPEN','ACKNOWLEDGED') ORDER BY id DESC LIMIT 1",(camera_id,trigger_key)).fetchone()
        return None if not r else r[0]
    def events(self,limit=300):
        with connect() as c: rows=c.execute('SELECT event_key,camera_id,template_key,trigger_key,severity,state,problem_text,opened_at,acknowledged_by,resolved_at FROM vqc3_runtime_events ORDER BY id DESC LIMIT ?',(int(limit),)).fetchall()
        keys=['event_key','camera_id','template_key','trigger_key','severity','state','problem_text','opened_at','acknowledged_by','resolved_at']
        return [dict(zip(keys,r)) for r in rows]
    def update_camera_health(self, camera_id, health):
        data = health.to_dict() if hasattr(health, 'to_dict') else dict(health)
        fields = dict(
            camera_id=camera_id, state=data.get('state','UNKNOWN'), message=data.get('message',''),
            source_type=data.get('source_type',''), backend=data.get('backend',''),
            width=int(data.get('width') or 0), height=int(data.get('height') or 0),
            source_fps=float(data.get('source_fps') or 0), measured_fps=float(data.get('measured_fps') or 0),
            last_frame_at=data.get('last_frame_at'), last_success_at=data.get('last_success_at'),
            last_error_at=data.get('last_error_at'), reconnect_count=int(data.get('reconnect_count') or 0),
            consecutive_failures=int(data.get('consecutive_failures') or 0), frames_received=int(data.get('frames_received') or 0),
            frames_analyzed=int(data.get('frames_analyzed') or 0), dropped_frames=int(data.get('dropped_frames') or 0),
            updated_at=data.get('updated_at') or now())
        with connect() as c:
            c.execute("""INSERT INTO vqc4_camera_health(camera_id,state,message,source_type,backend,width,height,source_fps,measured_fps,last_frame_at,last_success_at,last_error_at,reconnect_count,consecutive_failures,frames_received,frames_analyzed,dropped_frames,updated_at)
            VALUES(:camera_id,:state,:message,:source_type,:backend,:width,:height,:source_fps,:measured_fps,:last_frame_at,:last_success_at,:last_error_at,:reconnect_count,:consecutive_failures,:frames_received,:frames_analyzed,:dropped_frames,:updated_at)
            ON CONFLICT(camera_id) DO UPDATE SET state=excluded.state,message=excluded.message,source_type=excluded.source_type,backend=excluded.backend,width=excluded.width,height=excluded.height,source_fps=excluded.source_fps,measured_fps=excluded.measured_fps,last_frame_at=excluded.last_frame_at,last_success_at=excluded.last_success_at,last_error_at=excluded.last_error_at,reconnect_count=excluded.reconnect_count,consecutive_failures=excluded.consecutive_failures,frames_received=excluded.frames_received,frames_analyzed=excluded.frames_analyzed,dropped_frames=excluded.dropped_frames,updated_at=excluded.updated_at""", fields)

    def camera_health(self, camera_id):
        with connect() as c:
            row=c.execute('SELECT camera_id,state,message,source_type,backend,width,height,source_fps,measured_fps,last_frame_at,last_success_at,last_error_at,reconnect_count,consecutive_failures,frames_received,frames_analyzed,dropped_frames,updated_at FROM vqc4_camera_health WHERE camera_id=?',(camera_id,)).fetchone()
        if not row:return None
        keys=['camera_id','state','message','source_type','backend','width','height','source_fps','measured_fps','last_frame_at','last_success_at','last_error_at','reconnect_count','consecutive_failures','frames_received','frames_analyzed','dropped_frames','updated_at']
        return dict(zip(keys,row))

    def camera_health_all(self):
        with connect() as c:
            rows=c.execute('SELECT camera_id,state,message,source_type,backend,width,height,source_fps,measured_fps,last_frame_at,last_success_at,last_error_at,reconnect_count,consecutive_failures,frames_received,frames_analyzed,dropped_frames,updated_at FROM vqc4_camera_health ORDER BY camera_id').fetchall()
        keys=['camera_id','state','message','source_type','backend','width','height','source_fps','measured_fps','last_frame_at','last_success_at','last_error_at','reconnect_count','consecutive_failures','frames_received','frames_analyzed','dropped_frames','updated_at']
        return [dict(zip(keys,row)) for row in rows]

    def log_action(self,event_key,action_key,step,status='DONE',details=None):
        with connect() as c: c.execute('INSERT INTO vqc3_action_executions(event_key,action_key,step_order,action_type,target,message,status,details_json,executed_at) VALUES(?,?,?,?,?,?,?,?,?)',(event_key,action_key,step.step_order,step.action_type,step.target,step.message,status,json.dumps(details or {},ensure_ascii=False),now()))
