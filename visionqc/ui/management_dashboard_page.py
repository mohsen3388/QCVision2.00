from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (QComboBox,QDateEdit,QFileDialog,QFrame,QGridLayout,QHBoxLayout,QLabel,QMessageBox,QPushButton,QTableWidget,QTableWidgetItem,QVBoxLayout,QWidget)

from visionqc.core.analytics import DashboardFilter, build_dashboard, distinct_filter_values, export_dashboard_csv, export_dashboard_json
from visionqc.core.settings import load_settings


class BarChart(QWidget):
    def __init__(self):
        super().__init__(); self.data=[]; self.setMinimumHeight(220)
    def set_data(self,data): self.data=data[:10]; self.update()
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        rect=self.rect().adjusted(45,20,-20,-35); p.drawRect(rect)
        if not self.data: p.drawText(rect,Qt.AlignCenter,"No data for selected filters"); return
        maximum=max(float(v) for _,v in self.data) or 1; width=max(18,rect.width()//max(1,len(self.data)*2))
        for i,(label,value) in enumerate(self.data):
            x=rect.left()+int((i+0.5)*rect.width()/len(self.data))-width//2
            h=int(float(value)/maximum*(rect.height()-25)); y=rect.bottom()-h
            p.fillRect(x,y,width,h,self.palette().highlight())
            p.drawText(x-20,rect.bottom()+5,width+40,25,Qt.AlignHCenter|Qt.AlignTop,str(label)[:12])
            p.drawText(x-10,y-20,width+20,18,Qt.AlignCenter,str(value))


class KpiCard(QFrame):
    def __init__(self,title):
        super().__init__(); self.setObjectName("Card"); box=QVBoxLayout(self); self.title=QLabel(title); self.value=QLabel("—"); self.value.setStyleSheet("font-size:26px;font-weight:700"); box.addWidget(self.title); box.addWidget(self.value)


class ManagementDashboardPage(QWidget):
    def __init__(self):
        super().__init__(); self.snapshot=None
        root=QVBoxLayout(self); title=QLabel("Management Dashboard"); title.setObjectName("PageTitle"); root.addWidget(title)
        subtitle=QLabel("Offline operational KPIs for batches, quality outcomes, lines, operators and process events."); subtitle.setWordWrap(True); root.addWidget(subtitle)
        filters=QHBoxLayout(); self.start=QDateEdit(); self.start.setCalendarPopup(True); self.start.setSpecialValueText("From date"); self.start.setDate(self.start.minimumDate())
        self.end=QDateEdit(); self.end.setCalendarPopup(True); self.end.setSpecialValueText("To date"); self.end.setDate(self.end.minimumDate())
        self.product=QComboBox(); self.line=QComboBox(); self.operator=QComboBox()
        for label,w in (("From",self.start),("To",self.end),("Product",self.product),("Line",self.line),("Operator",self.operator)): filters.addWidget(QLabel(label)); filters.addWidget(w)
        apply=QPushButton("Apply Filters"); clear=QPushButton("Clear"); apply.clicked.connect(self.refresh); clear.clicked.connect(self.clear_filters); filters.addWidget(apply); filters.addWidget(clear); root.addLayout(filters)
        grid=QGridLayout(); self.cards={}
        for i,(key,label) in enumerate((("total","Total Batches"),("accepted","Accepted"),("rejected","Rejected"),("rate","Acceptance Rate"),("open","Open"),("duration","Avg Duration"),("warnings","Warnings"),("critical","Critical Events"))):
            card=KpiCard(label); self.cards[key]=card; grid.addWidget(card,i//4,i%4)
        root.addLayout(grid)
        self.chart=BarChart(); root.addWidget(QLabel("Daily batch volume")); root.addWidget(self.chart)
        tables=QHBoxLayout(); self.product_table=self._table(["Product","Count","Percent"]); self.line_table=self._table(["Line","Count","Percent"]); self.event_table=self._table(["Event Type","Count"])
        tables.addWidget(self.product_table); tables.addWidget(self.line_table); tables.addWidget(self.event_table); root.addLayout(tables)
        actions=QHBoxLayout(); export_csv=QPushButton("Export CSV"); export_json=QPushButton("Export JSON"); export_csv.clicked.connect(self._csv); export_json.clicked.connect(self._json); actions.addStretch(); actions.addWidget(export_csv); actions.addWidget(export_json); root.addLayout(actions)
        self._load_filters(); self.refresh()
    def _table(self,headers):
        t=QTableWidget(0,len(headers)); t.setHorizontalHeaderLabels(headers); t.horizontalHeader().setStretchLastSection(True); return t
    def _load_filters(self):
        values=distinct_filter_values()
        for combo,key in ((self.product,"products"),(self.line,"lines"),(self.operator,"operators")):
            combo.clear(); combo.addItem("All",None)
            for value in values[key]: combo.addItem(value,value)
    def _date_value(self,w): return None if w.date()==w.minimumDate() else w.date().toString("yyyy-MM-dd")
    def clear_filters(self):
        self.start.setDate(self.start.minimumDate()); self.end.setDate(self.end.minimumDate()); self.product.setCurrentIndex(0); self.line.setCurrentIndex(0); self.operator.setCurrentIndex(0); self.refresh()
    def refresh(self):
        f=DashboardFilter(self._date_value(self.start),self._date_value(self.end),self.product.currentData(),self.line.currentData(),self.operator.currentData())
        self.snapshot=build_dashboard(f); s=self.snapshot
        vals={"total":s.total_batches,"accepted":s.accepted_batches,"rejected":s.rejected_batches,"rate":f"{s.acceptance_rate:.1f}%","open":s.open_batches,"duration":"—" if s.average_duration_minutes is None else f"{s.average_duration_minutes:.1f} min","warnings":s.warning_events,"critical":s.critical_events}
        for k,v in vals.items(): self.cards[k].value.setText(str(v))
        self.chart.set_data([(r["date"][5:],r["total"]) for r in s.by_day])
        self._fill(self.product_table,s.by_product,("product","count","percent")); self._fill(self.line_table,s.by_line,("line","count","percent")); self._fill(self.event_table,s.top_event_types,("event_type","count"))
    def _fill(self,t,rows,keys):
        t.setRowCount(len(rows))
        for i,row in enumerate(rows):
            for j,key in enumerate(keys): t.setItem(i,j,QTableWidgetItem(str(row.get(key,""))+("%" if key=="percent" else "")))
    def _csv(self): self._export("csv")
    def _json(self): self._export("json")
    def _export(self,kind):
        if not self.snapshot: return
        directory=Path(load_settings()["reports_directory"]); default=directory/f"VisionQC_Dashboard.{kind}"
        path,_=QFileDialog.getSaveFileName(self,"Export Dashboard",str(default),"CSV (*.csv)" if kind=="csv" else "JSON (*.json)")
        if path:
            (export_dashboard_csv if kind=="csv" else export_dashboard_json)(self.snapshot,path); QMessageBox.information(self,"Export complete",f"Dashboard exported to:\n{path}")
