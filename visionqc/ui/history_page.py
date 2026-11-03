from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget
from visionqc.core.database import list_batches
from visionqc.core.reporting import get_batch_timeline, list_reports


class HistoryPage(QWidget):
    def __init__(self):
        super().__init__(); root=QVBoxLayout(self); title=QLabel("History & Replay"); title.setObjectName("PageTitle"); root.addWidget(title)
        root.addWidget(QLabel("Select a batch to replay its recorded lifecycle, process events and generated evidence reports in chronological order."))
        row=QHBoxLayout(); refresh=QPushButton("Refresh"); refresh.clicked.connect(self.refresh); row.addWidget(refresh); row.addStretch(); root.addLayout(row)
        splitter=QSplitter(); self.table=QTableWidget(0,9); self.table.setHorizontalHeaderLabels(["Code","Product","Line","Operator","Stage","Status","QC","Started","Ended"]); self.table.itemSelectionChanged.connect(self.show_selected); splitter.addWidget(self.table)
        detail=QWidget(); d=QVBoxLayout(detail); d.addWidget(QLabel("Batch Replay Timeline")); self.summary=QTextEdit(); self.summary.setReadOnly(True); self.summary.setMaximumHeight(145); d.addWidget(self.summary); self.events=QTableWidget(0,5); self.events.setHorizontalHeaderLabels(["Time","Severity","Source","Event","Description"]); d.addWidget(self.events,1); splitter.addWidget(detail); splitter.setStretchFactor(0,3); splitter.setStretchFactor(1,4); root.addWidget(splitter,1)
        self.rows=[]; self.refresh()
    def refresh(self):
        self.rows=list_batches(500); self.table.setRowCount(len(self.rows)); keys=["batch_code","product_name","production_line","operator_name","process_stage","status","qc_outcome","started_at","ended_at"]
        for r,row in enumerate(self.rows):
            for c,k in enumerate(keys): self.table.setItem(r,c,QTableWidgetItem(str(row[k] or "")))
        self.table.resizeColumnsToContents()
        if self.rows and self.table.currentRow()<0:self.table.selectRow(0)
    def show_selected(self):
        idx=self.table.currentRow()
        if idx<0 or idx>=len(self.rows):return
        b=self.rows[idx]; reports=list_reports(int(b['id'])); timeline=get_batch_timeline(int(b['id']))
        self.summary.setPlainText(f"Batch: {b['batch_code']}\nProduct: {b['product_name']} | Line: {b['production_line'] or '—'} | Operator: {b['operator_name'] or '—'}\nStage: {b['process_stage'] or '—'} | Status: {b['status']} | QC: {b['qc_outcome'] or '—'}\nReports generated: {len(reports)} | Timeline events: {len(timeline)}\nNotes: {b['notes'] or '—'}")
        self.events.setRowCount(len(timeline))
        for r,e in enumerate(timeline):
            vals=[e.get('created_at'),e.get('severity'),e.get('source'),e.get('event_type'),e.get('message')]
            for c,v in enumerate(vals): self.events.setItem(r,c,QTableWidgetItem(str(v or '')))
        self.events.resizeColumnsToContents()
