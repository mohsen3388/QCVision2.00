from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import (QComboBox,QDoubleSpinBox,QFileDialog,QFormLayout,QFrame,QGridLayout,QHBoxLayout,QLabel,QLineEdit,QMessageBox,QPushButton,QSpinBox,QTableWidget,QTableWidgetItem,QVBoxLayout,QWidget)

from visionqc.core.database import list_batches
from visionqc.core.settings import load_settings
from visionqc.core.spc import add_measurement, build_spc, export_spc_csv, list_metric_names


class ControlChart(QWidget):
    def __init__(self): super().__init__(); self.snapshot=None; self.setMinimumHeight(280)
    def set_snapshot(self,s): self.snapshot=s; self.update()
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing); r=self.rect().adjusted(55,20,-25,-35); p.drawRect(r)
        s=self.snapshot
        if not s or not s.measurements: p.drawText(r,Qt.AlignCenter,"No measurements for this metric"); return
        values=[x['value'] for x in s.measurements]; refs=[x for x in (s.ucl,s.lcl,s.usl,s.lsl) if x is not None]
        lo=min(values+refs); hi=max(values+refs); pad=(hi-lo)*.1 or 1; lo-=pad; hi+=pad
        def y(v): return r.bottom()-int((v-lo)/(hi-lo)*r.height())
        def line(value,label):
            if value is None:return
            yy=y(value); p.setPen(QPen(self.palette().mid().color(),1,Qt.DashLine)); p.drawLine(r.left(),yy,r.right(),yy); p.drawText(r.left()+4,yy-3,f"{label} {value:.3f}")
        for value,label in ((s.ucl,'UCL'),(s.center_line,'CL'),(s.lcl,'LCL'),(s.usl,'USL'),(s.lsl,'LSL')): line(value,label)
        p.setPen(QPen(self.palette().highlight().color(),2)); points=[]
        for i,v in enumerate(values):
            x=r.left()+int(i*r.width()/max(1,len(values)-1)); points.append((x,y(v)))
        for a,b in zip(points,points[1:]): p.drawLine(a[0],a[1],b[0],b[1])
        for x,yy in points: p.drawEllipse(x-3,yy-3,6,6)


class Card(QFrame):
    def __init__(self,title): super().__init__(); self.setObjectName('Card'); b=QVBoxLayout(self); b.addWidget(QLabel(title)); self.value=QLabel('—'); self.value.setStyleSheet('font-size:22px;font-weight:700'); b.addWidget(self.value)


