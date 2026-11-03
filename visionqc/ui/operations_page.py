from __future__ import annotations

from pathlib import Path
from PySide6.QtWidgets import (QComboBox,QDoubleSpinBox,QFileDialog,QFormLayout,QGridLayout,QHBoxLayout,QLabel,QLineEdit,QMessageBox,QPushButton,QSpinBox,QTableWidget,QTableWidgetItem,QTabWidget,QVBoxLayout,QWidget)

from visionqc.core.operations import (add_downtime,calculate_oee,create_production_run,create_shift,export_oee,list_runs,list_shifts,update_run_counts)
from visionqc.core.settings import load_settings


class OEEPage(QWidget):
    def __init__(self):
        super().__init__(); self.snapshot=None
        root=QVBoxLayout(self); title=QLabel('Production Operations & OEE'); title.setObjectName('PageTitle'); root.addWidget(title)
        root.addWidget(QLabel('Define shifts, record production and downtime, and calculate explainable Availability × Performance × Quality.'))
        tabs=QTabWidget(); root.addWidget(tabs)
        shifts=QWidget(); sf=QFormLayout(shifts); self.shift_name=QLineEdit(); self.start=QLineEdit('06:00'); self.end=QLineEdit('14:00'); self.breaks=QSpinBox(); self.breaks.setRange(0,1440)
        for l,w in [('Shift name',self.shift_name),('Start time',self.start),('End time',self.end),('Planned break (min)',self.breaks)]: sf.addRow(l,w)
        b=QPushButton('Create Shift'); b.clicked.connect(self.create_shift); sf.addRow(b); self.shift_table=QTableWidget(0,4); self.shift_table.setHorizontalHeaderLabels(['Name','Start','End','Break']); sf.addRow(self.shift_table); tabs.addTab(shifts,'Shifts')
        run=QWidget(); rf=QFormLayout(run); self.shift=QComboBox(); self.line=QLineEdit(); self.product=QLineEdit(); self.operator=QLineEdit(); self.planned=QDoubleSpinBox(); self.planned.setRange(.1,100000); self.planned.setValue(480); self.cycle=QDoubleSpinBox(); self.cycle.setRange(.001,100000); self.cycle.setValue(10); self.total=QSpinBox(); self.total.setRange(0,100000000); self.good=QSpinBox(); self.good.setRange(0,100000000)
        for l,w in [('Shift',self.shift),('Production line',self.line),('Product',self.product),('Operator',self.operator),('Planned minutes',self.planned),('Ideal cycle seconds',self.cycle),('Total units',self.total),('Good units',self.good)]: rf.addRow(l,w)
        rb=QPushButton('Create Production Run'); rb.clicked.connect(self.create_run); rf.addRow(rb); tabs.addTab(run,'New Run')
        dash=QWidget(); dv=QVBoxLayout(dash); select=QHBoxLayout(); self.run=QComboBox(); refresh=QPushButton('Refresh OEE'); refresh.clicked.connect(self.refresh); select.addWidget(QLabel('Production run')); select.addWidget(self.run,1); select.addWidget(refresh); dv.addLayout(select)
        counts=QHBoxLayout(); self.edit_total=QSpinBox(); self.edit_total.setRange(0,100000000); self.edit_good=QSpinBox(); self.edit_good.setRange(0,100000000); save=QPushButton('Update Counts'); save.clicked.connect(lambda:self.update_counts(False)); finish=QPushButton('Finish Run'); finish.clicked.connect(lambda:self.update_counts(True)); counts.addWidget(QLabel('Total')); counts.addWidget(self.edit_total); counts.addWidget(QLabel('Good')); counts.addWidget(self.edit_good); counts.addWidget(save); counts.addWidget(finish); dv.addLayout(counts)
        dt=QHBoxLayout(); self.reason=QLineEdit(); self.category=QComboBox(); self.category.addItems(['Unplanned','Planned','Changeover','Maintenance','Material','Quality']); self.duration=QDoubleSpinBox(); self.duration.setRange(.01,100000); add=QPushButton('Add Downtime'); add.clicked.connect(self.add_downtime); dt.addWidget(QLabel('Reason')); dt.addWidget(self.reason,1); dt.addWidget(self.category); dt.addWidget(QLabel('Minutes')); dt.addWidget(self.duration); dt.addWidget(add); dv.addLayout(dt)
        grid=QGridLayout(); self.cards={}
        for i,(k,l) in enumerate([('availability','Availability'),('performance','Performance'),('quality','Quality'),('oee','OEE'),('planned','Planned min'),('downtime','Downtime min'),('operating','Operating min'),('rejects','Rejected')]):
            box=QWidget(); lay=QVBoxLayout(box); lay.addWidget(QLabel(l)); val=QLabel('—'); val.setStyleSheet('font-size:24px;font-weight:700'); lay.addWidget(val); self.cards[k]=val; grid.addWidget(box,i//4,i%4)
        dv.addLayout(grid); self.dt_table=QTableWidget(0,3); self.dt_table.setHorizontalHeaderLabels(['Reason','Category','Minutes']); dv.addWidget(self.dt_table)
        ex=QHBoxLayout(); csv=QPushButton('Export CSV'); csv.clicked.connect(lambda:self.export('csv')); js=QPushButton('Export JSON'); js.clicked.connect(lambda:self.export('json')); ex.addStretch(); ex.addWidget(csv); ex.addWidget(js); dv.addLayout(ex); tabs.addTab(dash,'OEE Dashboard')
        self.reload()
    def create_shift(self):
        try: create_shift(self.shift_name.text(),self.start.text(),self.end.text(),self.breaks.value())
        except Exception as e: QMessageBox.warning(self,'Cannot create shift',str(e)); return
        self.shift_name.clear(); self.reload()
    def create_run(self):
        try: rid=create_production_run(shift_id=self.shift.currentData(),production_line=self.line.text(),product_name=self.product.text(),operator_name=self.operator.text(),planned_minutes=self.planned.value(),ideal_cycle_seconds=self.cycle.value(),total_units=self.total.value(),good_units=self.good.value())
        except Exception as e: QMessageBox.warning(self,'Cannot create run',str(e)); return
        self.reload(); idx=self.run.findData(rid); self.run.setCurrentIndex(idx); self.refresh()
    def add_downtime(self):
        if self.run.currentData() is None:return
        try:add_downtime(self.run.currentData(),self.reason.text(),self.duration.value(),self.category.currentText())
        except Exception as e: QMessageBox.warning(self,'Cannot add downtime',str(e)); return
        self.reason.clear(); self.refresh()
    def update_counts(self,finish):
        if self.run.currentData() is None:return
        try:update_run_counts(self.run.currentData(),self.edit_total.value(),self.edit_good.value(),finish)
        except Exception as e: QMessageBox.warning(self,'Invalid counts',str(e)); return
        self.reload(); self.refresh()
    def reload(self):
        shifts=list_shifts(); self.shift.clear(); self.shift_table.setRowCount(len(shifts))
        for i,s in enumerate(shifts):
            self.shift.addItem(s['name'],s['id'])
            for j,v in enumerate([s['name'],s['start_time'],s['end_time'],s['planned_break_minutes']]):self.shift_table.setItem(i,j,QTableWidgetItem(str(v)))
        current=self.run.currentData(); self.run.clear()
        for r in list_runs():self.run.addItem(f"#{r['id']} {r['shift_name']} — {r['production_line']} — {r['product_name']} ({r['status']})",r['id'])
        if current is not None:
            idx=self.run.findData(current)
            if idx>=0:self.run.setCurrentIndex(idx)
    def refresh(self):
        rid=self.run.currentData()
        if rid is None:return
        self.snapshot=calculate_oee(rid); s=self.snapshot
        vals={'availability':f'{s.availability:.1%}','performance':f'{s.performance:.1%}','quality':f'{s.quality:.1%}','oee':f'{s.oee:.1%}','planned':s.planned_minutes,'downtime':s.downtime_minutes,'operating':s.operating_minutes,'rejects':s.rejected_units}
        for k,v in vals.items():self.cards[k].setText(str(v))
        self.edit_total.setValue(s.total_units); self.edit_good.setValue(s.good_units); self.dt_table.setRowCount(len(s.downtime_by_reason))
        for i,r in enumerate(s.downtime_by_reason):
            for j,v in enumerate([r['reason'],r['category'],r['minutes']]):self.dt_table.setItem(i,j,QTableWidgetItem(str(v)))
    def export(self,kind):
        if not self.snapshot:return
        default=Path(load_settings()['reports_directory'])/f'OEE_Run_{self.snapshot.run_id}.{kind}'; path,_=QFileDialog.getSaveFileName(self,'Export OEE',str(default),f'{kind.upper()} (*.{kind})')
        if path:export_oee(self.snapshot,path); QMessageBox.information(self,'Export complete',path)
