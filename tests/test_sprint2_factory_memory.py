from __future__ import annotations

from pathlib import Path

import pytest

from visionqc.application.services.factory_memory_service import FactoryMemoryService
from visionqc.core import database
from visionqc.domain.factory_memory import (
    CorrectiveAction, DefectObservation, EvidenceReference, FactoryMemoryCase,
    MemoryStatus, ProcessSnapshot, ProductionContext,
)
from visionqc.infrastructure.persistence.sqlite_factory_memory import SqliteFactoryMemoryRepository
from visionqc.platform.event_bus import InProcessEventBus


@pytest.fixture()
def memory_env(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "database_path", lambda: tmp_path / "memory.db")
    database.initialize_database()
    bus = InProcessEventBus()
    events = []
    bus.subscribe("*", events.append)
    service = FactoryMemoryService(SqliteFactoryMemoryRepository(), bus)
    return service, events


def sample_case(*, machine="Stuffer-2", temp=8.2, defect="Casing tear"):
    return FactoryMemoryCase(
        product_name="Chicken Hot Dog",
        passed=False,
        production=ProductionContext(
            batch_code="B-1405-001", production_line="Line 2", shift_name="Night",
            operator_name="Operator A", machine_name=machine, recipe_name="RCP-12",
            supplier_name="Casing Supplier A", process_stage="Stuffing",
        ),
        process=ProcessSnapshot(dough_temperature_c=temp, line_speed=118, vacuum_bar=-0.82),
        defects=[DefectObservation(defect, severity="Reject", confidence=.93, measurement=3.2, unit="mm")],
        evidence=[EvidenceReference("sample.jpg", caption="Rejected product")],
        suspected_causes=["Dull blade", "Low vacuum"],
        measurements={"tear_length_mm": 3.2},
    )


def test_capture_round_trip_and_event(memory_env):
    service, events = memory_env
    case_id = service.capture(sample_case())
    loaded = service.get(case_id)
    assert loaded is not None
    assert loaded.production.machine_name == "Stuffer-2"
    assert loaded.process.dough_temperature_c == 8.2
    assert loaded.defects[0].defect_type == "Casing tear"
    assert events[-1].name == "factory_memory.case_captured"


def test_corrective_action_and_qc_verification(memory_env):
    service, events = memory_env
    case_id = service.capture(sample_case())
    service.add_corrective_action(case_id, CorrectiveAction("Maintenance", "Replace blade #2", owner="Maintenance Team"))
    verified = service.confirm_root_cause(case_id, "Dull blade #2", qc_user="QC Manager", notes="Confirmed after replacement")
    assert verified.status is MemoryStatus.VERIFIED
    assert verified.qc_approved is True
    assert verified.corrective_actions[0].description == "Replace blade #2"
    assert events[-1].name == "factory_memory.case_verified"


def test_similarity_finds_same_failure_pattern(memory_env):
    service, _ = memory_env
    service.capture(sample_case(temp=8.1))
    service.capture(sample_case(machine="Stuffer-5", temp=16.0, defect="Color deviation"))
    query = sample_case(temp=8.4)
    matches = service.find_similar(query, limit=2)
    assert matches
    assert matches[0].case.production.machine_name == "Stuffer-2"
    assert matches[0].similarity > .7
    assert any("matching defects" in signal for signal in matches[0].matching_signals)


def test_rejects_invalid_confidence(memory_env):
    service, _ = memory_env
    case = sample_case()
    case.defects[0].confidence = 1.5
    with pytest.raises(ValueError):
        service.capture(case)
