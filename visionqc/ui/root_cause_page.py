from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget, QLineEdit)

from visionqc.application.services.factory_memory_service import FactoryMemoryService
from visionqc.application.services.root_cause_service import RootCauseIntelligenceService


class RootCausePage(QWidget):
    def __init__(self, service: RootCauseIntelligenceService, memory: FactoryMemoryService) -> None:
        super().__init__(); self.service=service; self.memory=memory; self._ids=[]; self._build(); self.refresh_cases()

    def _build(self):
        layout=QVBoxLayout(self)
        title=QLabel("Root Cause Intelligence"); title.setObjectName("pageTitle")
        sub=QLabel("Explainable evidence-weighted hypotheses from QC-verified Factory Memory. VisionQC does not automatically confirm a root cause."); sub.setWordWrap(True)
        layout.addWidget(title); layout.addWidget(sub)
        controls=QHBoxLayout(); self.case_combo=QComboBox(); self.case_combo.setMinimumWidth(560)
        run=QPushButton("Analyze Selected Case"); run.clicked.connect(self.analyze)
        refresh=QPushButton("Refresh Cases"); refresh.clicked.connect(self.refresh_cases)
        controls.addWidget(QLabel("Factory Memory case:")); controls.addWidget(self.case_combo,1); controls.addWidget(run); controls.addWidget(refresh); layout.addLayout(controls)
        self.summary=QLabel("Select a rejected case and run analysis."); self.summary.setWordWrap(True); layout.addWidget(self.summary)
        self.table=QTableWidget(0,5); self.table.setHorizontalHeaderLabels(["Rank","Hypothesis","Confidence","Score","Verified cases"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows); self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch); self.table.itemSelectionChanged.connect(self._show_detail)
        layout.addWidget(self.table,1)
        verify_row=QHBoxLayout(); self.qc_user=QLineEdit(); self.qc_user.setPlaceholderText("نام مسئول QC")
        self.qc_notes=QLineEdit(); self.qc_notes.setPlaceholderText("یادداشت تأیید علت")
        confirm=QPushButton("تأیید علت انتخاب‌شده توسط QC"); confirm.clicked.connect(self.confirm_selected)
        verify_row.addWidget(QLabel("تأیید انسانی:")); verify_row.addWidget(self.qc_user); verify_row.addWidget(self.qc_notes,1); verify_row.addWidget(confirm); layout.addLayout(verify_row)
        box=QGroupBox("Evidence, limitations and recommended checks"); v=QVBoxLayout(box); self.detail=QTextEdit(); self.detail.setReadOnly(True); v.addWidget(self.detail); layout.addWidget(box,1)
        self._analysis=None

    def refresh_cases(self):
        self.case_combo.clear(); self._ids=[]
        for case in self.memory.list_recent(300):
            if case.passed: continue
            cid=self._resolve_id(case.case_uuid)
            if cid is None: continue
            self._ids.append(cid); defects=", ".join(d.defect_type for d in case.defects) or "no defect"
            self.case_combo.addItem(f"#{cid} | {case.product_name} | {defects} | {case.created_at[:19]}")

    def _resolve_id(self, uuid):
        repo=getattr(self.memory,"_repository",None)
        if repo is None: return None
        try:
            from visionqc.core.database import connect
            with connect() as conn:
                row=conn.execute("SELECT id FROM factory_memory_cases WHERE case_uuid=?",(uuid,)).fetchone()
                return int(row[0]) if row else None
        except Exception: return None

    def analyze(self):
        i=self.case_combo.currentIndex()
        if i<0 or i>=len(self._ids): QMessageBox.information(self,"Root Cause","No rejected Factory Memory case is available."); return
        try: self._analysis=self.service.analyze(self._ids[i],limit=7)
        except Exception as exc: QMessageBox.critical(self,"Root Cause",str(exc)); return
        self.table.setRowCount(len(self._analysis.hypotheses))
        for row,h in enumerate(self._analysis.hypotheses):
            vals=[str(row+1),h.cause,str(h.confidence),f"{h.score*100:.1f}%",str(h.verified_case_count)]
            for col,val in enumerate(vals):
                item=QTableWidgetItem(val); item.setTextAlignment(Qt.AlignCenter if col!=1 else Qt.AlignLeft|Qt.AlignVCenter); self.table.setItem(row,col,item)
        top=self._analysis.top_hypothesis
        self.summary.setText(f"Leading hypothesis: {top.cause} — {top.score*100:.1f}% ({top.confidence}). QC verification is required." if top else "No hypothesis generated.")
        if self.table.rowCount(): self.table.selectRow(0)

    def _show_detail(self):
        if self._analysis is None: return
        row=self.table.currentRow()
        if row<0 or row>=len(self._analysis.hypotheses): return
        h=self._analysis.hypotheses[row]
        lines=[f"HYPOTHESIS\n{h.cause}",f"\nCONFIDENCE\n{h.confidence} — {h.score*100:.1f}%",f"\nSUPPORTING EVIDENCE ({len(h.supporting_evidence)})"]
        for e in h.supporting_evidence: lines.append(f"• {e.signal}: {e.explanation} [contribution {e.contribution:.3f}]")
        if h.opposing_evidence:
            lines.append("\nLIMITATIONS / OPPOSING EVIDENCE"); lines.extend(f"• {x}" for x in h.opposing_evidence)
        lines.append("\nRECOMMENDED CHECKS"); lines.extend(f"{i+1}. {a}" for i,a in enumerate(h.recommended_actions or ["Escalate to qualified QC/process engineering"]))
        lines.append("\nSAFETY NOTE\n"+self._analysis.safety_note)
        self.detail.setPlainText("\n".join(lines))

    def confirm_selected(self):
        if self._analysis is None:
            QMessageBox.information(self,"Root Cause","ابتدا تحلیل علت را اجرا کنید."); return
        row=self.table.currentRow()
        if row<0 or row>=len(self._analysis.hypotheses):
            QMessageBox.information(self,"Root Cause","یک فرضیه را انتخاب کنید."); return
        user=self.qc_user.text().strip()
        if not user:
            QMessageBox.warning(self,"Root Cause","نام مسئول QC الزامی است."); return
        idx=self.case_combo.currentIndex()
        if idx<0 or idx>=len(self._ids): return
        cause=self._analysis.hypotheses[row].cause
        try:
            self.memory.confirm_root_cause(self._ids[idx],cause,qc_user=user,notes=self.qc_notes.text().strip())
        except Exception as exc:
            QMessageBox.critical(self,"Root Cause",str(exc)); return
        QMessageBox.information(self,"Root Cause",f"علت «{cause}» توسط {user} تأیید و وارد حافظه کارخانه شد.")
        self.refresh_cases()
