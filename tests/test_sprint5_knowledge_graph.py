from pathlib import Path

from visionqc.application.services.factory_memory_service import FactoryMemoryService
from visionqc.application.services.knowledge_graph_service import KnowledgeGraphService
from visionqc.domain.factory_memory import CorrectiveAction, DefectObservation, FactoryMemoryCase, ProductionContext
from visionqc.domain.knowledge_graph import NodeType
from visionqc.infrastructure.persistence.sqlite_factory_memory import SqliteFactoryMemoryRepository
from visionqc.infrastructure.persistence.sqlite_knowledge_graph import SqliteKnowledgeGraphRepository
from visionqc.platform.event_bus import InProcessEventBus


def test_graph_rebuild_canonicalizes_and_links(monkeypatch, tmp_path: Path):
    monkeypatch.setattr('visionqc.core.database.database_path', lambda: tmp_path/'test.db')
    from visionqc.core.database import initialize_database
    initialize_database()
    bus=InProcessEventBus(); memory=FactoryMemoryService(SqliteFactoryMemoryRepository(),bus)
    for cause in ('Worn cutter','Worn cutter blade'):
        memory.capture(FactoryMemoryCase(product_name='Sausage',passed=False,qc_approved=True,confirmed_cause=cause,
            production=ProductionContext(machine_name='Cutter 1',production_line='Line A'),
            defects=[DefectObservation('Casing tear',severity='Reject',confidence=.94)],
            corrective_actions=[CorrectiveAction('maintenance','Replace cutter blade',status='Verified',result='Reject reduced',verified_by='QC')]))
    graph=KnowledgeGraphService(SqliteKnowledgeGraphRepository(),memory,bus)
    summary=graph.rebuild_from_factory_memory()
    assert summary.node_count >= 5 and summary.edge_count >= 4
    causes=graph.nodes(NodeType.CAUSE)
    assert len(causes)==1
    defects=graph.nodes(NodeType.DEFECT)
    paths=graph.find_paths(defects[0].node_id,NodeType.CAUSE,max_depth=2)
    assert paths and 'cutter' in paths[0].nodes[-1].canonical_name


def test_graph_finds_verified_action(monkeypatch, tmp_path: Path):
    monkeypatch.setattr('visionqc.core.database.database_path', lambda: tmp_path/'test2.db')
    from visionqc.core.database import initialize_database
    initialize_database(); bus=InProcessEventBus(); memory=FactoryMemoryService(SqliteFactoryMemoryRepository(),bus)
    memory.capture(FactoryMemoryCase(product_name='Hot dog',passed=False,qc_approved=True,confirmed_cause='Casing tension',
        defects=[DefectObservation('Casing tear',severity='Reject')], corrective_actions=[CorrectiveAction('adjustment','Adjust casing tension',result='Effective',verified_by='QC')]))
    graph=KnowledgeGraphService(SqliteKnowledgeGraphRepository(),memory,bus); graph.rebuild_from_factory_memory()
    cause=graph.nodes(NodeType.CAUSE)[0]
    paths=graph.find_paths(cause.node_id,NodeType.ACTION,max_depth=1)
    assert paths and paths[0].nodes[-1].node_type == NodeType.ACTION
