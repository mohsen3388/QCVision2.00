from __future__ import annotations

from threading import Event
from PySide6.QtCore import QObject, Signal, Slot

from visionqc.analysis.temporal import analyze_video


class VideoAnalysisWorker(QObject):
    progress = Signal(int, str)
    sample = Signal(object)
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, path: str, interval: float) -> None:
        super().__init__(); self.path = path; self.interval = interval; self.cancel_event = Event()

    @Slot()
    def run(self) -> None:
        try:
            result = analyze_video(self.path, self.interval, self.progress.emit, self.sample.emit, self.cancel_event)
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()

    def cancel(self) -> None:
        self.cancel_event.set()
