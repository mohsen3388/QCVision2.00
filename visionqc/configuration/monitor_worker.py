from __future__ import annotations

import time
from datetime import datetime, timezone

from PySide6.QtCore import QThread, Signal

from visionqc.edge.capture import ResilientCapture
from visionqc.edge.models import CameraHealth, ReconnectPolicy
from .production_runtime import ProductionRuntimeEngine


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RuntimeMonitorWorker(QThread):
    """Reliable image-source worker for file, USB and RTSP assignments.

    Network/USB failures no longer terminate monitoring immediately. The worker records health,
    applies exponential reconnect backoff, and continues until explicitly stopped or a file ends.
    """

    sample_ready = Signal(dict)
    failed = Signal(str)
    state_changed = Signal(str)
    health_ready = Signal(dict)

    def __init__(self, assignment, engine: ProductionRuntimeEngine, parent=None):
        super().__init__(parent)
        self.assignment = assignment
        self.engine = engine
        self._stop = False
        self.policy = ReconnectPolicy.from_overrides(assignment.get("overrides"))
        self.health = CameraHealth(
            camera_id=assignment["camera_id"],
            state="STARTING",
            source_type=assignment.get("source_type", ""),
        )

    def stop(self):
        self._stop = True
        self.requestInterruption()

    def _emit_health(self, state: str | None = None, message: str | None = None, capture=None):
        if state:
            self.health.state = state
        if message is not None:
            self.health.message = message
        if capture is not None:
            meta = capture.metadata()
            for key in ("backend", "width", "height", "source_fps", "measured_fps", "last_frame_at"):
                setattr(self.health, key, meta.get(key, getattr(self.health, key)))
        self.health.updated_at = utc_now()
        payload = self.health.to_dict()
        self.engine.repo.update_camera_health(self.assignment["camera_id"], payload)
        self.health_ready.emit(payload)
        self.state_changed.emit(self.health.state)

    def _interruptible_sleep(self, seconds: float):
        deadline = time.monotonic() + max(0.0, seconds)
        while not self._stop and time.monotonic() < deadline:
            self.msleep(100)

    def run(self):
        a = self.assignment
        source = a["source_value"]
        if a["source_type"].upper() == "USB":
            try:
                source = int(source or 0)
            except (TypeError, ValueError):
                source = 0

        interval = max(0.25, float(a.get("sampling_seconds", 2)))
        capture = ResilientCapture(source, a["source_type"], self.policy)
        reconnect_attempt = 0
        reconnect_delay = self.policy.initial_delay_seconds
        last_analysis = 0.0
        last_health_emit = 0.0

        self._emit_health("CONNECTING", "در حال اتصال به منبع تصویر...")
        try:
            while not self._stop:
                if not capture.is_opened:
                    ok, message = capture.open()
                    if not ok:
                        reconnect_attempt += 1
                        self.health.reconnect_count += 1
                        self.health.last_error_at = utc_now()
                        self.health.consecutive_failures += 1
                        self._emit_health("RECONNECTING", message, capture)
                        if self.policy.max_attempts > 0 and reconnect_attempt >= self.policy.max_attempts:
                            self.failed.emit(f"اتصال پس از {reconnect_attempt} تلاش برقرار نشد: {message}")
                            self._emit_health("FAILED", message, capture)
                            return
                        self._interruptible_sleep(reconnect_delay)
                        reconnect_delay = min(self.policy.max_delay_seconds, reconnect_delay * self.policy.multiplier)
                        continue
                    reconnect_attempt = 0
                    reconnect_delay = self.policy.initial_delay_seconds
                    self.health.consecutive_failures = 0
                    self.health.last_success_at = utc_now()
                    self._emit_health("RUNNING", "اتصال برقرار است.", capture)

                ok, frame = capture.read()
                if not ok:
                    self.health.consecutive_failures += 1
                    self.health.dropped_frames += 1
                    if a["source_type"].upper() == "FILE":
                        self._emit_health("EOF", "پایان فایل ویدئویی.", capture)
                        break
                    if self.health.consecutive_failures >= self.policy.read_failure_threshold:
                        self.health.last_error_at = utc_now()
                        capture.close()
                        self._emit_health("RECONNECTING", "دریافت فریم متوقف شد؛ تلاش برای اتصال مجدد.")
                    else:
                        self.msleep(100)
                    continue

                self.health.frames_received += 1
                self.health.consecutive_failures = 0
                self.health.last_frame_at = capture.last_frame_at
                self.health.last_success_at = self.health.last_frame_at
                now = time.monotonic()

                if now - last_analysis >= interval:
                    last_analysis = now
                    try:
                        result = self.engine.process_frame(a["camera_id"], frame)
                        self.health.frames_analyzed += 1
                        self.sample_ready.emit(result)
                    except Exception as exc:
                        self.failed.emit(str(exc))
                        self.health.last_error_at = utc_now()
                        self._emit_health("ANALYSIS_ERROR", str(exc), capture)
                        # A detector/template error should not leak capture resources or spin forever.
                        break

                if now - last_health_emit >= 1.0:
                    last_health_emit = now
                    self._emit_health("RUNNING", "جریان تصویر سالم است.", capture)
                self.msleep(10)
        finally:
            capture.close()
            if self.health.state not in {"FAILED", "EOF", "ANALYSIS_ERROR"}:
                self._emit_health("STOPPED", "پایش متوقف شد.")