class SPCPage(QWidget):
    def __init__(self):
        super().__init__(); self.snapshot=None
        root=QVBoxLayout(self); title=QLabel('Statistical Process Control'); title.setObjectName('PageTitle'); root.addWidget(title)
        root.addWidget(QLabel('Record quality measurements, monitor control limits and assess process capability. Decision support only.'))
        top=QHBoxLayout(); form=QFormLayout(); self.batch=QComboBox(); self.metric=QComboBox(); self.metric.setEditable(True); self.group=QLineEdit('Quality'); self.unit=QLineEdit(); self.value=QDoubleSpinBox(); self.value.setRange(-1e9,1e9); self.value.setDecimals(6)
        self.target=QDoubleSpinBox(); self.lsl=QDoubleSpinBox(); self.usl=QDoubleSpinBox()
        for w in (self.target,self.lsl,self.usl): w.setRange(-1e9,1e9); w.setDecimals(6); w.setSpecialValueText('Not set'); w.setMinimum(-1e9); w.setValue(-1e9)
        self.product=QLineEdit(); self.line=QLineEdit(); self.notes=QLineEdit()
        for label,w in [('Batch',self.batch),('Metric',self.metric),('Group',self.group),('Value',self.value),('Unit',self.unit),('Target',self.target),('LSL',self.lsl),('USL',self.usl),('Product',self.product),('Line',self.line),('Notes',self.notes)]: form.addRow(label,w)
        add=QPushButton('Add Measurement'); add.clicked.connect(self.add); form.addRow(add); top.addLayout(form,1)
        right=QVBoxLayout(); select=QHBoxLayout(); self.analysis_metric=QComboBox(); self.analysis_metric.setEditable(True); refresh=QPushButton('Analyze'); refresh.clicked.connect(self.refresh); select.addWidget(QLabel('Metric')); select.addWidget(self.analysis_metric,1); select.addWidget(refresh); right.addLayout(select)
        grid=QGridLayout(); self.cards={}
        for i,(key,label) in enumerate([('n','Points'),('mean','Mean'),('sigma','Sigma'),('cp','Cp'),('cpk','Cpk'),('ooc','Out of Control'),('oos','Out of Spec'),('trend','Trend Alerts')]): c=Card(label); self.cards[key]=c; grid.addWidget(c,i//4,i%4)
        right.addLayout(grid); self.chart=ControlChart(); right.addWidget(self.chart); top.addLayout(right,3); root.addLayout(top)
        self.table=QTableWidget(0,7); self.table.setHorizontalHeaderLabels(['#','Time','Value','Batch','Product','Line','Status']); self.table.horizontalHeader().setStretchLastSection(True); root.addWidget(self.table)
        actions=QHBoxLayout(); export=QPushButton('Export SPC CSV'); export.clicked.connect(self.export); actions.addStretch(); actions.addWidget(export); root.addLayout(actions)
        self.reload_sources(); self.refresh()
    def _optional(self,w): return None if w.value()==w.minimum() else w.value()
    def reload_sources(self):
        self.batch.clear(); self.batch.addItem('No batch',None)
        for b in list_batches(500): self.batch.addItem(f"{b['batch_code']} — {b['product_name']}",int(b['id']))
        names=list_metric_names(); current=self.analysis_metric.currentText(); self.analysis_metric.clear(); self.analysis_metric.addItems(names); self.metric.clear(); self.metric.addItems(names)
        if current:self.analysis_metric.setCurrentText(current)
    def add(self):
        name=self.metric.currentText().strip()
        if not name: QMessageBox.warning(self,'Metric required','Enter a metric name.'); return
        try:
            add_measurement(metric_name=name,value=self.value.value(),metric_group=self.group.text(),unit=self.unit.text(),batch_id=self.batch.currentData(),product_name=self.product.text() or None,production_line=self.line.text() or None,target=self._optional(self.target),lsl=self._optional(self.lsl),usl=self._optional(self.usl),notes=self.notes.text())
        except ValueError as e: QMessageBox.warning(self,'Invalid measurement',str(e)); return
        self.analysis_metric.setCurrentText(name); self.reload_sources(); self.analysis_metric.setCurrentText(name); self.refresh()
    def refresh(self):
        name=self.analysis_metric.currentText().strip()
        self.snapshot=build_spc(name) if name else None; s=self.snapshot; self.chart.set_snapshot(s)
        vals={'n':s.count if s else 0,'mean':self._fmt(s.mean if s else None),'sigma':self._fmt(s.sigma if s else None),'cp':self._fmt(s.cp if s else None),'cpk':self._fmt(s.cpk if s else None),'ooc':s.out_of_control if s else 0,'oos':s.out_of_spec if s else 0,'trend':s.trend_warnings if s else 0}
        for k,v in vals.items(): self.cards[k].value.setText(str(v))
        rows=s.measurements if s else []; self.table.setRowCount(len(rows))
        for i,r in enumerate(rows):
            for j,v in enumerate([r['sequence'],r['captured_at'],r['value'],r['batch_id'] or '',r['product_name'] or '',r['production_line'] or '',r['status']]): self.table.setItem(i,j,QTableWidgetItem(str(v)))
    def _fmt(self,v): return '—' if v is None else f'{v:.4f}'
    def export(self):
        if not self.snapshot or not self.snapshot.count: QMessageBox.information(self,'No data','There is no SPC data to export.'); return
        default=Path(load_settings()['reports_directory'])/f"SPC_{self.snapshot.metric_name}.csv"; path,_=QFileDialog.getSaveFileName(self,'Export SPC',str(default),'CSV (*.csv)')
        if path: export_spc_csv(self.snapshot,path); QMessageBox.information(self,'Export complete',f'Exported to:\n{path}')
