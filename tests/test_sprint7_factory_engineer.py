from pathlib import Path

from visionqc.application.services.factory_engineer_service import AIFactoryEngineerService
from visionqc.application.services.factory_memory_service import FactoryMemoryService
from visionqc.application.services.knowledge_graph_service import KnowledgeGraphService
from visionqc.application.services.predictive_quality_service import PredictiveQualityService
from visionqc.application.services.root_cause_service import RootCauseIntelligenceService
from visionqc.domain.factory_engineer import OperationalPriority
from visionqc.domain.factory_memory import DefectObservation, FactoryMemoryCase, ProcessSnapshot, ProductionContext
from visionqc.infrastructure.persistence.sqlite_factory_memory import SqliteFactoryMemoryRepository
from visionqc.infrastructure.persistence.sqlite_knowledge_graph import SqliteKnowledgeGraphRepository
from visionqc.platform.event_bus import InProcessEventBus


def _setup(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("visionqc.core.database.database_path", lambda: tmp_path / "s7.db")
    from visionqc.core.database import initialize_database
    initialize_database()
    bus = InProcessEventBus()
    memory = FactoryMemoryService(SqliteFactoryMemoryRepository(), bus)
    graph = KnowledgeGraphService(SqliteKnowledgeGraphRepository(), memory, bus)
    root = RootCauseIntelligenceService(memory, bus, knowledge_graph=graph)
    predictive = PredictiveQualityService(memory, bus, knowledge_graph=graph)
    engineer = AIFactoryEngineerService(memory, predictive, root, graph, bus)
    return bus, memory, engineer


def test_factory_engineer_coordinates_high_risk_rejected_case(monkeypatch, tmp_path):
    bus, memory, engineer = _setup(monkeypatch, tmp_path)
    for i in range(30):
        memory.capture(FactoryMemoryCase(product_name="Sausage", passed=True,
            production=ProductionContext(production_line="A", machine_name="Filler 1"),
            process=ProcessSnapshot(pressure_bar=4.0 + i * .002)))
    case_id = None
    for _ in range(8):
        case_id = memory.capture(FactoryMemoryCase(product_name="Sausage", passed=False,
            production=ProductionContext(production_line="A", machine_name="Filler 1"),
            process=ProcessSnapshot(pressure_bar=5.4),
            defects=[DefectObservation("Casing tear", severity="Reject")]))
    briefing = engineer.generate_briefing(case_id=case_id)
    assert briefing.priority in {OperationalPriority.ATTENTION, OperationalPriority.HOLD_AND_VERIFY}
    assert briefing.actions
    assert briefing.decision_gates
    assert "Predictive Quality" in {a.source for a in briefing.actions}
    stored = memory.get(case_id)
    assert "factory_engineer_briefing" in stored.metadata


def test_factory_engineer_is_conservative_without_data(monkeypatch, tmp_path):
    bus, memory, engineer = _setup(monkeypatch, tmp_path)
    briefing = engineer.generate_briefing()
    assert briefing.priority == OperationalPriority.ROUTINE
    assert briefing.actions
    assert any("does not autonomously" in x for x in briefing.limitations)
