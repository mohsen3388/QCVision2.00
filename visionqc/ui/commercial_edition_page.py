from __future__ import annotations

from pathlib import Path
from PySide6.QtWidgets import QFileDialog, QFormLayout, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget


class CommercialEditionPage(QWidget):
    def __init__(self, service) -> None:
        super().__init__(); self.service = service
        root = QVBoxLayout(self)
        title = QLabel("Commercial Edition & Product Operations"); title.setObjectName("PageTitle"); root.addWidget(title)
        root.addWidget(QLabel("Offline licensing, verified update manifests, diagnostics bundles and local crash-report operations."))
        form = QFormLayout(); self.state=QLabel(); self.customer=QLabel(); self.machine=QLabel(); self.expiry=QLabel(); self.version=QLabel()
        form.addRow("License state", self.state); form.addRow("Customer", self.customer); form.addRow("Machine ID", self.machine); form.addRow("Expires", self.expiry); form.addRow("Installed version", self.version); root.addLayout(form)
        buttons=QHBoxLayout()
        for label, slot in [("Import offline license",self.import_license),("Remove license",self.remove_license),("Check offline update manifest",self.check_update),("Create support bundle",self.create_bundle),("Refresh",self.refresh)]:
            b=QPushButton(label); b.clicked.connect(slot); buttons.addWidget(b)
        buttons.addStretch(); root.addLayout(buttons)
        self.summary=QLabel(); self.summary.setWordWrap(True); root.addWidget(self.summary)
        self.checks=QTableWidget(0,3); self.checks.setHorizontalHeaderLabels(["Commercial check","Status","Details"]); self.checks.horizontalHeader().setSectionResizeMode(2,QHeaderView.Stretch); root.addWidget(self.checks,1)
        self.refresh()

    def refresh(self):
        report=self.service.readiness(); status=report.license_status
        self.state.setText(status.state.value); self.customer.setText(status.customer or "—"); self.machine.setText(status.machine_id); self.expiry.setText(status.expires_at or "Perpetual / not specified")
        self.version.setText(report.update_assessment.current_version); self.summary.setText(f"Crash reports retained locally: {report.crash_reports}. License message: {status.message}")
        self.checks.setRowCount(len(report.checks))
        for r,item in enumerate(report.checks):
            for c,value in enumerate([item['name'],"OK" if item['ok'] else "Attention",item['details']]): self.checks.setItem(r,c,QTableWidgetItem(str(value)))

    def import_license(self):
        path,_=QFileDialog.getOpenFileName(self,"Import VisionQC license",str(Path.home()),"VisionQC license (*.json);;JSON (*.json)")
        if not path:return
        try: status=self.service.import_license(Path(path)); QMessageBox.information(self,"License imported",status.message); self.refresh()
        except Exception as exc: QMessageBox.critical(self,"License rejected",str(exc))

    def remove_license(self):
        self.service.remove_license(); self.refresh()

    def check_update(self):
        path,_=QFileDialog.getOpenFileName(self,"Select offline update manifest",str(Path.home()),"Update manifest (*.json)")
        if not path:return
        try:
            result=self.service.assess_update_manifest(Path(path)); QMessageBox.information(self,"Update assessment",f"Current: {result.current_version}\nAvailable: {result.available_version or 'None'}\nUpdate available: {'Yes' if result.update_available else 'No'}\n{result.message}")
        except Exception as exc: QMessageBox.critical(self,"Update check failed",str(exc))

    def create_bundle(self):
        folder=QFileDialog.getExistingDirectory(self,"Select support bundle destination",str(Path.home()))
        if not folder:return
        try: path=self.service.create_diagnostics_bundle(Path(folder)); QMessageBox.information(self,"Support bundle created",str(path))
        except Exception as exc: QMessageBox.critical(self,"Bundle failed",str(exc))
