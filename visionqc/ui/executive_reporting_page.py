from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (QComboBox,QDateEdit,QFileDialog,QGridLayout,QHBoxLayout,QLabel,QMessageBox,QPushButton,QTableWidget,QTableWidgetItem,QVBoxLayout,QWidget)

from visionqc.core.analytics import distinct_filter_values
from visionqc.core.executive_reporting import (ReportFilter,build_executive_snapshot,default_report_path,export_executive_csv,export_executive_json,export_executive_pdf,export_executive_xlsx)


class ExecutiveReportingPage(QWidget):
    def __init__(self):
        super().__init__(); self.snapshot=None
        root=QVBoxLayout(self); title=QLabel("Executive Reporting & KPI Center"); title.setObjectName("PageTitle"); root.addWidget(title)
        sub=QLabel("Daily, shift and management-level quality KPIs with auditable exports to PDF, Excel, CSV and JSON."); sub.setWordWrap(True); root.addWidget(sub)
        filters=QHBoxLayout(); self.start=QDateEdit(); self.start.setCalendarPopup(True); self.start.setSpecialValueText("From date"); self.start.setDate(self.start.minimumDate()); self.end=QDateEdit(); self.end.setCalendarPopup(True); self.end.setSpecialValueText("To date"); self.end.setDate(self.end.minimumDate())
        self.product=QComboBox(); self.line=QComboBox(); self.operator=QComboBox()
        for label,w in (("From",self.start),("To",self.end),("Product",self.product),("Line",self.line),("Operator",self.operator)): filters.addWidget(QLabel(label)); filters.addWidget(w)
        refresh=QPushButton("Refresh KPIs"); refresh.clicked.connect(self.refresh); filters.addWidget(refresh); root.addLayout(filters)
        grid=QGridLayout(); self.cards={}
        labels=(("total","Total Batches"),("accept","Acceptance Rate"),("quality","Average Quality"),("oee","Average OEE"),("open","Open Events"),("critical","Critical Events"),("actions","Action Effectiveness"),("repeat","Repeat Defect Rate"),("camera","Camera Availability"))
        for i,(key,text) in enumerate(labels):
            card=QLabel(f"{text}\n—"); card.setAlignment(Qt.AlignCenter); card.setObjectName("Card"); card.setMinimumHeight(75); grid.addWidget(card,i//3,i%3); self.cards[key]=card
        root.addLayout(grid)
        self.table=QTableWidget(0,6); self.table.setHorizontalHeaderLabels(["Date","Total","Accepted","Rejected","Acceptance %","Events"]); root.addWidget(self.table,1)
        buttons=QHBoxLayout()
        for label,kind in (("Export PDF","pdf"),("Export Excel","xlsx"),("Export CSV","csv"),("Export JSON","json")):
            b=QPushButton(label); b.clicked.connect(lambda checked=False,k=kind:self.export(k)); buttons.addWidget(b)
        buttons.addStretch(); root.addLayout(buttons)
        note=QLabel("KPIs are management decision-support outputs. Laboratory testing, HACCP/food-safety controls and qualified QC approval remain mandatory."); note.setWordWrap(True); root.addWidget(note)
        self.reload_filters(); self.refresh()

    def reload_filters(self):
        values=distinct_filter_values()
        for combo,key in ((self.product,"products"),(self.line,"lines"),(self.operator,"operators")):
            current=combo.currentData(); combo.clear(); combo.addItem("All",None)
            for value in values.get(key,[]): combo.addItem(value,value)
            idx=combo.findData(current)
            if idx>=0: combo.setCurrentIndex(idx)

    def _filter(self):
        def date_value(w): return None if w.date()==w.minimumDate() else w.date().toString("yyyy-MM-dd")
        return ReportFilter(date_value(self.start),date_value(self.end),self.product.currentData(),self.line.currentData(),self.operator.currentData())

    def refresh(self):
        self.reload_filters(); self.snapshot=build_executive_snapshot(self._filter()); s=self.snapshot
        vals={"total":s.total_batches,"accept":f"{s.acceptance_rate:.1f}%","quality":"—" if s.average_quality_score is None else f"{s.average_quality_score:.1f}","oee":"—" if s.average_oee is None else f"{s.average_oee:.1f}%","open":s.open_quality_events,"critical":s.critical_quality_events,"actions":"—" if s.corrective_action_effectiveness is None else f"{s.corrective_action_effectiveness:.1f}%","repeat":"—" if s.repeat_defect_rate is None else f"{s.repeat_defect_rate:.1f}%","camera":"—" if s.camera_availability is None else f"{s.camera_availability:.1f}%"}
        names={"total":"Total Batches","accept":"Acceptance Rate","quality":"Average Quality","oee":"Average OEE","open":"Open Events","critical":"Critical Events","actions":"Action Effectiveness","repeat":"Repeat Defect Rate","camera":"Camera Availability"}
        for k,v in vals.items(): self.cards[k].setText(f"{names[k]}\n{v}")
        self.table.setRowCount(len(s.by_day))
        for r,row in enumerate(s.by_day):
            for c,key in enumerate(("date","total","accepted","rejected","acceptance_rate","events")): self.table.setItem(r,c,QTableWidgetItem(str(row.get(key,""))))
        self.table.resizeColumnsToContents()

    def export(self,kind):
        if self.snapshot is None: self.refresh()
        filters={"pdf":"PDF (*.pdf)","xlsx":"Excel (*.xlsx)","csv":"CSV (*.csv)","json":"JSON (*.json)"}
        default=default_report_path(kind); path,_=QFileDialog.getSaveFileName(self,"Export Executive Report",str(default),filters[kind])
        if not path:return
        try:
            result={"pdf":export_executive_pdf,"xlsx":export_executive_xlsx,"csv":export_executive_csv,"json":export_executive_json}[kind](self.snapshot,path)
        except Exception as exc:
            QMessageBox.critical(self,"Export failed",str(exc)); return
        QMessageBox.information(self,"Export complete",f"Report created:\n{result}"); QDesktopServices.openUrl(QUrl.fromLocalFile(str(result)))
