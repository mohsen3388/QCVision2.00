from __future__ import annotations
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTableWidget,QTableWidgetItem,QHeaderView,QInputDialog,QMessageBox,QTabWidget
from visionqc.domain.industrial_automation import ActionKind

class IndustrialAutomationPage(QWidget):
    def __init__(self,service):
        super().__init__(); self.service=service
        root=QVBoxLayout(self); title=QLabel("Industrial Automation"); title.setObjectName("PageTitle"); root.addWidget(title)
        root.addWidget(QLabel("Fail-safe event workflows with human approval. VisionQC does not directly control PLCs, recipes or machine settings."))
        tabs=QTabWidget(); root.addWidget(tabs,1)
        self.rules=QTableWidget(0,6); self.rules.setHorizontalHeaderLabels(["ID","Rule","Event","Action","Approval","Enabled"]); self.rules.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch); tabs.addTab(self.rules,"Rules")
        self.executions=QTableWidget(0,6); self.executions.setHorizontalHeaderLabels(["Execution","Rule","Event","Action","Status","Message"]); self.executions.horizontalHeader().setSectionResizeMode(5,QHeaderView.Stretch); tabs.addTab(self.executions,"Executions")
        self.tasks=QTableWidget(0,6); self.tasks.setHorizontalHeaderLabels(["Task","Title","Owner","Priority","Source","Status"]); self.tasks.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch); tabs.addTab(self.tasks,"Tasks")
        row=QHBoxLayout();
        for text,fn in [("Create safe rule",self.create_rule),("Enable/disable",self.toggle_rule),("Simulate selected",self.simulate),("Approve selected execution",self.approve),("Refresh",self.refresh)]: b=QPushButton(text); b.clicked.connect(fn); row.addWidget(b)
        row.addStretch(); root.addLayout(row); self.refresh()
    def refresh(self):
        rules=self.service.list_rules(); self.rules.setRowCount(len(rules))
        for r,x in enumerate(rules):
            for c,v in enumerate([x.rule_id,x.name,x.event_name,x.action_kind.value,"Yes" if x.requires_approval else "No","Yes" if x.enabled else "No"]): self.rules.setItem(r,c,QTableWidgetItem(str(v)))
        ex=self.service.list_executions(); self.executions.setRowCount(len(ex))
        for r,x in enumerate(ex):
            for c,k in enumerate(["execution_id","rule_id","event_name","action_kind","status","message"]): self.executions.setItem(r,c,QTableWidgetItem(str(x[k])))
        tasks=self.service.list_tasks(); self.tasks.setRowCount(len(tasks))
        for r,x in enumerate(tasks):
            for c,k in enumerate(["task_id","title","owner_role","priority","source_event","status"]): self.tasks.setItem(r,c,QTableWidgetItem(str(x[k])))
    def create_rule(self):
        name,ok=QInputDialog.getText(self,"New automation rule","Rule name:");
        if not ok or not name.strip(): return
        event,ok=QInputDialog.getItem(self,"Trigger event","Event:",sorted(self.service.SAFE_EVENTS),0,False);
        if not ok:return
        action,ok=QInputDialog.getItem(self,"Safe action","Action:",[x.value for x in ActionKind],0,False);
        if not ok:return
        self.service.create_rule(name.strip(),event,action,requires_approval=True,action_config={"title":name.strip(),"owner_role":"QC","priority":"High"}); self.refresh()
    def toggle_rule(self):
        r=self.rules.currentRow();
        if r<0:return
        self.service.set_enabled(self.rules.item(r,0).text(),self.rules.item(r,5).text()!="Yes"); self.refresh()
    def simulate(self):
        r=self.rules.currentRow();
        if r<0:return
        try:self.service.simulate(self.rules.item(r,0).text(),{"risk":"High","simulation":True}); self.refresh()
        except Exception as exc: QMessageBox.critical(self,"Simulation",str(exc))
    def approve(self):
        r=self.executions.currentRow();
        if r<0:return
        try:self.service.approve(self.executions.item(r,0).text()); self.refresh()
        except Exception as exc: QMessageBox.critical(self,"Approval",str(exc))
