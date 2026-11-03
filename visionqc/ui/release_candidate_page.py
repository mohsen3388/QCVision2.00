from __future__ import annotations

from pathlib import Path
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton,
    QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)


class ReleaseCandidatePage(QWidget):
    def __init__(self, service) -> None:
        super().__init__()
        self.service = service
        self.last_report = None
        root = QVBoxLayout(self)
        title = QLabel("Release Candidate & Production Readiness")
        title.setObjectName("PageTitle")
        root.addWidget(title)
        root.addWidget(QLabel("Validate data integrity, recovery, deployment prerequisites and operational auditability before factory rollout."))
        self.summary = QLabel("Not assessed")
        self.summary.setObjectName("SectionTitle")
        root.addWidget(self.summary)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.checks = QTableWidget(0, 5)
        self.checks.setHorizontalHeaderLabels(["Category", "Check", "Required", "Status", "Details"])
        self.checks.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.tabs.addTab(self.checks, "Readiness checks")
        self.audit = QTableWidget(0, 6)
        self.audit.setHorizontalHeaderLabels(["Time", "Event", "Actor", "Entity", "Outcome", "Details"])
        self.audit.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.tabs.addTab(self.audit, "Audit trail")
        row = QHBoxLayout()
        assess = QPushButton("Run release assessment")
        assess.clicked.connect(self.refresh)
        export = QPushButton("Export readiness report")
        export.clicked.connect(self.export_report)
        reload_audit = QPushButton("Refresh audit trail")
        reload_audit.clicked.connect(self.refresh_audit)
        row.addWidget(assess); row.addWidget(export); row.addWidget(reload_audit); row.addStretch()
        root.addLayout(row)
        self.refresh()

    def refresh(self) -> None:
        try:
            self.last_report = self.service.assess()
        except Exception as exc:
            QMessageBox.critical(self, "Assessment failed", str(exc))
            return
        meta = self.last_report.metadata
        self.summary.setText(
            f"Release status: {self.last_report.level.value} — "
            f"{meta.get('required_failures', 0)} required failure(s), {meta.get('warnings', 0)} warning(s)"
        )
        self.checks.setRowCount(len(self.last_report.checks))
        for row, check in enumerate(self.last_report.checks):
            values = [check.category, check.name, "Yes" if check.required else "No", "OK" if check.ok else "Attention", check.message]
            for column, value in enumerate(values):
                self.checks.setItem(row, column, QTableWidgetItem(str(value)))
        self.refresh_audit()

    def refresh_audit(self) -> None:
        rows = self.service.recent_audit(200)
        self.audit.setRowCount(len(rows))
        for row, item in enumerate(rows):
            entity = f"{item.get('entity_type') or ''}:{item.get('entity_id') or ''}".strip(":")
            details = item.get("details", {})
            values = [item.get("created_at", ""), item.get("event_type", ""), item.get("actor", ""), entity, item.get("outcome", ""), str(details)]
            for column, value in enumerate(values):
                self.audit.setItem(row, column, QTableWidgetItem(str(value)))

    def export_report(self) -> None:
        target, _ = QFileDialog.getSaveFileName(
            self, "Export readiness report", str(Path.home() / "VisionQC_Release_Readiness.json"), "JSON (*.json)"
        )
        if not target:
            return
        try:
            path = self.service.export_report(Path(target), self.last_report)
            QMessageBox.information(self, "Report exported", f"Created:\n{path}")
            self.refresh_audit()
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
