from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWizard, QWizardPage
)

from visionqc.core.diagnostics import camera_test
from visionqc.core.settings import load_settings, save_settings


class FirstRunWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("VisionQC First-run Setup")
        self.setMinimumSize(720, 500)
        self.settings = load_settings()
        self.addPage(self._welcome_page())
        self.addPage(self._factory_page())
        self.addPage(self._storage_page())
        self.addPage(self._device_page())
        self.addPage(self._finish_page())
        self.accepted.connect(self._save)

    def _welcome_page(self):
        p = QWizardPage(); p.setTitle("Welcome to VisionQC")
        l = QVBoxLayout(p)
        text = QLabel("This guided setup prepares VisionQC for a non-technical user. It configures the factory profile, local storage and camera defaults. No internet connection is required.")
        text.setWordWrap(True); l.addWidget(text); l.addStretch(); return p

    def _factory_page(self):
        p = QWizardPage(); p.setTitle("Factory and operator")
        f = QFormLayout(p)
        self.factory = QLineEdit(self.settings["factory_name"])
        self.operator = QLineEdit(self.settings["operator_name"])
        self.language = QComboBox(); self.language.addItems(["English", "Persian (planned)"])
        f.addRow("Factory name", self.factory); f.addRow("Default operator", self.operator); f.addRow("Language", self.language)
        return p

    def _storage_page(self):
        p = QWizardPage(); p.setTitle("Local data storage")
        l = QVBoxLayout(p)
        self.data_dir = QLineEdit(self.settings["data_directory"])
        self.report_dir = QLineEdit(self.settings["reports_directory"])
        for label, edit in [("Batch data", self.data_dir), ("Reports", self.report_dir)]:
            row = QHBoxLayout(); row.addWidget(QLabel(label)); row.addWidget(edit, 1)
            b = QPushButton("Browse"); b.clicked.connect(lambda checked=False, e=edit: self._browse(e)); row.addWidget(b); l.addLayout(row)
        self.keep_data = QCheckBox("Keep production data if the application is uninstalled")
        self.keep_data.setChecked(True); l.addWidget(self.keep_data); l.addStretch(); return p

    def _device_page(self):
        p = QWizardPage(); p.setTitle("Camera test")
        l = QVBoxLayout(p)
        row = QHBoxLayout(); self.camera = QSpinBox(); self.camera.setRange(0, 20); self.camera.setValue(int(self.settings["camera_index"]))
        test = QPushButton("Test camera"); self.camera_result = QLabel("Not tested")
        test.clicked.connect(self._test_camera); row.addWidget(QLabel("Camera index")); row.addWidget(self.camera); row.addWidget(test); row.addStretch()
        l.addLayout(row); l.addWidget(self.camera_result); l.addWidget(QLabel("You can change this later under Settings & Diagnostics.")); l.addStretch(); return p

    def _finish_page(self):
        p = QWizardPage(); p.setTitle("Setup complete")
        l = QVBoxLayout(p); t = QLabel("VisionQC will create its local database and open the Home Dashboard. All features remain accessible through the ALL FEATURES button.")
        t.setWordWrap(True); l.addWidget(t); l.addStretch(); return p

    def _browse(self, edit):
        selected = QFileDialog.getExistingDirectory(self, "Choose directory", edit.text())
        if selected: edit.setText(selected)

    def _test_camera(self):
        ok, msg = camera_test(self.camera.value())
        self.camera_result.setText(("✓ " if ok else "⚠ ") + msg)

    def _save(self):
        values = self.settings.copy()
        values.update({
            "first_run_complete": True,
            "factory_name": self.factory.text().strip() or "My Factory",
            "operator_name": self.operator.text().strip() or "Operator",
            "language": self.language.currentText(),
            "data_directory": str(Path(self.data_dir.text()).expanduser()),
            "reports_directory": str(Path(self.report_dir.text()).expanduser()),
            "camera_index": self.camera.value(),
            "keep_data_on_uninstall": self.keep_data.isChecked(),
        })
        save_settings(values)
