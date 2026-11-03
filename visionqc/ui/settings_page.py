from __future__ import annotations
from pathlib import Path
import json
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog,QFormLayout,QHBoxLayout,QLabel,QLineEdit,QMessageBox,QPushButton,QSpinBox,QTabWidget,QTextEdit,QVBoxLayout,QWidget,QComboBox,QCheckBox,QTableWidget,QTableWidgetItem,QHeaderView
from visionqc.core.backup import create_backup,restore_backup,validate_backup
from visionqc.core.diagnostics import camera_test,create_support_bundle,system_report
from visionqc.core.deployment import deployment_readiness, export_deployment_report
from visionqc.core.health import health_report
from visionqc.core.settings import load_settings,save_settings
from visionqc.ui.theme import THEMES

class SettingsPage(QWidget):
    settings_saved=Signal()
    theme_changed=Signal(str)
    def __init__(self):
        super().__init__(); self.settings=load_settings(); root=QVBoxLayout(self)
        title=QLabel('Settings & Diagnostics'); title.setObjectName('PageTitle'); root.addWidget(title)
        root.addWidget(QLabel('Configure appearance, protect local data, and verify release readiness.'))
        self.tabs=QTabWidget(); root.addWidget(self.tabs,1)
        self.tabs.addTab(self._general_tab(),'General'); self.tabs.addTab(self._appearance_tab(),'Appearance')
        self.tabs.addTab(self._devices_tab(),'Devices'); self.tabs.addTab(self._health_tab(),'System Health')
        self.tabs.addTab(self._backup_tab(),'Backup & Restore'); self.tabs.addTab(self._deployment_tab(),'Deployment'); self.tabs.addTab(self._diagnostics_tab(),'Diagnostics')
    def _general_tab(self):
        w=QWidget(); f=QFormLayout(w); self.factory=QLineEdit(self.settings['factory_name']); self.operator=QLineEdit(self.settings['operator_name'])
        self.data_dir=QLineEdit(self.settings['data_directory']); self.reports_dir=QLineEdit(self.settings['reports_directory'])
        f.addRow('Factory name',self.factory); f.addRow('Default operator',self.operator)
        for label,edit in [('Data directory',self.data_dir),('Reports directory',self.reports_dir)]:
            row=QHBoxLayout(); row.addWidget(edit,1); b=QPushButton('Browse'); b.clicked.connect(lambda checked=False,e=edit:self._browse(e)); row.addWidget(b); f.addRow(label,row)
        save=QPushButton('Save settings'); save.clicked.connect(self._save); f.addRow('',save); return w
    def _appearance_tab(self):
        w=QWidget(); f=QFormLayout(w); self.theme=QComboBox(); self.theme.addItems(THEMES.keys()); self.theme.setCurrentText(self.settings.get('theme','Factory Blue'))
        self.scale=QSpinBox(); self.scale.setRange(90,150); self.scale.setSuffix('%'); self.scale.setValue(int(self.settings.get('ui_scale',100)))
        apply=QPushButton('Apply appearance'); apply.clicked.connect(self._save_appearance)
        f.addRow('Theme',self.theme); f.addRow('UI scale',self.scale); f.addRow('',apply); f.addRow('',QLabel('Theme changes apply immediately. UI scale applies after restart.')); return w
    def _devices_tab(self):
        w=QWidget(); l=QVBoxLayout(w); row=QHBoxLayout(); self.camera=QSpinBox(); self.camera.setRange(0,20); self.camera.setValue(int(self.settings['camera_index']))
        b=QPushButton('Test USB camera'); b.clicked.connect(self._camera_test); self.camera_msg=QLabel('Not tested')
        row.addWidget(QLabel('Camera index')); row.addWidget(self.camera); row.addWidget(b); row.addStretch(); l.addLayout(row); l.addWidget(self.camera_msg); l.addStretch(); return w
    def _health_tab(self):
        w=QWidget(); l=QVBoxLayout(w); self.health_summary=QLabel(); self.health_summary.setObjectName('SectionTitle'); l.addWidget(self.health_summary)
        self.health_table=QTableWidget(0,3); self.health_table.setHorizontalHeaderLabels(['Component','Status','Details']); self.health_table.horizontalHeader().setSectionResizeMode(2,QHeaderView.Stretch); l.addWidget(self.health_table,1)
        b=QPushButton('Run health check'); b.clicked.connect(self._refresh_health); l.addWidget(b); self._refresh_health(); return w
    def _backup_tab(self):
        w=QWidget(); l=QVBoxLayout(w); l.addWidget(QLabel('Create a portable offline backup of the SQLite database and local settings.'))
        row=QHBoxLayout(); create=QPushButton('Create backup'); create.clicked.connect(self._create_backup); restore=QPushButton('Restore backup'); restore.clicked.connect(self._restore_backup); row.addWidget(create); row.addWidget(restore); row.addStretch(); l.addLayout(row)
        l.addWidget(QLabel('Restore creates a safety copy of the current database before replacement.')); l.addStretch(); return w
    def _deployment_tab(self):
        w=QWidget(); l=QVBoxLayout(w)
        l.addWidget(QLabel('Verify that this computer can run the installed standalone VisionQC application without Python or specialist software.'))
        self.deployment_summary=QLabel(); self.deployment_summary.setObjectName('SectionTitle'); l.addWidget(self.deployment_summary)
        self.deployment_table=QTableWidget(0,3); self.deployment_table.setHorizontalHeaderLabels(['Check','Status','Details']); self.deployment_table.horizontalHeader().setSectionResizeMode(2,QHeaderView.Stretch); l.addWidget(self.deployment_table,1)
        row=QHBoxLayout(); refresh=QPushButton('Run deployment check'); refresh.clicked.connect(self._refresh_deployment); export=QPushButton('Export deployment report'); export.clicked.connect(self._export_deployment); row.addWidget(refresh); row.addWidget(export); row.addStretch(); l.addLayout(row)
        self._refresh_deployment(); return w
    def _refresh_deployment(self):
        r=deployment_readiness(); self.deployment_summary.setText('Deployment status: '+r['status']+' — '+r['installation_note']); self.deployment_table.setRowCount(len(r['checks']))
        for i,c in enumerate(r['checks']):
            self.deployment_table.setItem(i,0,QTableWidgetItem(c['name'])); self.deployment_table.setItem(i,1,QTableWidgetItem('OK' if c['ok'] else 'Attention')); self.deployment_table.setItem(i,2,QTableWidgetItem(c['message']))
    def _export_deployment(self):
        file,_=QFileDialog.getSaveFileName(self,'Export deployment report',str(Path.home()/'VisionQC_Deployment_Report.json'),'JSON (*.json)')
        if file:
            path=export_deployment_report(Path(file)); QMessageBox.information(self,'Deployment report',f'Created:\n{path}')

    def _diagnostics_tab(self):
        w=QWidget(); l=QVBoxLayout(w)
        self.report=QTextEdit(); self.report.setReadOnly(True)
        self.report.setPlainText(json.dumps(system_report(),indent=2)); l.addWidget(self.report,1)
        row=QHBoxLayout()
        refresh=QPushButton('Refresh')
        refresh.clicked.connect(lambda:self.report.setPlainText(json.dumps(system_report(),indent=2)))
        bundle=QPushButton('Export support bundle'); bundle.clicked.connect(self._bundle)
        row.addWidget(refresh); row.addWidget(bundle); row.addStretch(); l.addLayout(row)
        return w
    def _browse(self,edit):
        selected=QFileDialog.getExistingDirectory(self,'Choose directory',edit.text());
        if selected: edit.setText(selected)
    def _save(self):
        self.settings.update({'factory_name':self.factory.text().strip(),'operator_name':self.operator.text().strip(),'data_directory':self.data_dir.text(),'reports_directory':self.reports_dir.text(),'camera_index':self.camera.value()}); save_settings(self.settings); self.settings_saved.emit(); QMessageBox.information(self,'Saved','Settings were saved successfully.')
    def _save_appearance(self):
        self.settings['theme']=self.theme.currentText(); self.settings['ui_scale']=self.scale.value(); save_settings(self.settings); self.theme_changed.emit(self.theme.currentText()); QMessageBox.information(self,'Appearance','Theme applied. Restart VisionQC to apply UI scale changes.')
    def _camera_test(self):
        ok,msg=camera_test(self.camera.value()); self.camera_msg.setText(('✓ ' if ok else '⚠ ')+msg)
    def _refresh_health(self):
        r=health_report(); self.health_summary.setText('Overall status: '+r['status']); self.health_table.setRowCount(len(r['checks']))
        for i,c in enumerate(r['checks']):
            self.health_table.setItem(i,0,QTableWidgetItem(c['name'])); self.health_table.setItem(i,1,QTableWidgetItem('OK' if c['ok'] else 'Attention')); self.health_table.setItem(i,2,QTableWidgetItem(c['message']))
    def _create_backup(self):
        folder=QFileDialog.getExistingDirectory(self,'Choose backup destination',str(Path.home()))
        if folder:
            path=create_backup(Path(folder)); QMessageBox.information(self,'Backup created',f'Created:\n{path}')
    def _restore_backup(self):
        file,_=QFileDialog.getOpenFileName(self,'Select VisionQC backup',str(Path.home()),'VisionQC Backup (*.zip)')
        if not file:return
        try: info=validate_backup(Path(file))
        except Exception as e: QMessageBox.critical(self,'Invalid backup',str(e)); return
        if QMessageBox.question(self,'Confirm restore',f"Restore backup created {info['manifest'].get('created_at','unknown')}?\nVisionQC should be restarted afterward.")!=QMessageBox.Yes:return
        try:
            result=restore_backup(Path(file)); QMessageBox.information(self,'Restore complete',f"Backup restored.\nSafety copy: {result.get('safety_copy') or 'not required'}\nRestart VisionQC now.")
        except Exception as e: QMessageBox.critical(self,'Restore failed',str(e))
    def _bundle(self):
        folder=QFileDialog.getExistingDirectory(self,'Choose support bundle destination',str(Path.home()))
        if folder:
            path=create_support_bundle(Path(folder)); QMessageBox.information(self,'Support bundle',f'Created:\n{path}')
