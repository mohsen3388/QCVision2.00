from __future__ import annotations

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QFrame,
                               QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from visionqc.core.automation import MetricProfile, import_analysis_file, list_imports, list_metric_profiles, save_metric_profile
from visionqc.core.database import list_batches


class AutomationCenterPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        title = QLabel("Automation Center"); title.setObjectName("PageTitle"); root.addWidget(title)
        root.addWidget(QLabel("Import visual-analysis results directly into SPC and create auditable events from triggered findings."))

        card = QFrame(); card.setObjectName("Card"); form = QFormLayout(card)
        file_row = QWidget(); fh = QHBoxLayout(file_row); fh.setContentsMargins(0,0,0,0)
        self.path = QLineEdit(); browse = QPushButton("Browse JSON"); browse.clicked.connect(self.browse)
        fh.addWidget(self.path,1); fh.addWidget(browse); form.addRow("Analysis result", file_row)
        self.batch = QComboBox(); form.addRow("Batch", self.batch)
        self.product = QLineEdit(); self.line = QLineEdit(); self.operator = QLineEdit()
        form.addRow("Product", self.product); form.addRow("Production line", self.line); form.addRow("Operator", self.operator)
        self.unprofiled = QCheckBox("Import numeric metrics even when no profile exists"); self.unprofiled.setChecked(True)
        self.events = QCheckBox("Create process events for triggered findings"); self.events.setChecked(True)
        form.addRow(self.unprofiled); form.addRow(self.events)
        run = QPushButton("Import into SPC"); run.clicked.connect(self.run_import); form.addRow(run)
        root.addWidget(card)

        profile = QFrame(); profile.setObjectName("Card"); pf = QFormLayout(profile)
        self.metric = QLineEdit(); self.group = QLineEdit("Quality"); self.unit = QLineEdit()
        self.target = QDoubleSpinBox(); self.lsl = QDoubleSpinBox(); self.usl = QDoubleSpinBox()
        for w in (self.target,self.lsl,self.usl): w.setRange(-1e9,1e9); w.setDecimals(6)
        self.has_target=QCheckBox("Use target"); self.has_lsl=QCheckBox("Use LSL"); self.has_usl=QCheckBox("Use USL")
        pf.addRow("Metric name",self.metric); pf.addRow("Metric group",self.group); pf.addRow("Unit",self.unit)
        tr=QWidget(); th=QHBoxLayout(tr); th.setContentsMargins(0,0,0,0); th.addWidget(self.has_target); th.addWidget(self.target); pf.addRow("Target",tr)
        lr=QWidget(); lh=QHBoxLayout(lr); lh.setContentsMargins(0,0,0,0); lh.addWidget(self.has_lsl); lh.addWidget(self.lsl); pf.addRow("LSL",lr)
        ur=QWidget(); uh=QHBoxLayout(ur); uh.setContentsMargins(0,0,0,0); uh.addWidget(self.has_usl); uh.addWidget(self.usl); pf.addRow("USL",ur)
        save=QPushButton("Save metric profile"); save.clicked.connect(self.save_profile); pf.addRow(save)
        root.addWidget(profile)

        self.table=QTableWidget(0,5); self.table.setHorizontalHeaderLabels(["Time","Source","Batch","Metrics","Events"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); root.addWidget(self.table,1)
        self.reload()

    def browse(self):
        p,_=QFileDialog.getOpenFileName(self,"Select analysis JSON","","JSON (*.json)")
        if p:self.path.setText(p)

    def reload(self):
        self.batch.clear(); self.batch.addItem("No batch",None)
        for b in list_batches(500): self.batch.addItem(f"{b['batch_code']} — {b['product_name']}",b['id'])
        rows=list_imports(); self.table.setRowCount(len(rows))
        for i,r in enumerate(rows):
            vals=[r['imported_at'],r['source_path'],str(r['batch_id'] or ''),str(r['imported_metrics']),str(r['generated_events'])]
            for j,v in enumerate(vals): self.table.setItem(i,j,QTableWidgetItem(v))

    def run_import(self):
        try:
            result=import_analysis_file(self.path.text().strip(),batch_id=self.batch.currentData(),product_name=self.product.text().strip() or None,
                production_line=self.line.text().strip() or None,operator_name=self.operator.text().strip() or None,
                import_unprofiled=self.unprofiled.isChecked(),create_finding_events=self.events.isChecked())
            QMessageBox.information(self,"Import complete",f"Imported metrics: {result.imported_metrics}\nSkipped: {result.skipped_metrics}\nEvents: {result.generated_events}")
            self.reload()
        except Exception as exc: QMessageBox.critical(self,"Import failed",str(exc))

    def save_profile(self):
        try:
            save_metric_profile(MetricProfile(self.metric.text().strip(),self.group.text().strip(),self.unit.text().strip(),
                self.target.value() if self.has_target.isChecked() else None,self.lsl.value() if self.has_lsl.isChecked() else None,
                self.usl.value() if self.has_usl.isChecked() else None,True))
            QMessageBox.information(self,"Saved",f"Metric profile saved. Total profiles: {len(list_metric_profiles())}")
        except Exception as exc: QMessageBox.critical(self,"Cannot save",str(exc))
