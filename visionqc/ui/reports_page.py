from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QComboBox, QFileDialog, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from visionqc.core.database import list_batches
from visionqc.core.reporting import generate_batch_pdf, list_reports
from visionqc.core.settings import load_settings


class ReportsPage(QWidget):
    def __init__(self):
        super().__init__()
        root=QVBoxLayout(self)
        title=QLabel("PDF Reports & QR Verification"); title.setObjectName("PageTitle"); root.addWidget(title)
        root.addWidget(QLabel("Generate an offline professional batch report with an auditable event timeline and embedded QR identity payload."))
        controls=QHBoxLayout(); self.batch=QComboBox(); controls.addWidget(QLabel("Batch")); controls.addWidget(self.batch,1)
        refresh=QPushButton("Refresh"); refresh.clicked.connect(self.refresh); controls.addWidget(refresh)
        generate=QPushButton("Generate PDF Report"); generate.clicked.connect(self.generate); controls.addWidget(generate)
        root.addLayout(controls)
        self.table=QTableWidget(0,5); self.table.setHorizontalHeaderLabels(["Report Code","Batch","Product","Created","File"]); self.table.doubleClicked.connect(self.open_selected); root.addWidget(self.table,1)
        buttons=QHBoxLayout(); open_btn=QPushButton("Open Selected Report"); open_btn.clicked.connect(self.open_selected); buttons.addWidget(open_btn); folder=QPushButton("Open Reports Folder"); folder.clicked.connect(self.open_folder); buttons.addWidget(folder); buttons.addStretch(); root.addLayout(buttons)
        root.addWidget(QLabel("Safety: the PDF is decision-support evidence and does not replace laboratory, food-safety or qualified QC approval."))
        self.rows=[]; self.refresh()

    def refresh(self):
        current=self.batch.currentData(); self.batch.clear()
        for row in list_batches(500): self.batch.addItem(f"{row['batch_code']} — {row['product_name']}", int(row['id']))
        if current is not None:
            idx=self.batch.findData(current)
            if idx>=0:self.batch.setCurrentIndex(idx)
        self.rows=list_reports(); self.table.setRowCount(len(self.rows))
        for r,item in enumerate(self.rows):
            vals=[item['report_code'],item['batch_code'],item['product_name'],item['created_at'],item['file_path']]
            for c,v in enumerate(vals): self.table.setItem(r,c,QTableWidgetItem(str(v or "")))
        self.table.resizeColumnsToContents()

    def generate(self):
        batch_id=self.batch.currentData()
        if batch_id is None:
            QMessageBox.warning(self,"PDF Reports","Create a batch first."); return
        try:
            result=generate_batch_pdf(int(batch_id))
        except Exception as exc:
            QMessageBox.critical(self,"Report generation failed",str(exc)); return
        self.refresh(); QMessageBox.information(self,"Report generated",f"PDF report created successfully:\n{result.path}")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(result.path)))

    def open_selected(self, *_):
        row=self.table.currentRow()
        if row<0 or row>=len(self.rows): return
        path=Path(self.rows[row]['file_path'])
        if not path.exists(): QMessageBox.warning(self,"Missing file",f"Report file no longer exists:\n{path}"); return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def open_folder(self):
        folder=Path(load_settings()['reports_directory']); folder.mkdir(parents=True,exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
