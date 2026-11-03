from pathlib import Path

from visionqc.application.services.voice_assistant_service import VoiceAssistantService
from visionqc.core.database import initialize_database
from visionqc.domain.factory_memory import CorrectiveAction, DefectObservation, FactoryMemoryCase, ProductionContext
from visionqc.infrastructure.persistence.sqlite_factory_memory import SqliteFactoryMemoryRepository
from visionqc.infrastructure.persistence.sqlite_voice import SqliteVoiceConversationRepository
from visionqc.platform.event_bus import InProcessEventBus
from visionqc.application.services.factory_memory_service import FactoryMemoryService


def test_voice_ai_persists_and_grounds_answers(tmp_path, monkeypatch):
    monkeypatch.setenv("VISIONQC_DATA_DIR", str(tmp_path))
    initialize_database()
    bus=InProcessEventBus(); memory=FactoryMemoryService(SqliteFactoryMemoryRepository(),bus)
    historical=FactoryMemoryCase(product_name="Sausage",passed=False,production=ProductionContext(machine_name="Cutter-1",production_line="Line-A"),defects=[DefectObservation("casing tear")],confirmed_cause="Worn cutter",qc_approved=True,corrective_actions=[CorrectiveAction("Maintenance","Replace cutter blade",status="Verified",result="Reject returned to normal")])
    memory.capture(historical)
    current=FactoryMemoryCase(product_name="Sausage",passed=False,production=ProductionContext(machine_name="Cutter-1",production_line="Line-A"),defects=[DefectObservation("casing tear")])
    current_id=memory.capture(current)
    repo=SqliteVoiceConversationRepository(); service=VoiceAssistantService(memory,repo,bus)
    cid,_=service.new_conversation(selected_case_id=current_id)
    similar=service.ask(cid,"Find similar cases")
    assert "similarity" in similar.text.lower()
    action=service.ask(cid,"What should I check first?")
    assert "Replace cutter blade" in action.text
    stored=repo.get(cid)
    assert stored is not None and len(stored.messages)==4


def test_voice_ai_requires_selected_case(tmp_path, monkeypatch):
    monkeypatch.setenv("VISIONQC_DATA_DIR", str(tmp_path))
    initialize_database(); bus=InProcessEventBus(); memory=FactoryMemoryService(SqliteFactoryMemoryRepository(),bus)
    service=VoiceAssistantService(memory,SqliteVoiceConversationRepository(),bus)
    cid,_=service.new_conversation()
    response=service.ask(cid,"Summarize this case")
    assert "ابتدا یک پرونده" in response.text
