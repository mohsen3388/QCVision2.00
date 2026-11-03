from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from visionqc.analysis.engine import analyze_image


class AnalysisWorker(QObject):
    progress = Signal(int, str)
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, path: str, roi) -> None:
        super().__init__()
        self.path = path
        self.roi = roi

    @Slot()
    def run(self) -> None:
        try:
            result = analyze_image(
                self.path,
                self.roi,
                progress=lambda value, message: self.progress.emit(value, message),
            )
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()
