from __future__ import annotations

import numpy as np

import visionqc.core.database as db
from visionqc.configuration.runtime_repository import RuntimeRepository
from visionqc.edge.capture import ResilientCapture
from visionqc.edge.models import CameraHealth, ReconnectPolicy


class FakeCapture:
    def __init__(self, source, backend=None):
        self.source = source
        self.backend = backend
        self.opened = True
        self.released = False
        self.props = {}
        self.frames = [np.zeros((48, 64, 3), dtype=np.uint8)]

    def set(self, key, value):
        self.props[key] = value
        return True

    def isOpened(self):
        return self.opened and not self.released

    def read(self):
        if self.frames:
            return True, self.frames.pop(0)
        return False, None

    def get(self, prop):
        import cv2
        if prop == cv2.CAP_PROP_FRAME_WIDTH:
            return 64
        if prop == cv2.CAP_PROP_FRAME_HEIGHT:
            return 48
        if prop == cv2.CAP_PROP_FPS:
            return 25
        return 0

    def release(self):
        self.released = True


def test_resilient_capture_returns_metadata(monkeypatch):
    import visionqc.edge.capture as module
    monkeypatch.setattr(module.cv2, "VideoCapture", FakeCapture)
    capture = ResilientCapture("rtsp://camera/stream", "RTSP", ReconnectPolicy(buffer_size=1))
    opened, _ = capture.open()
    assert opened
    ok, frame = capture.read()
    assert ok and frame.shape[:2] == (48, 64)
    metadata = capture.metadata()
    assert metadata["width"] == 64
    assert metadata["height"] == 48
    assert metadata["source_fps"] == 25
    capture.close()
    assert not capture.is_opened


def test_reconnect_policy_reads_assignment_overrides():
    policy = ReconnectPolicy.from_overrides({"edge": {"max_attempts": 7, "stale_after_seconds": 3}})
    assert policy.max_attempts == 7
    assert policy.stale_after_seconds == 3
    assert policy.read_failure_threshold == 3


def test_camera_health_is_persisted(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "database_path", lambda: tmp_path / "sprint6.db")
    repo = RuntimeRepository()
    health = CameraHealth(
        camera_id="cam-1", state="RUNNING", source_type="RTSP", backend="FFMPEG",
        width=1280, height=720, measured_fps=12.5, reconnect_count=2,
        frames_received=100, frames_analyzed=10, message="healthy",
    )
    repo.update_camera_health("cam-1", health)
    stored = repo.camera_health("cam-1")
    assert stored["state"] == "RUNNING"
    assert stored["backend"] == "FFMPEG"
    assert stored["reconnect_count"] == 2
    assert stored["frames_received"] == 100
