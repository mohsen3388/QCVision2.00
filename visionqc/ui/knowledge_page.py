from __future__ import annotations
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QGroupBox,QLabel,QLineEdit,QComboBox,QDoubleSpinBox,QCheckBox,QPushButton,QTableWidget,QTableWidgetItem,QMessageBox,QTextEdit
from visionqc.core.knowledge_engine import KnowledgeEntry, save_entry, list_entries, delete_entry, set_entry_enabled

class KnowledgePage(QWidget):
    def __init__(self):
        super().__init__(); root=QVBoxLayout(self); title=QLabel("Factory Knowledge Engine"); title.setObjectName("PageTitle"); root.addWidget(title); root.addWidget(QLabel("Capture approved product, process and metric knowledge locally. Entries remain explainable and operator-controlled."))
        body=QHBoxLayout(); form_box=QGroupBox("New knowledge entry"); form=QFormLayout(form_box)
        self.title=QLineEdit(); self.content=QTextEdit(); self.content.setMaximumHeight(90); self.category=QComboBox(); self.category.addItems(["Process Note","Approved Range","Troubleshooting","Product Guidance","Safety Note"])
        self.product=QLineEdit(); self.stage=QLineEdit(); self.group=QLineEdit(); self.metric=QLineEdit(); self.low=QLineEdit(); self.high=QLineEdit(); self.recommend=QLineEdit(); self.conf=QDoubleSpinBox(); self.conf.setRange(0,100); self.conf.setValue(100); self.enabled=QCheckBox("Enabled"); self.enabled.setChecked(True)
        for label,w in [("Title",self.title),("Content",self.content),("Category",self.category),("Product scope",self.product),("Process stage",self.stage),("Metric group",self.group),("Metric name",self.metric),("Lower bound",self.low),("Upper bound",self.high),("Recommendation",self.recommend),("Confidence",self.conf)]: form.addRow(label,w)
        form.addRow(self.enabled); b=QPushButton("Save Knowledge"); b.clicked.connect(self.save); form.addRow(b); body.addWidget(form_box,1)
        right=QGroupBox("Factory knowledge base"); rv=QVBoxLayout(right); self.table=QTableWidget(0,8); self.table.setHorizontalHeaderLabels(["ID","Title","Category","Product","Stage","Metric","Confidence","Enabled"]); self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); rv.addWidget(self.table)
        actions=QHBoxLayout(); toggle=QPushButton("Toggle Enabled"); toggle.clicked.connect(self.toggle); remove=QPushButton("Delete"); remove.clicked.connect(self.remove); refresh=QPushButton("Refresh"); refresh.clicked.connect(self.refresh); actions.addWidget(toggle); actions.addWidget(remove); actions.addWidget(refresh); rv.addLayout(actions); body.addWidget(right,2); root.addLayout(body,1); self.refresh()
    def _float(self, edit): return float(edit.text()) if edit.text().strip() else None
    def save(self):
        try:
            save_entry(KnowledgeEntry(title=self.title.text(),content=self.content.toPlainText(),category=self.category.currentText(),product_name=self.product.text(),process_stage=self.stage.text(),metric_group=self.group.text(),metric_name=self.metric.text(),lower_bound=self._float(self.low),upper_bound=self._float(self.high),recommendation=self.recommend.text(),confidence=self.conf.value(),enabled=self.enabled.isChecked())); self.title.clear(); self.content.clear(); self.refresh(); QMessageBox.information(self,"Saved","Knowledge entry saved locally.")
        except Exception as e: QMessageBox.warning(self,"Invalid entry",str(e))
    def refresh(self):
        rows=list_entries(); self.table.setRowCount(len(rows))
        for i,e in enumerate(rows):
            vals=[e.entry_id,e.title,e.category,e.product_name,e.process_stage,f"{e.metric_group}.{e.metric_name}" if e.metric_name else "—",f"{e.confidence:.0f}%","Yes" if e.enabled else "No"]
            for j,v in enumerate(vals): self.table.setItem(i,j,QTableWidgetItem(str(v)))
        self.table.resizeColumnsToContents()
    def selected(self):
        r=self.table.currentRow(); return int(self.table.item(r,0).text()) if r>=0 else None
    def toggle(self):
        i=self.selected();
        if i is not None: set_entry_enabled(i,self.table.item(self.table.currentRow(),7).text()!="Yes"); self.refresh()
    def remove(self):
        i=self.selected();
        if i is not None and QMessageBox.question(self,"Delete","Delete selected knowledge entry?")==QMessageBox.StandardButton.Yes: delete_entry(i); self.refresh()
