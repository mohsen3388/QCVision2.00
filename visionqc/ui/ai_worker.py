from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from visionqc.ai.gemini_provider import GeminiProvider
from visionqc.ai.schemas import AIInspectionResult


class GeminiWorker(QObject):
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        mode: str,
        model: str,
        image_path: str | None = None,
        question: str = "",
        process_data: dict[str, Any] | None = None,
        local_context: dict[str, Any] | None = None,
        inspection: AIInspectionResult | None = None,
    ) -> None:
        super().__init__()
        self.mode = mode
        self.model = model
        self.image_path = image_path
        self.question = question
        self.process_data = process_data or {}
        self.local_context = local_context or {}
        self.inspection = inspection

    @Slot()
    def run(self) -> None:
        try:
            provider = GeminiProvider(model=self.model)
            if self.mode == "inspect":
                result = provider.inspect_image(
                    self.image_path or "",
                    process_data=self.process_data,
                    opencv_context=self.local_context,
                )
            elif self.mode == "chat":
                result = provider.ask(
                    self.question,
                    inspection=self.inspection,
                    local_context=self.local_context,
                    image_path=self.image_path,
                )
            else:
                raise ValueError(f"Unsupported Gemini worker mode: {self.mode}")
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()
