from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Iterable

from visionqc.multicamera.models import CameraDefinition, CameraRegistry
from visionqc.configuration.runtime_repository import RuntimeRepository


@dataclass(frozen=True)
class FactoryCameraSnapshot:
    camera_id: str
    camera_name: str
    area: str
    asset: str
    profile_key: str
    status: str
    health: float | None
    active_events: int
    highest_severity: str | None
    last_event: str


@dataclass(frozen=True)
class FactoryOverview:
    total_cameras: int
    enabled_cameras: int
    cameras_with_events: int
    active_events: int
    average_health: float | None
    critical_cameras: int
    snapshots: tuple[FactoryCameraSnapshot, ...] = field(default_factory=tuple)


_SEVERITY_RANK = {
    "INFO": 0,
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}


class FactoryMonitoringService:
    """Aggregates camera topology and runtime events for the factory dashboard."""

    def __init__(
        self,
        camera_registry: CameraRegistry | None = None,
        runtime_repository: RuntimeRepository | None = None,
    ) -> None:
        self.camera_registry = camera_registry or CameraRegistry()
        self.runtime_repository = runtime_repository or RuntimeRepository()

    def overview(self) -> FactoryOverview:
        cameras = self.camera_registry.list()
        events = self.runtime_repository.events()
        open_events = [e for e in events if str(e.get("state", "")).upper() != "RESOLVED"]
        by_camera: dict[str, list[dict]] = {}
        for event in open_events:
            by_camera.setdefault(str(event.get("camera_id", "")), []).append(event)

        snapshots: list[FactoryCameraSnapshot] = []
        health_values: list[float] = []
        for camera in cameras:
            camera_events = by_camera.get(camera.camera_id, [])
            severity = self._highest_severity(camera_events)
            health = camera.health_score
            if health is not None:
                health_values.append(float(health))
            status = self._status(camera, camera_events, severity)
            last_event = camera.last_event_fa
            if camera_events:
                latest = sorted(camera_events, key=lambda x: str(x.get("opened_at", "")), reverse=True)[0]
                last_event = str(latest.get("problem_text") or latest.get("trigger_key") or "رخداد فعال")
            snapshots.append(
                FactoryCameraSnapshot(
                    camera_id=camera.camera_id,
                    camera_name=camera.name_fa,
                    area=camera.area_fa,
                    asset=camera.asset_fa,
                    profile_key=camera.profile_key,
                    status=status,
                    health=health,
                    active_events=len(camera_events),
                    highest_severity=severity,
                    last_event=last_event,
                )
            )

        critical = sum(1 for s in snapshots if s.highest_severity in {"HIGH", "CRITICAL"})
        return FactoryOverview(
            total_cameras=len(cameras),
            enabled_cameras=sum(1 for c in cameras if c.enabled),
            cameras_with_events=sum(1 for s in snapshots if s.active_events),
            active_events=len(open_events),
            average_health=round(mean(health_values), 2) if health_values else None,
            critical_cameras=critical,
            snapshots=tuple(snapshots),
        )

    @staticmethod
    def _highest_severity(events: Iterable[dict]) -> str | None:
        values = [str(e.get("severity", "INFO")).upper() for e in events]
        if not values:
            return None
        return max(values, key=lambda value: _SEVERITY_RANK.get(value, 0))

    @staticmethod
    def _status(camera: CameraDefinition, events: list[dict], severity: str | None) -> str:
        if not camera.enabled:
            return "غیرفعال"
        if severity == "CRITICAL":
            return "بحرانی"
        if severity == "HIGH":
            return "هشدار سطح بالا"
        if events:
            return "نیازمند رسیدگی"
        if camera.health_score is None:
            return camera.status_fa or "آماده اتصال"
        if camera.health_score >= 90:
            return "پایدار"
        if camera.health_score >= 80:
            return "نیاز به پایش"
        if camera.health_score >= 70:
            return "هشدار سطح متوسط"
        if camera.health_score >= 50:
            return "هشدار سطح بالا"
        return "بحرانی"
