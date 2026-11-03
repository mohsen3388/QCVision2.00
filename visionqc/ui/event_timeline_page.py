from __future__ import annotations
import json
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QComboBox,QPushButton,QTableWidget,QTableWidgetItem,QMessageBox,QFileDialog
from visionqc.core.event_engine import ProcessEvent,record_event,list_events,acknowledge_event,events_to_timeline,SEVERITIES

class EventTimelinePage(QWidget):
    def __init__(self):
        super().__init__(); root=QVBoxLayout(self); title=QLabel("Event Engine & Process Timeline"); title.setObjectName("PageTitle"); root.addWidget(title); root.addWidget(QLabel("Auditable local timeline for process, camera, quality, operator and system events."))
        row=QHBoxLayout(); self.type=QLineEdit("OPERATOR_NOTE"); self.type.setPlaceholderText("Event type"); self.sev=QComboBox(); self.sev.addItems(SEVERITIES); self.source=QLineEdit("Operator"); self.message=QLineEdit(); self.message.setPlaceholderText("Event message"); add=QPushButton("Record Event"); add.clicked.connect(self.add); row.addWidget(self.type); row.addWidget(self.sev); row.addWidget(self.source); row.addWidget(self.message,1); row.addWidget(add); root.addLayout(row)
        filters=QHBoxLayout(); self.filter=QComboBox(); self.filter.addItems(["All",*SEVERITIES]); refresh=QPushButton("Refresh"); refresh.clicked.connect(self.refresh); self.operator=QLineEdit(); self.operator.setPlaceholderText("Operator for acknowledgement"); ack=QPushButton("Acknowledge Selected"); ack.clicked.connect(self.ack); export=QPushButton("Export Timeline JSON"); export.clicked.connect(self.export); filters.addWidget(QLabel("Severity:")); filters.addWidget(self.filter); filters.addStretch(); filters.addWidget(self.operator); filters.addWidget(ack); filters.addWidget(export); filters.addWidget(refresh); root.addLayout(filters)
        self.table=QTableWidget(0,8); self.table.setHorizontalHeaderLabels(["ID","Time","Severity","Type","Source","Message","Acknowledged","By"]); self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); root.addWidget(self.table,1); self.filter.currentTextChanged.connect(self.refresh); self.refresh()
    def add(self):
        try: record_event(ProcessEvent(event_type=self.type.text().strip(),severity=self.sev.currentText(),source=self.source.text().strip() or "Operator",message=self.message.text().strip())); self.message.clear(); self.refresh()
        except Exception as e: QMessageBox.warning(self,"Invalid event",str(e))
    def refresh(self):
        sev=None if self.filter.currentText()=="All" else self.filter.currentText(); rows=list_events(severity=sev); self.rows=rows; self.table.setRowCount(len(rows))
        for i,e in enumerate(rows):
            vals=[e.event_id,e.created_at,e.severity,e.event_type,e.source,e.message,"Yes" if e.acknowledged else "No",e.acknowledged_by]
            for j,v in enumerate(vals): self.table.setItem(i,j,QTableWidgetItem(str(v)))
        self.table.resizeColumnsToContents()
    def selected(self):
        r=self.table.currentRow(); return int(self.table.item(r,0).text()) if r>=0 else None
    def ack(self):
        i=self.selected()
        if i is None: return
        try: acknowledge_event(i,self.operator.text()); self.refresh()
        except Exception as e: QMessageBox.warning(self,"Cannot acknowledge",str(e))
    def export(self):
        path,_=QFileDialog.getSaveFileName(self,"Export event timeline","visionqc_event_timeline.json","JSON (*.json)")
        if path:
            from pathlib import Path
            Path(path).write_text(json.dumps(events_to_timeline(self.rows),ensure_ascii=False,indent=2),encoding="utf-8")
