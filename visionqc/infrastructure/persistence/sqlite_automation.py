from __future__ import annotations
import json
from visionqc.core.database import connect
from visionqc.domain.industrial_automation import AutomationRule, AutomationExecution, AutomationTask, ActionKind, ExecutionStatus

class SqliteIndustrialAutomationRepository:
    def initialize(self) -> None:
        with connect() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS industrial_automation_rules(
              rule_id TEXT PRIMARY KEY,name TEXT NOT NULL,event_name TEXT NOT NULL,action_kind TEXT NOT NULL,
              action_config_json TEXT NOT NULL,conditions_json TEXT NOT NULL,requires_approval INTEGER NOT NULL,
              enabled INTEGER NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS industrial_automation_executions(
              execution_id TEXT PRIMARY KEY,rule_id TEXT NOT NULL,event_name TEXT NOT NULL,action_kind TEXT NOT NULL,
              status TEXT NOT NULL,payload_json TEXT NOT NULL,message TEXT NOT NULL,created_at TEXT NOT NULL,completed_at TEXT);
            CREATE TABLE IF NOT EXISTS industrial_automation_tasks(
              task_id TEXT PRIMARY KEY,title TEXT NOT NULL,owner_role TEXT NOT NULL,priority TEXT NOT NULL,
              source_event TEXT NOT NULL,details_json TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_automation_rules_event ON industrial_automation_rules(event_name,enabled);
            CREATE INDEX IF NOT EXISTS idx_automation_execution_created ON industrial_automation_executions(created_at);
            """)
    def save_rule(self, rule: AutomationRule) -> None:
        self.initialize()
        with connect() as conn:
            conn.execute("""INSERT OR REPLACE INTO industrial_automation_rules VALUES(?,?,?,?,?,?,?,?,?)""",
              (rule.rule_id,rule.name,rule.event_name,rule.action_kind.value,json.dumps(rule.action_config),json.dumps(rule.conditions),int(rule.requires_approval),int(rule.enabled),rule.created_at))
    def list_rules(self) -> list[AutomationRule]:
        self.initialize()
        with connect() as conn: rows=conn.execute("SELECT * FROM industrial_automation_rules ORDER BY created_at DESC").fetchall()
        return [AutomationRule(rule_id=r[0],name=r[1],event_name=r[2],action_kind=ActionKind(r[3]),action_config=json.loads(r[4]),conditions=json.loads(r[5]),requires_approval=bool(r[6]),enabled=bool(r[7]),created_at=r[8]) for r in rows]
    def set_rule_enabled(self,rule_id:str,enabled:bool)->None:
        with connect() as conn: conn.execute("UPDATE industrial_automation_rules SET enabled=? WHERE rule_id=?",(int(enabled),rule_id))
    def append_execution(self,e:AutomationExecution)->None:
        self.initialize()
        with connect() as conn: conn.execute("INSERT OR REPLACE INTO industrial_automation_executions VALUES(?,?,?,?,?,?,?,?,?)",(e.execution_id,e.rule_id,e.event_name,e.action_kind.value,e.status.value,json.dumps(e.payload,default=str),e.message,e.created_at,e.completed_at))
    def list_executions(self,limit:int=100)->list[dict]:
        self.initialize()
        with connect() as conn:
            cur=conn.execute("SELECT * FROM industrial_automation_executions ORDER BY created_at DESC LIMIT ?",(limit,)); cols=[c[0] for c in cur.description]; rows=cur.fetchall()
        return [dict(zip(cols,r)) for r in rows]
    def create_task(self,t:AutomationTask)->None:
        self.initialize()
        with connect() as conn: conn.execute("INSERT INTO industrial_automation_tasks VALUES(?,?,?,?,?,?,?,?)",(t.task_id,t.title,t.owner_role,t.priority,t.source_event,json.dumps(t.details,default=str),t.status,t.created_at))
    def list_tasks(self,limit:int=100)->list[dict]:
        self.initialize()
        with connect() as conn:
            cur=conn.execute("SELECT * FROM industrial_automation_tasks ORDER BY created_at DESC LIMIT ?",(limit,)); cols=[c[0] for c in cur.description]; rows=cur.fetchall()
        return [dict(zip(cols,r)) for r in rows]
