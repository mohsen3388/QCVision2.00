from pathlib import Path
import tempfile
from visionqc.domain.events import DomainEvent
from visionqc.domain.industrial_automation import ActionKind,ExecutionStatus
from visionqc.application.services.industrial_automation_service import IndustrialAutomationService
from visionqc.infrastructure.persistence.sqlite_automation import SqliteIndustrialAutomationRepository
from visionqc.infrastructure.persistence.sqlite_audit import SqliteAuditTrailRepository
from visionqc.platform.event_bus import InProcessEventBus


def _service(monkeypatch):
    import visionqc.core.database as db
    tmp=tempfile.TemporaryDirectory(); path=Path(tmp.name)/"test.sqlite3"
    monkeypatch.setattr(db,"database_path",lambda:path)
    repo=SqliteIndustrialAutomationRepository(); audit=SqliteAuditTrailRepository(); bus=InProcessEventBus()
    return tmp,IndustrialAutomationService(repo,audit,bus)

def test_rule_requires_human_approval(monkeypatch):
    tmp,svc=_service(monkeypatch)
    try:
        rule=svc.create_rule("High-risk QC review","predictive_quality.early_warning",ActionKind.CREATE_TASK,action_config={"title":"Review risk"},requires_approval=True)
        out=svc.handle_event(DomainEvent("predictive_quality.early_warning",{"risk":"High"}))
        assert out[0].status is ExecutionStatus.PENDING_APPROVAL
        assert svc.list_tasks()==[]
        svc.approve(out[0].execution_id)
        assert len(svc.list_tasks())==1
    finally: tmp.cleanup()

def test_non_matching_condition_is_skipped(monkeypatch):
    tmp,svc=_service(monkeypatch)
    try:
        svc.create_rule("Critical only","predictive_quality.early_warning",ActionKind.RECORD_ALERT,conditions={"score":{"gte":80}},requires_approval=False)
        assert svc.handle_event(DomainEvent("predictive_quality.early_warning",{"score":50}))==[]
    finally: tmp.cleanup()

def test_unsafe_event_is_rejected(monkeypatch):
    tmp,svc=_service(monkeypatch)
    try:
        try: svc.create_rule("PLC write","plc.write",ActionKind.RECORD_ALERT)
        except ValueError: pass
        else: raise AssertionError("unsafe event accepted")
    finally: tmp.cleanup()

def test_automatic_task_creation_when_explicitly_approved_by_rule_design(monkeypatch):
    tmp,svc=_service(monkeypatch)
    try:
        svc.create_rule("Create QC task","factory_engineer.escalation_recommended",ActionKind.CREATE_TASK,requires_approval=False,action_config={"title":"Escalation review","owner_role":"QC"})
        out=svc.handle_event(DomainEvent("factory_engineer.escalation_recommended",{"priority":"Urgent"}))
        assert out[0].status is ExecutionStatus.COMPLETED
        assert svc.list_tasks()[0]["owner_role"]=="QC"
    finally: tmp.cleanup()
