from visionqc.application.services.factory_memory_service import FactoryMemoryService
from visionqc.application.services.root_cause_service import RootCauseIntelligenceService
from visionqc.application.services.voice_assistant_service import VoiceAssistantService
from visionqc.core import database
from visionqc.domain.factory_memory import CorrectiveAction, DefectObservation, FactoryMemoryCase, ProductionContext, ProcessSnapshot
from visionqc.infrastructure.persistence.sqlite_factory_memory import SqliteFactoryMemoryRepository
from visionqc.infrastructure.persistence.sqlite_voice import SqliteVoiceConversationRepository
from visionqc.platform.event_bus import InProcessEventBus


def build(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "database_path", lambda: tmp_path / "rca.db"); database.initialize_database()
    bus=InProcessEventBus(); memory=FactoryMemoryService(SqliteFactoryMemoryRepository(),bus)
    rca=RootCauseIntelligenceService(memory,bus)
    return bus,memory,rca


def test_rca_ranks_verified_similar_cause(tmp_path, monkeypatch):
    bus,memory,rca=build(tmp_path,monkeypatch)
    for i in range(2):
        hist=FactoryMemoryCase(product_name="Sausage",passed=False,production=ProductionContext(machine_name="Cutter-1",production_line="Line-A",recipe_name="R1"),process=ProcessSnapshot(dough_temperature_c=9.0),defects=[DefectObservation("casing tear",severity="Reject")],confirmed_cause="Worn cutter blade",qc_approved=True,corrective_actions=[CorrectiveAction("Maintenance","Replace cutter blade",status="Verified",result="Reject normalized")])
        memory.capture(hist)
    current=FactoryMemoryCase(product_name="Sausage",passed=False,production=ProductionContext(machine_name="Cutter-1",production_line="Line-A",recipe_name="R1"),process=ProcessSnapshot(dough_temperature_c=9.3),defects=[DefectObservation("casing tear",severity="Reject")])
    cid=memory.capture(current)
    result=rca.analyze(cid)
    assert result.top_hypothesis is not None
    target = next(h for h in result.hypotheses if h.cause == "Worn cutter blade")
    assert target.verified_case_count == 2
    assert "Replace cutter blade" in target.recommended_actions
    assert memory.get(cid).metadata["root_cause_analysis"]["method"]


def test_rca_voice_integration(tmp_path, monkeypatch):
    bus,memory,rca=build(tmp_path,monkeypatch)
    memory.capture(FactoryMemoryCase(product_name="Sausage",passed=False,production=ProductionContext(machine_name="Cutter-1"),defects=[DefectObservation("casing tear")],confirmed_cause="Worn cutter",qc_approved=True,corrective_actions=[CorrectiveAction("Maintenance","Inspect blade",status="Verified",result="Effective")]))
    cid=memory.capture(FactoryMemoryCase(product_name="Sausage",passed=False,production=ProductionContext(machine_name="Cutter-1"),defects=[DefectObservation("casing tear")]))
    voice=VoiceAssistantService(memory,SqliteVoiceConversationRepository(),bus,root_cause_service=rca)
    conv,_=voice.new_conversation(selected_case_id=cid)
    answer=voice.ask(conv,"Why is this defect happening?")
    assert "فرضیه اصلی" in answer.text
    assert "علت قطعی محسوب نمی‌شود" in answer.text
