from __future__ import annotations

import os
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

import cv2

from visionqc.capture.sources import normalize_camera_source
from .models import ReconnectPolicy


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ResilientCapture:
    """OpenCV capture adapter with explicit timeout, low-latency buffering and health telemetry.

    Reconnection is intentionally coordinated by the worker so this class stays UI-independent
    and can also be exercised in unit tests or a future Windows service.
    """

    def __init__(self, source: str | int, source_type: str, policy: ReconnectPolicy | None = None):
        self.source = normalize_camera_source(source)
        self.source_type = source_type
        self.policy = policy or ReconnectPolicy()
        self.cap: Any = None
        self.backend = ""
        self.opened_at: str | None = None
        self.last_frame_at: str | None = None
        self.last_error = ""
        self._frame_times: deque[float] = deque(maxlen=60)

    def _backend_candidates(self) -> list[int | None]:
        if isinstance(self.source, int):
            if os.name == "nt":
                return [getattr(cv2, "CAP_DSHOW", None), getattr(cv2, "CAP_MSMF", None), None]
            return [getattr(cv2, "CAP_V4L2", None), None]
        if self.source_type.upper() in {"RTSP", "IP", "HTTP"}:
            return [getattr(cv2, "CAP_FFMPEG", None), None]
        return [None]

    def open(self) -> tuple[bool, str]:
        self.close()
        errors: list[str] = []
        for backend in self._backend_candidates():
            try:
                cap = cv2.VideoCapture(self.source) if backend is None else cv2.VideoCapture(self.source, backend)
                self._apply_options(cap)
                if cap.isOpened():
                    self.cap = cap
                    self.backend = self._backend_name(backend)
                    self.opened_at = _now_iso()
                    self.last_error = ""
                    return True, f"Connected using {self.backend}."
                cap.release()
                errors.append(f"{self._backend_name(backend)}: open failed")
            except Exception as exc:  # pragma: no cover - backend-specific
                errors.append(f"{self._backend_name(backend)}: {exc}")
        self.last_error = "; ".join(errors) or "Could not open source."
        return False, self.last_error

    def _apply_options(self, cap: Any) -> None:
        options = [
            (getattr(cv2, "CAP_PROP_BUFFERSIZE", -1), float(self.policy.buffer_size)),
            (getattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC", -1), float(self.policy.open_timeout_ms)),
            (getattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC", -1), float(self.policy.read_timeout_ms)),
        ]
        for prop, value in options:
            if prop >= 0:
                try:
                    cap.set(prop, value)
                except Exception:
                    pass

    @staticmethod
    def _backend_name(backend: int | None) -> str:
        names = {
            getattr(cv2, "CAP_FFMPEG", -100): "FFMPEG",
            getattr(cv2, "CAP_DSHOW", -101): "DSHOW",
            getattr(cv2, "CAP_MSMF", -102): "MSMF",
            getattr(cv2, "CAP_V4L2", -103): "V4L2",
        }
        return "AUTO" if backend is None else names.get(backend, str(backend))

    @property
    def is_opened(self) -> bool:
        return bool(self.cap is not None and self.cap.isOpened())

    def read(self):
        if not self.is_opened:
            return False, None
        ok, frame = self.cap.read()
        now = time.monotonic()
        if ok and frame is not None:
            self._frame_times.append(now)
            self.last_frame_at = _now_iso()
            self.last_error = ""
            return True, frame
        self.last_error = "Frame read failed."
        return False, None

    def metadata(self) -> dict:
        cap = self.cap
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0) if cap is not None else 0
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0) if cap is not None else 0
        source_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0) if cap is not None else 0.0
        measured = 0.0
        if len(self._frame_times) >= 2:
            elapsed = self._frame_times[-1] - self._frame_times[0]
            measured = (len(self._frame_times) - 1) / elapsed if elapsed > 0 else 0.0
        return {
            "backend": self.backend,
            "width": width,
            "height": height,
            "source_fps": round(source_fps, 2),
            "measured_fps": round(measured, 2),
            "last_frame_at": self.last_frame_at,
            "last_error": self.last_error,
        }

    def close(self) -> None:
        if self.cap is not None:
            try:
                self.cap.release()
            finally:
                self.cap = None
