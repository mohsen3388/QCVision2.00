from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QTextEdit, QVBoxLayout,
)

from visionqc.ai.speech import (
    last_audio_status, list_windows_audio_devices, open_windows_sound_settings,
    test_headset,
)


class AudioSettingsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Audio Settings & Headset Test")
        self.resize(620, 430)
        root = QVBoxLayout(self)

        info = QLabel(
            "VisionQC sends operator alerts to the Windows default output device. "
            "Select your USB or Bluetooth headset as the Windows default output before testing."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        form = QFormLayout()
        self.devices = QComboBox()
        self.devices.addItems(list_windows_audio_devices())
        form.addRow("Detected playback endpoints", self.devices)
        root.addLayout(form)

        row = QHBoxLayout()
        self.test_button = QPushButton("Test Headset")
        self.windows_button = QPushButton("Open Windows Sound Settings")
        self.refresh_button = QPushButton("Refresh Devices")
        row.addWidget(self.test_button); row.addWidget(self.windows_button); row.addWidget(self.refresh_button)
        root.addLayout(row)

        self.status = QTextEdit(); self.status.setReadOnly(True)
        root.addWidget(self.status, 1)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        root.addWidget(close_button)

        self.test_button.clicked.connect(self._test)
        self.windows_button.clicked.connect(open_windows_sound_settings)
        self.refresh_button.clicked.connect(self._refresh)
        self._show_status()

    def _refresh(self) -> None:
        self.devices.clear(); self.devices.addItems(list_windows_audio_devices())
        self._show_status()

    def _test(self) -> None:
        test_headset()
        self.status.setPlainText(
            "English and Persian test messages were queued. Listen through the Windows default output device.\n\n"
            "You must hear both messages. If only the English message is audible, install project requirements "
            "again so the Persian neural voice component is available."
        )
        QTimer.singleShot(5000, self._show_status)

    def _show_status(self) -> None:
        state = last_audio_status()
        self.status.setPlainText(
            f"Last audio status: {state.get('status', 'unknown')}\n"
            f"Time: {state.get('timestamp', '—')}\n"
            f"Detail: {state.get('detail', '—')}\n\n"
            "Important: this list now shows Windows playback endpoints. VisionQC still follows the current "
            "Windows default output route, so select your Headphones endpoint in Windows before testing."
        )
