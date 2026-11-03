from pathlib import Path

from visionqc.multicamera.models import CameraDefinition, CameraRegistry
from visionqc.multicamera.factory_service import FactoryMonitoringService


class FakeRuntimeRepository:
    def __init__(self, events=None):
        self._events = list(events or [])
    def events(self):
        return list(self._events)


def test_factory_overview_aggregates_camera_health(tmp_path: Path):
    camera_path = tmp_path / "cameras.json"
    registry = CameraRegistry(camera_path)
    registry.save([
        CameraDefinition("c1", "دیگ ۱", "اختلاط", "Mixer 1", "mixing", health_score=92),
        CameraDefinition("c2", "دیگ ۲", "اختلاط", "Mixer 2", "mixing", health_score=68),
    ])
    runtime = FakeRuntimeRepository()
    service = FactoryMonitoringService(registry, runtime)
    overview = service.overview()
    assert overview.total_cameras == 2
    assert overview.enabled_cameras == 2
    assert overview.average_health == 80.0
    assert {item.status for item in overview.snapshots} == {"پایدار", "هشدار سطح بالا"}


def test_factory_overview_marks_open_high_event(tmp_path: Path):
    registry = CameraRegistry(tmp_path / "cameras.json")
    registry.save([CameraDefinition("c1", "دیگ ۱", "اختلاط", "Mixer 1", "mixing", health_score=95)])
    runtime = FakeRuntimeRepository([{
        "event_key": "evt1", "camera_id": "c1", "template_key": "tpl",
        "trigger_key": "texture.low", "severity": "HIGH", "state": "OPEN",
        "problem_text": "افت یکنواختی بافت", "opened_at": "2026-08-06T00:00:00Z",
    }])
    overview = FactoryMonitoringService(registry, runtime).overview()
    assert overview.active_events == 1
    assert overview.cameras_with_events == 1
    assert overview.critical_cameras == 1
    assert overview.snapshots[0].status == "هشدار سطح بالا"
