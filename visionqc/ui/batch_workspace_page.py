from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget
)

from visionqc.core.database import add_batch_event, create_batch, list_batches, update_batch
from visionqc.core.settings import load_settings


class BatchWorkspacePage(QWidget):
    def __init__(self):
        super().__init__(); self.current_batch_id: int|None=None
        root=QVBoxLayout(self); title=QLabel("Batch Workspace"); title.setObjectName("PageTitle"); root.addWidget(title)
        root.addWidget(QLabel("Create a traceable production batch, record stage changes and capture the final QC decision."))
        form=QFormLayout(); self.code=QLineEdit(datetime.now().strftime("BATCH-%Y%m%d-%H%M")); self.product=QLineEdit("Sausage Emulsion")
        self.line=QLineEdit("Line 1"); self.operator=QLineEdit(load_settings()["operator_name"])
        self.stage=QComboBox(); self.stage.addItems(["Preparation","Mixing","Homogenization","Stable","Finished"])
        self.notes=QTextEdit(); self.notes.setMaximumHeight(90)
        form.addRow("Batch code",self.code); form.addRow("Product / recipe",self.product); form.addRow("Production line",self.line); form.addRow("Operator",self.operator); form.addRow("Process stage",self.stage); form.addRow("Notes",self.notes); root.addLayout(form)
        actions=QHBoxLayout(); self.start=QPushButton("Start batch"); self.save=QPushButton("Save update"); self.accept=QPushButton("Finish — Accept"); self.reject=QPushButton("Finish — Reject")
        self.start.clicked.connect(self._start); self.save.clicked.connect(self._save); self.accept.clicked.connect(lambda:self._finish("Accepted")); self.reject.clicked.connect(lambda:self._finish("Rejected"))
        for b in [self.start,self.save,self.accept,self.reject]: actions.addWidget(b)
        actions.addStretch(); root.addLayout(actions)
        self.status=QLabel("No active batch"); self.status.setObjectName("InfoPanel"); root.addWidget(self.status)
        root.addWidget(QLabel("Recent batches")); self.table=QTableWidget(0,7); self.table.setHorizontalHeaderLabels(["Code","Product","Line","Operator","Stage","Status","QC Outcome"]); root.addWidget(self.table,1); self.refresh()

    def _start(self):
        if not self.code.text().strip() or not self.product.text().strip(): QMessageBox.warning(self,"Required","Batch code and product are required."); return
        try:
            self.current_batch_id=create_batch(self.code.text().strip(),self.product.text().strip(),self.line.text().strip(),self.operator.text().strip(),self.stage.currentText(),self.notes.toPlainText().strip())
            self.status.setText(f"Active batch: {self.code.text()} — {self.stage.currentText()}"); self.refresh()
        except Exception as e: QMessageBox.critical(self,"Could not start batch",str(e))

    def _save(self):
        if self.current_batch_id is None: QMessageBox.information(self,"No active batch","Start a batch first."); return
        update_batch(self.current_batch_id,self.stage.currentText(),self.notes.toPlainText().strip())
        add_batch_event(self.current_batch_id,"BATCH_UPDATED",f"Stage changed or confirmed: {self.stage.currentText()}")
        self.status.setText(f"Saved: {self.code.text()} — {self.stage.currentText()}"); self.refresh()

    def _finish(self,outcome):
        if self.current_batch_id is None: QMessageBox.information(self,"No active batch","Start a batch first."); return
        answer=QMessageBox.question(self,"Confirm final QC decision",f"Finish this batch as {outcome}? This decision will be recorded.")
        if answer!=QMessageBox.StandardButton.Yes:return
        update_batch(self.current_batch_id,"Finished",self.notes.toPlainText().strip(),"Finished",outcome)
        add_batch_event(self.current_batch_id,"QC_DECISION",outcome)
        self.status.setText(f"Batch finished — {outcome}"); self.current_batch_id=None; self.refresh()

    def refresh(self):
        rows=list_batches(); self.table.setRowCount(len(rows))
        keys=["batch_code","product_name","production_line","operator_name","process_stage","status","qc_outcome"]
        for r,row in enumerate(rows):
            for c,k in enumerate(keys): self.table.setItem(r,c,QTableWidgetItem(str(row[k] or "")))
        self.table.resizeColumnsToContents()
