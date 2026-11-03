from pathlib import Path
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QPushButton,QLabel,QTableWidget,QTableWidgetItem,QFileDialog,QMessageBox,QCheckBox
from visionqc.core.sync import *
class SyncPage(QWidget):
 def __init__(self):
  super().__init__();r=QVBoxLayout(self);r.addWidget(QLabel('<h1>Secure Synchronization</h1><p>Signed offline store-and-forward packages for sites without permanent connectivity.</p>'))
  f=QFormLayout();self.site=QLineEdit('FACTORY-01');self.key=QLineEdit();self.key.setEchoMode(QLineEdit.Password);f.addRow('Site ID',self.site);f.addRow('Shared sync key',self.key);r.addLayout(f)
  h=QHBoxLayout();
  for text,fn in [('Generate Key',self.gen),('Create Package',self.export),('Validate Package',self.validate),('Import Package',self.import_)]:b=QPushButton(text);b.clicked.connect(fn);h.addWidget(b)
  r.addLayout(h);self.apply=QCheckBox('Apply safe snapshot records during import');r.addWidget(self.apply);self.status=QLabel();r.addWidget(self.status)
  self.table=QTableWidget(0,6);self.table.setHorizontalHeaderLabels(['Direction','Site','Items','Status','Created','File']);r.addWidget(self.table);self.refresh()
 def gen(self):self.key.setText(generate_sync_key());self.status.setText('Key fingerprint: '+fingerprint(self.key.text()))
 def export(self):
  p,_=QFileDialog.getSaveFileName(self,'Create sync package',str(Path.home()/'VisionQC_Sync.vqcsync'),'VisionQC Sync (*.vqcsync)')
  if p:
   try:x=create_sync_package(p,self.key.text(),self.site.text());QMessageBox.information(self,'Created',f"Signed package created with {x['items']} queued item(s).")
   except Exception as e:QMessageBox.critical(self,'Error',str(e))
   self.refresh()
 def validate(self):
  p,_=QFileDialog.getOpenFileName(self,'Validate sync package','','VisionQC Sync (*.vqcsync)')
  if p:
   try:x=validate_sync_package(p,self.key.text());QMessageBox.information(self,'Validation',str(x))
   except Exception as e:QMessageBox.critical(self,'Error',str(e))
 def import_(self):
  p,_=QFileDialog.getOpenFileName(self,'Import sync package','','VisionQC Sync (*.vqcsync)')
  if p:
   try:x=import_sync_package(p,self.key.text(),self.apply.isChecked());QMessageBox.information(self,'Imported',f"Applied receipts: {x['applied']}\nConflicts: {x['conflicts']}")
   except Exception as e:QMessageBox.critical(self,'Error',str(e))
   self.refresh()
 def refresh(self):
  q=queue_summary();self.status.setText('Queue — '+' | '.join(f'{k}: {v}' for k,v in q.items()));rows=list_packages();self.table.setRowCount(len(rows))
  for i,x in enumerate(rows):
   for j,v in enumerate([x['direction'],x['site_id'],x['item_count'],x['status'],x['created_at'],x['file_path']]):self.table.setItem(i,j,QTableWidgetItem(str(v or '')))
