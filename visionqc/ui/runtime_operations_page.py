
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QComboBox,QTableWidget,QTableWidgetItem,QHeaderView,QMessageBox,QInputDialog,QTextEdit,QSplitter,QDoubleSpinBox
from visionqc.configuration.repository import ConfigurationRepository
from visionqc.configuration.runtime_repository import RuntimeRepository
from visionqc.configuration.production_runtime import ProductionRuntimeEngine
from visionqc.configuration.monitor_worker import RuntimeMonitorWorker
from visionqc.multicamera.models import CameraRegistry

class RuntimeOperationsPage(QWidget):
    def __init__(self):
        super().__init__(); self.config=ConfigurationRepository(); self.repo=RuntimeRepository(); self.cameras=CameraRegistry(); self.engine=ProductionRuntimeEngine(self.config,self.repo,self._action); self.workers={}; self._build(); self.refresh()
    def _build(self):
        root=QVBoxLayout(self); title=QLabel('مرکز عملیات Runtime — پایش عملیاتی VisionQC 3.0'); title.setObjectName('PageTitle'); root.addWidget(title)
        sub=QLabel('الگوی آشنا برای کاربران Zabbix: Host/Camera ← Template Assignment ← Item History ← Trigger ← Problem/Event ← Action/Acknowledge'); sub.setObjectName('PageSubtitle'); root.addWidget(sub)
        bar=QHBoxLayout(); self.cam=QComboBox(); self.tpl=QComboBox(); self.interval=QDoubleSpinBox(); self.interval.setRange(.5,60); self.interval.setValue(2); self.interval.setSuffix(' ثانیه')
        for label,w in [('دوربین:',self.cam),('Template Production:',self.tpl),('نمونه‌برداری:',self.interval)]: bar.addWidget(QLabel(label)); bar.addWidget(w)
        self.assign_btn=QPushButton('Assign Template'); self.start_btn=QPushButton('Start Monitoring'); self.stop_btn=QPushButton('Stop'); self.refresh_btn=QPushButton('Refresh')
        for b in (self.assign_btn,self.start_btn,self.stop_btn,self.refresh_btn):bar.addWidget(b)
        root.addLayout(bar)
        split=QSplitter(Qt.Orientation.Vertical)
        self.assignments=QTableWidget(0,12); self.assignments.setHorizontalHeaderLabels(['Host/Camera','Source','Template','Interval','State','Final','Product','Process','FPS','Last Frame','Reconnects','Backend']); self.assignments.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); self.assignments.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.events=QTableWidget(0,8); self.events.setHorizontalHeaderLabels(['Event','Camera','Trigger','Severity','State','Problem','Opened','Ack By']); self.events.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); self.events.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        split.addWidget(self.assignments); split.addWidget(self.events); root.addWidget(split,1)
        tools=QHBoxLayout(); self.ack_btn=QPushButton('Acknowledge Event'); self.diag_btn=QPushButton('Runtime Diagnostics'); tools.addWidget(self.ack_btn); tools.addWidget(self.diag_btn); tools.addStretch(); root.addLayout(tools)
        self.log=QTextEdit(); self.log.setReadOnly(True); self.log.setMaximumHeight(150); root.addWidget(self.log)
        self.assign_btn.clicked.connect(self.assign); self.start_btn.clicked.connect(self.start); self.stop_btn.clicked.connect(self.stop); self.refresh_btn.clicked.connect(self.refresh); self.ack_btn.clicked.connect(self.ack); self.diag_btn.clicked.connect(self.diagnostics)
    def refresh(self):
        current=self.cam.currentData(); self.cam.clear()
        for c in self.cameras.list(): self.cam.addItem(f'{c.name_fa} — {c.source_type}',c.camera_id)
        if current:
            i=self.cam.findData(current); self.cam.setCurrentIndex(max(0,i))
        self.tpl.clear()
        for t in self.config.list_templates():
            if t.lifecycle=='Production':self.tpl.addItem(f'{t.name_fa} ({t.version})',t.key)
        arr=self.repo.assignments(); self.assignments.setRowCount(len(arr))
        for r,a in enumerate(arr):
            h=self.repo.camera_health(a['camera_id']) or {}; vals=[a['camera_name'],a['source_type'],a['template_key'],a['sampling_seconds'],h.get('state','RUNNING' if a['camera_id'] in self.workers else 'STOPPED'),'—','—','—',h.get('measured_fps','—'),h.get('last_frame_at','—') or '—',h.get('reconnect_count',0),h.get('backend','—') or '—']
            for c,v in enumerate(vals):
                it=QTableWidgetItem(str(v)); it.setData(Qt.ItemDataRole.UserRole,a['camera_id']); self.assignments.setItem(r,c,it)
        ev=self.repo.events(); self.events.setRowCount(len(ev))
        for r,e in enumerate(ev):
            vals=[e['event_key'],e['camera_id'],e['trigger_key'],e['severity'],e['state'],e['problem_text'],e['opened_at'],e['acknowledged_by'] or '—']
            for c,v in enumerate(vals):self.events.setItem(r,c,QTableWidgetItem(str(v)))
    def assign(self):
        cid=self.cam.currentData(); key=self.tpl.currentData(); cam=next((c for c in self.cameras.list() if c.camera_id==cid),None)
        if not cam or not key: QMessageBox.warning(self,'Assignment','دوربین و Template Production را انتخاب کنید.'); return
        self.repo.assign(cam.camera_id,cam.name_fa,cam.source_type,cam.source_value,key,self.interval.value()); self.log.append(f'ASSIGNED {cam.name_fa} -> {key}'); self.refresh()
    def _selected_camera(self):
        r=self.assignments.currentRow(); return None if r<0 or not self.assignments.item(r,0) else self.assignments.item(r,0).data(Qt.ItemDataRole.UserRole)
    def start(self):
        cid=self._selected_camera(); a=self.repo.assignment(cid) if cid else None
        if not a: QMessageBox.information(self,'Runtime','یک Assignment را انتخاب کنید.'); return
        if cid in self.workers:return
        w=RuntimeMonitorWorker(a,self.engine,self); w.sample_ready.connect(lambda x,cid=cid:self._sample(cid,x)); w.failed.connect(lambda x:self.log.append('ERROR: '+x)); w.state_changed.connect(lambda x:self.log.append(f'{cid}: {x}')); w.health_ready.connect(lambda h,cid=cid:self._health(cid,h)); w.finished.connect(lambda cid=cid:self._finished(cid)); self.workers[cid]=w; w.start(); self.refresh()
    def stop(self):
        cid=self._selected_camera(); w=self.workers.get(cid)
        if w:w.stop(); w.wait(3000); self.workers.pop(cid,None); self.refresh()
    def _finished(self,cid): self.workers.pop(cid,None); self.refresh()
    def _health(self,cid,h):
        for row in range(self.assignments.rowCount()):
            if self.assignments.item(row,0).data(Qt.ItemDataRole.UserRole)==cid:
                mapping={4:'state',8:'measured_fps',9:'last_frame_at',10:'reconnect_count',11:'backend'}
                for col,key in mapping.items(): self.assignments.setItem(row,col,QTableWidgetItem(str(h.get(key,'—') or '—')))
                break

    def _sample(self,cid,r):
        for row in range(self.assignments.rowCount()):
            if self.assignments.item(row,0).data(Qt.ItemDataRole.UserRole)==cid:
                for col,key in [(5,'final_score'),(6,'product_health'),(7,'process_health')]:self.assignments.setItem(row,col,QTableWidgetItem(str(r.get(key,'—'))))
        self.log.append(f"{cid}: score={r['final_score']} status={r['status']} events={r['active_events']}"); self.refresh_events_only()
    def refresh_events_only(self):
        ev=self.repo.events(); self.events.setRowCount(len(ev))
        for r,e in enumerate(ev):
            vals=[e['event_key'],e['camera_id'],e['trigger_key'],e['severity'],e['state'],e['problem_text'],e['opened_at'],e['acknowledged_by'] or '—']
            for c,v in enumerate(vals):self.events.setItem(r,c,QTableWidgetItem(str(v)))
    def ack(self):
        r=self.events.currentRow()
        if r<0:return
        key=self.events.item(r,0).text(); user,ok=QInputDialog.getText(self,'Acknowledge','نام تأییدکننده:')
        if ok and user.strip():self.repo.acknowledge(key,user.strip()); self.refresh_events_only()
    def diagnostics(self):
        lines=['Runtime Diagnostics','',f'Assignments: {len(self.repo.assignments())}',f'Active workers: {len(self.workers)}',f'Events: {len(self.repo.events())}',f'Health records: {len(self.repo.camera_health_all())}']
        for a in self.repo.assignments():
            t=self.config.get_template(a['template_key']); h=self.repo.camera_health(a['camera_id']) or {}; lines.append(f"{a['camera_name']}: {'OK' if t and t.lifecycle=='Production' else 'INVALID TEMPLATE'} | edge={h.get('state','NO DATA')} | reconnects={h.get('reconnect_count',0)}")
        self.log.setPlainText('\n'.join(lines))
    def _action(self,event_key,action,step,details):
        self.log.append(f'ACTION {event_key}: {step.action_type} -> {step.target}: {step.message}')
