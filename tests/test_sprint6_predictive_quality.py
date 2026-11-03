from pathlib import Path

from visionqc.application.services.factory_memory_service import FactoryMemoryService
from visionqc.application.services.predictive_quality_service import PredictiveQualityService
from visionqc.domain.factory_memory import DefectObservation, FactoryMemoryCase, ProcessSnapshot, ProductionContext
from visionqc.domain.predictive_quality import RiskBand
from visionqc.infrastructure.persistence.sqlite_factory_memory import SqliteFactoryMemoryRepository
from visionqc.platform.event_bus import InProcessEventBus


def _setup(monkeypatch,tmp_path:Path):
    monkeypatch.setattr('visionqc.core.database.database_path',lambda:tmp_path/'pq.db')
    from visionqc.core.database import initialize_database
    initialize_database(); bus=InProcessEventBus(); memory=FactoryMemoryService(SqliteFactoryMemoryRepository(),bus)
    return bus,memory,PredictiveQualityService(memory,bus)


def test_predictive_quality_detects_rising_reject_risk(monkeypatch,tmp_path):
    bus,memory,service=_setup(monkeypatch,tmp_path)
    for i in range(30):
        memory.capture(FactoryMemoryCase(product_name='Sausage',passed=True,production=ProductionContext(production_line='A',machine_name='Filler 1'),process=ProcessSnapshot(pressure_bar=4.0+i*.005)))
    for i in range(8):
        memory.capture(FactoryMemoryCase(product_name='Sausage',passed=i<2,production=ProductionContext(production_line='A',machine_name='Filler 1'),process=ProcessSnapshot(pressure_bar=5.2),defects=[] if i<2 else [DefectObservation('Casing tear',severity='Reject')]))
    f=service.forecast(product_name='Sausage',line='A',machine='Filler 1',recent_window=8,baseline_window=30)
    assert f.risk_band in {RiskBand.HIGH,RiskBand.CRITICAL}
    assert f.predicted_reject_rate >= f.baseline_reject_rate
    assert any('Reject' in d.name or 'defect' in d.name.casefold() for d in f.drivers)


def test_predictive_quality_is_conservative_with_no_data(monkeypatch,tmp_path):
    bus,memory,service=_setup(monkeypatch,tmp_path)
    f=service.forecast(product_name='Unknown')
    assert f.risk_band == RiskBand.LOW
    assert f.sample_count == 0
    assert f.limitations
