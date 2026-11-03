from __future__ import annotations

import time
from threading import Event
import cv2
from PySide6.QtCore import QObject, Signal, Slot

from visionqc.analysis.engine import analyze_bgr
from visionqc.analysis.temporal import sample_from_result
from visionqc.analysis.motion import motion_scores
from visionqc.capture.sources import normalize_camera_source


class CameraWorker(QObject):
    frame_ready = Signal(bytes, int, int)
    sample_ready = Signal(object)
    analysis_ready = Signal(object, object, bytes)
    status = Signal(str)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, source: str | int, analysis_interval: float = 2.0) -> None:
        super().__init__()
        self.source = normalize_camera_source(source)
        self.analysis_interval = max(.5, analysis_interval)
        self.stop_event = Event()

    @Slot()
    def run(self):
        cap = cv2.VideoCapture(self.source, cv2.CAP_DSHOW) if isinstance(self.source, int) else cv2.VideoCapture(self.source)
        if not cap.isOpened():
            self.failed.emit("Could not open the selected camera or network stream.")
            self.finished.emit()
            return
        self.status.emit("Connected. Continuous local analysis is active.")
        started = time.monotonic()
        last_analysis = 0.0
        last_preview = 0.0
        preview_interval = 0.10  # cap GUI preview at ~10 FPS to prevent queued-signal backlog
        frame_index = 0
        previous_analysis_gray = None
        failures = 0
        try:
            while not self.stop_event.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:
                    failures += 1
                    if failures > 30:
                        self.failed.emit("The stream stopped delivering frames.")
                        break
                    time.sleep(.05)
                    continue
                failures = 0
                frame_index += 1
                now = time.monotonic()
                jpeg = b""
                needs_preview = now - last_preview >= preview_interval
                needs_analysis = now - last_analysis >= self.analysis_interval
                if needs_preview or needs_analysis:
                    ok_jpg, encoded = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 78])
                    jpeg = encoded.tobytes() if ok_jpg else b""
                if needs_preview and jpeg:
                    self.frame_ready.emit(jpeg, frame.shape[1], frame.shape[0])
                    last_preview = now
                if needs_analysis:
                    result = analyze_bgr(
                        frame,
                        f"camera://{self.source}#frame={frame_index}",
                        include_diagnostics=False,
                    )
                    sample = sample_from_result(result, frame_index, now - started)
                    previous_analysis_gray, sample.motion_stability, sample.mixing_coverage = motion_scores(previous_analysis_gray, frame)
                    self.sample_ready.emit(sample)
                    self.analysis_ready.emit(result, sample, jpeg)
                    last_analysis = now
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            cap.release()
            self.finished.emit()

    def stop(self):
        self.stop_event.set()
