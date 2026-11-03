from __future__ import annotations
from PySide6.QtWidgets import QComboBox,QFormLayout,QHBoxLayout,QHeaderView,QInputDialog,QLabel,QLineEdit,QMessageBox,QPushButton,QTableWidget,QTableWidgetItem,QTabWidget,QVBoxLayout,QWidget

class EnterpriseIntegrationPage(QWidget):
    def __init__(self,service,rest_server) -> None:
        super().__init__(); self.service=service; self.rest_server=rest_server
        root=QVBoxLayout(self); title=QLabel("Enterprise Integration Hub"); title.setObjectName("PageTitle"); root.addWidget(title)
        root.addWidget(QLabel("Offline-first connector health, secured REST access, API keys and auditable enterprise exchange."))
        self.summary=QLabel("Not checked"); self.summary.setObjectName("SectionTitle"); root.addWidget(self.summary)
        tabs=QTabWidget(); root.addWidget(tabs,1)
        self.connectors=QTableWidget(0,6); self.connectors.setHorizontalHeaderLabels(["Connector","Type","State","Latency","Message","Metadata"]); self.connectors.horizontalHeader().setSectionResizeMode(4,QHeaderView.Stretch); tabs.addTab(self.connectors,"Connectors")
        self.keys=QTableWidget(0,6); self.keys.setHorizontalHeaderLabels(["ID","Name","Role","Enabled","Created","Last used"]); self.keys.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch); tabs.addTab(self.keys,"API keys")
        row=QHBoxLayout(); self.server_button=QPushButton("Start REST API"); self.server_button.clicked.connect(self.toggle_server); check=QPushButton("Check connector health"); check.clicked.connect(self.refresh); issue=QPushButton("Issue API key"); issue.clicked.connect(self.issue_key); disable=QPushButton("Disable selected key"); disable.clicked.connect(self.disable_key)
        for b in (self.server_button,check,issue,disable): row.addWidget(b)
        row.addStretch(); root.addLayout(row); self.refresh()
    def refresh(self):
        health=self.service.connector_health(); ready=sum(1 for h in health if h.state.value=="Ready"); self.summary.setText(f"{ready}/{len(health)} connector(s) ready — REST: {self.rest_server.address}")
        self.connectors.setRowCount(len(health))
        for r,h in enumerate(health):
            vals=[h.name,h.kind.value,h.state.value,"" if h.latency_ms is None else f"{h.latency_ms:.1f} ms",h.message,str(h.metadata)]
            for c,v in enumerate(vals): self.connectors.setItem(r,c,QTableWidgetItem(str(v)))
        keys=self.service.list_api_keys(); self.keys.setRowCount(len(keys))
        for r,k in enumerate(keys):
            vals=[k["key_id"],k["name"],k["role"],"Yes" if k["enabled"] else "No",k["created_at"],k["last_used_at"] or ""]
            for c,v in enumerate(vals): self.keys.setItem(r,c,QTableWidgetItem(str(v)))
        self.server_button.setText("Stop REST API" if self.rest_server.is_running else "Start REST API")
    def toggle_server(self):
        try:
            self.rest_server.stop() if self.rest_server.is_running else self.rest_server.start(); self.refresh()
        except Exception as exc: QMessageBox.critical(self,"REST API",str(exc))
    def issue_key(self):
        name,ok=QInputDialog.getText(self,"Issue API key","Integration name:")
        if not ok or not name.strip(): return
        role,ok=QInputDialog.getItem(self,"Role","Role:",["Operator","QC","Supervisor","Maintenance","Administrator","Auditor"],0,False)
        if not ok:return
        key_id,secret=self.service.issue_api_key(name.strip(),role); QMessageBox.information(self,"API key issued",f"Key ID: {key_id}\n\nSecret (shown once):\n{secret}"); self.refresh()
    def disable_key(self):
        row=self.keys.currentRow()
        if row<0:return
        key_id=self.keys.item(row,0).text(); self.service.disable_api_key(key_id); self.refresh()
