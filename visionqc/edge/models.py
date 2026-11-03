from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class ReconnectPolicy:
    initial_delay_seconds: float = 0.5
    max_delay_seconds: float = 15.0
    multiplier: float = 2.0
    max_attempts: int = 0  # zero means unlimited until the worker is stopped
    stale_after_seconds: float = 8.0
    read_failure_threshold: int = 3
    open_timeout_ms: int = 5000
    read_timeout_ms: int = 5000
    buffer_size: int = 1

    @classmethod
    def from_overrides(cls, value: dict | None) -> "ReconnectPolicy":
        source = (value or {}).get("edge", value or {})
        allowed = {f.name for f in cls.__dataclass_fields__.values()}
        kwargs = {key: source[key] for key in allowed if key in source}
        return cls(**kwargs)


@dataclass(slots=True)
class CameraHealth:
    camera_id: str
    state: str = "STOPPED"
    message: str = ""
    source_type: str = ""
    backend: str = ""
    width: int = 0
    height: int = 0
    source_fps: float = 0.0
    measured_fps: float = 0.0
    last_frame_at: str | None = None
    last_success_at: str | None = None
    last_error_at: str | None = None
    reconnect_count: int = 0
    consecutive_failures: int = 0
    frames_received: int = 0
    frames_analyzed: int = 0
    dropped_frames: int = 0
    updated_at: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["updated_at"] = self.updated_at or utc_now()
        return data
