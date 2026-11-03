from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from visionqc.domain.events import DomainEvent
from visionqc.domain.industrial_automation import AutomationRule,AutomationExecution,AutomationTask,ActionKind,ExecutionStatus

class IndustrialAutomationService:
    """Fail-safe orchestration. It never writes to PLCs or changes recipes/settings."""
    SAFE_EVENTS={"predictive_quality.early_warning","factory_engineer.escalation_recommended","root_cause.analysis_completed","release_candidate.assessment_completed"}
    def __init__(self,repository,audit,event_bus=None,enterprise_integration=None):
        self.repository=repository; self.audit=audit; self.event_bus=event_bus; self.enterprise=enterprise_integration
        repository.initialize()
        if event_bus is not None: event_bus.subscribe("*",self.handle_event)
    def create_rule(self,name,event_name,action_kind,*,conditions=None,action_config=None,requires_approval=True,enabled=True):
        if event_name not in self.SAFE_EVENTS: raise ValueError("Unsupported automation event")
        kind=action_kind if isinstance(action_kind,ActionKind) else ActionKind(action_kind)
        rule=AutomationRule(name=name,event_name=event_name,action_kind=kind,conditions=conditions or {},action_config=action_config or {},requires_approval=requires_approval,enabled=enabled)
        self.repository.save_rule(rule); self.audit.append("automation.rule_created",entity_type="automation_rule",entity_id=rule.rule_id,details={"event":event_name,"action":kind.value}); return rule
    def list_rules(self): return self.repository.list_rules()
    def list_executions(self,limit=100): return self.repository.list_executions(limit)
    def list_tasks(self,limit=100): return self.repository.list_tasks(limit)
    def set_enabled(self,rule_id,enabled): self.repository.set_rule_enabled(rule_id,enabled); self.audit.append("automation.rule_state_changed",entity_type="automation_rule",entity_id=rule_id,details={"enabled":enabled})
    def handle_event(self,event:DomainEvent):
        if event.name not in self.SAFE_EVENTS: return []
        results=[]
        for rule in self.repository.list_rules():
            if not rule.enabled or rule.event_name!=event.name or not self._matches(rule.conditions,event.payload): continue
            results.append(self._execute(rule,event))
        return results
    def simulate(self,rule_id:str,payload:dict[str,Any]|None=None):
        rule=next((r for r in self.list_rules() if r.rule_id==rule_id),None)
        if rule is None: raise KeyError(rule_id)
        return self._execute(rule,DomainEvent(name=rule.event_name,payload=payload or {"simulation":True},source="automation.simulation"))
    def approve(self,execution_id:str,actor:str="Supervisor"):
        row=next((x for x in self.list_executions(500) if x["execution_id"]==execution_id),None)
        if row is None: raise KeyError(execution_id)
        if row["status"]!=ExecutionStatus.PENDING_APPROVAL.value: return row
        rule=next(r for r in self.list_rules() if r.rule_id==row["rule_id"])
        import json; payload=json.loads(row["payload_json"])
        e=AutomationExecution(execution_id=execution_id,rule_id=rule.rule_id,event_name=rule.event_name,action_kind=rule.action_kind,status=ExecutionStatus.COMPLETED,payload=payload,message=self._perform(rule,payload),created_at=row["created_at"],completed_at=datetime.now(timezone.utc).isoformat())
        self.repository.append_execution(e); self.audit.append("automation.execution_approved",actor=actor,entity_type="automation_execution",entity_id=execution_id); return e
    def _matches(self,conditions,payload):
        for key,expected in conditions.items():
            actual=payload.get(key)
            if isinstance(expected,dict):
                if "gte" in expected and (actual is None or float(actual)<float(expected["gte"])): return False
                if "eq" in expected and actual!=expected["eq"]: return False
            elif actual!=expected:return False
        return True
    def _execute(self,rule,event):
        if rule.requires_approval:
            e=AutomationExecution(rule_id=rule.rule_id,event_name=event.name,action_kind=rule.action_kind,status=ExecutionStatus.PENDING_APPROVAL,payload=event.payload,message="Human approval required before action")
        else:
            try: e=AutomationExecution(rule_id=rule.rule_id,event_name=event.name,action_kind=rule.action_kind,status=ExecutionStatus.COMPLETED,payload=event.payload,message=self._perform(rule,event.payload),completed_at=datetime.now(timezone.utc).isoformat())
            except Exception as exc: e=AutomationExecution(rule_id=rule.rule_id,event_name=event.name,action_kind=rule.action_kind,status=ExecutionStatus.FAILED,payload=event.payload,message=str(exc),completed_at=datetime.now(timezone.utc).isoformat())
        self.repository.append_execution(e); self.audit.append("automation.execution_created",entity_type="automation_execution",entity_id=e.execution_id,outcome=e.status.value,details={"rule_id":rule.rule_id,"event":event.name}); return e
    def _perform(self,rule,payload):
        if rule.action_kind is ActionKind.CREATE_TASK:
            cfg=rule.action_config; task=AutomationTask(title=cfg.get("title",f"Review {rule.event_name}"),owner_role=cfg.get("owner_role","QC"),priority=cfg.get("priority","High"),source_event=rule.event_name,details=payload); self.repository.create_task(task); return f"Task {task.task_id} created"
        if rule.action_kind is ActionKind.RECORD_ALERT: return "Operational alert recorded"
        if rule.action_kind is ActionKind.DELIVER_WEBHOOK:
            if self.enterprise is None: raise RuntimeError("Enterprise Integration is unavailable")
            status=self.enterprise.deliver_webhook(rule.event_name,payload); return f"Webhook delivered ({status})"
        if rule.action_kind is ActionKind.REQUEST_APPROVAL: return "Approval request recorded"
        raise ValueError("Unsupported action")
