from __future__ import annotations
import json
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTableWidget,QTableWidgetItem,QComboBox,QLineEdit,QGroupBox,QFormLayout,QMessageBox,QTabWidget,QHeaderView,QPlainTextEdit)
from visionqc.configuration.repository import ConfigurationRepository
from visionqc.core.backup import create_backup
from visionqc.core.settings import app_data_dir

class SecurityGovernancePage(QWidget):
    def __init__(self, security_service, audit_repository) -> None:
        super().__init__(); self.security=security_service; self.audit=audit_repository; self.config=ConfigurationRepository()
        root=QVBoxLayout(self)
        title=QLabel("امنیت، حاکمیت و ممیزی سازمانی"); title.setStyleSheet("font-size:22px;font-weight:700")
        self.session_label=QLabel(); root.addWidget(title); root.addWidget(self.session_label)
        tabs=QTabWidget(); root.addWidget(tabs)
        tabs.addTab(self._users_tab(),"کاربران و نقش‌ها")
        tabs.addTab(self._audit_tab(),"Audit Log")
        tabs.addTab(self._templates_tab(),"قفل و نسخه‌بندی Template")
        tabs.addTab(self._backup_tab(),"Backup / Restore")
        self.refresh()

    def _users_tab(self):
        w=QWidget(); lay=QVBoxLayout(w)
        form=QGroupBox("ایجاد یا به‌روزرسانی کاربر"); f=QFormLayout(form)
        self.username=QLineEdit(); self.display=QLineEdit(); self.password=QLineEdit(); self.password.setEchoMode(QLineEdit.Password)
        self.role=QComboBox(); self.role.addItems(["Operator","QC Manager","Factory Manager","Administrator"])
        f.addRow("نام کاربری",self.username); f.addRow("نام نمایشی",self.display); f.addRow("نقش",self.role); f.addRow("رمز عبور",self.password)
        save=QPushButton("ذخیره کاربر"); save.clicked.connect(self._save_user); f.addRow(save); lay.addWidget(form)
        self.users=QTableWidget(0,6); self.users.setHorizontalHeaderLabels(["Username","Name","Role","Active","Change Password","Last Login"]); self.users.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); lay.addWidget(self.users)
        return w

    def _audit_tab(self):
        w=QWidget(); lay=QVBoxLayout(w); bar=QHBoxLayout(); refresh=QPushButton("به‌روزرسانی"); refresh.clicked.connect(self._refresh_audit); bar.addWidget(refresh); bar.addStretch(); lay.addLayout(bar)
        self.audit_table=QTableWidget(0,7); self.audit_table.setHorizontalHeaderLabels(["Time","Actor","Event","Entity","ID","Outcome","Details"]); self.audit_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents); self.audit_table.horizontalHeader().setStretchLastSection(True); lay.addWidget(self.audit_table)
        return w

    def _templates_tab(self):
        w=QWidget(); lay=QVBoxLayout(w); self.templates=QTableWidget(0,6); self.templates.setHorizontalHeaderLabels(["Key","Name","Version","Lifecycle","Locked","Action"]); self.templates.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); lay.addWidget(self.templates)
        self.versions=QTableWidget(0,7); self.versions.setHorizontalHeaderLabels(["ID","Template","Version","Lifecycle","Actor","State","Checksum"]); self.versions.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); lay.addWidget(QLabel("نسخه‌های ثبت‌شده")); lay.addWidget(self.versions)
        return w

    def _backup_tab(self):
        w=QWidget(); lay=QVBoxLayout(w); txt=QLabel("نسخه پشتیبان شامل تنظیمات، Templateها، کالیبراسیون، رویدادها، حافظه کارخانه و کاربران است."); txt.setWordWrap(True); lay.addWidget(txt)
        btn=QPushButton("ایجاد Backup امن"); btn.clicked.connect(self._backup); lay.addWidget(btn); self.backup_output=QPlainTextEdit(); self.backup_output.setReadOnly(True); lay.addWidget(self.backup_output); return w

    def _save_user(self):
        try:
            if not self.username.text().strip() or not self.password.text(): raise ValueError("نام کاربری و رمز عبور الزامی است")
            self.security.create_user(self.username.text().strip(),self.display.text().strip() or self.username.text().strip(),self.role.currentText(),self.password.text(),True)
            self.password.clear(); self.refresh(); QMessageBox.information(self,"VisionQC","کاربر ذخیره شد.")
        except Exception as e: QMessageBox.warning(self,"خطا",str(e))

    def _toggle_lock(self,key,locked):
        try:
            self.security.lock_template(key,not locked,"Production governance lock")
            if not locked:
                t=self.config.get_template(key)
                if t: self.security.repository.snapshot_template(t,self.security.session.username,"Locked")
            self.refresh()
        except Exception as e: QMessageBox.warning(self,"خطا",str(e))

    def _backup(self):
        try:
            path=create_backup(app_data_dir()/"backups"); self.audit.append("governance.backup.created",self.security.session.username,"backup",str(path)); self.backup_output.setPlainText(str(path))
        except Exception as e: QMessageBox.warning(self,"Backup",str(e))

    def _refresh_audit(self):
        rows=self.audit.recent(300); self.audit_table.setRowCount(len(rows))
        for i,r in enumerate(rows):
            vals=[r.get("created_at",""),r.get("actor",""),r.get("event_type",""),r.get("entity_type",""),r.get("entity_id",""),r.get("outcome",""),json.dumps(r.get("details",{}),ensure_ascii=False)]
            for j,v in enumerate(vals): self.audit_table.setItem(i,j,QTableWidgetItem(str(v)))

    def refresh(self):
        s=self.security.session; self.session_label.setText(f"کاربر جاری: {s.display_name} | نقش: {s.role}")
        users=self.security.repository.list_users(); self.users.setRowCount(len(users))
        for i,u in enumerate(users):
            for j,v in enumerate([u.username,u.display_name,u.role,"Yes" if u.active else "No","Yes" if u.must_change_password else "No",u.last_login_at or "-"]): self.users.setItem(i,j,QTableWidgetItem(str(v)))
        templates=self.config.list_templates(); self.templates.setRowCount(len(templates))
        for i,t in enumerate(templates):
            locked=self.security.repository.is_locked("template",t.key)
            for j,v in enumerate([t.key,t.name_fa,t.version,t.lifecycle,"Locked" if locked else "Open"]): self.templates.setItem(i,j,QTableWidgetItem(str(v)))
            b=QPushButton("بازکردن" if locked else "قفل و Snapshot"); b.clicked.connect(lambda _=False,k=t.key,l=locked:self._toggle_lock(k,l)); self.templates.setCellWidget(i,5,b)
        versions=self.security.repository.list_versions(limit=200); self.versions.setRowCount(len(versions))
        for i,r in enumerate(versions):
            vals=[r["id"],r["template_key"],r["version"],r["lifecycle"],r["actor"],r["approval_state"],r["checksum"][:12]]
            for j,v in enumerate(vals): self.versions.setItem(i,j,QTableWidgetItem(str(v)))
        self._refresh_audit()
