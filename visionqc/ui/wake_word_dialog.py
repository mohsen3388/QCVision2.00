from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout
from visionqc.voice.speech_recognition import recognize_once


class _MicrophoneTestWorker(QThread):
    completed = Signal(str)

    def run(self) -> None:
        result = recognize_once(culture="en-US", timeout_seconds=6)
        if result.text:
            self.completed.emit(f"Microphone test passed. Heard: {result.text} ({result.confidence:.0%})")
        elif result.available:
            self.completed.emit(f"Microphone is available, but no speech was recognized. {result.error}".strip())
        else:
            self.completed.emit(f"Microphone test failed: {result.error}")


class WakeWordStatusDialog(QDialog):
    def __init__(self, *, enabled: bool, status: str, debug_text: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Wake Word & Microphone Debug")
        self.resize(620, 390)
        self._worker: _MicrophoneTestWorker | None = None
        layout = QVBoxLayout(self)
        title = QLabel("Hands-Free Wake Word")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        layout.addWidget(title)
        explanation = QLabel(
            "Say ‘Vision’ followed by a question, for example:\n\n"
            "Vision, what should I check first?\n\n"
            "The microphone pauses while VisionQC is speaking and resumes automatically afterwards."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        self.state = QLabel(f"Enabled: {'Yes' if enabled else 'No'}\nStatus: {status}")
        self.state.setWordWrap(True)
        layout.addWidget(self.state)
        self.debug = QLabel(f"Last voice event: {debug_text or 'No microphone event received yet.'}")
        self.debug.setWordWrap(True)
        self.debug.setStyleSheet("padding: 8px; border: 1px solid #b8c2cc; border-radius: 4px;")
        layout.addWidget(self.debug)
        self.test_button = QPushButton("Test Microphone (6 seconds)")
        self.test_button.clicked.connect(self._test_microphone)
        layout.addWidget(self.test_button)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        layout.addWidget(close)

    def _test_microphone(self) -> None:
        self.test_button.setEnabled(False)
        self.debug.setText("Listening. Say: Vision, microphone test.")
        self._worker = _MicrophoneTestWorker()
        self._worker.completed.connect(self._test_completed)
        self._worker.start()

    def _test_completed(self, message: str) -> None:
        self.debug.setText(message)
        self.test_button.setEnabled(True)
        self._worker = None
