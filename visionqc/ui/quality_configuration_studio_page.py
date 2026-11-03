from __future__ import annotations
import json
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QTabWidget,QTableWidget,QTableWidgetItem,
 QGroupBox,QFormLayout,QLineEdit,QComboBox,QDoubleSpinBox,QSpinBox,QCheckBox,QPushButton,QLabel,QTextEdit,
 QFileDialog,QMessageBox,QHeaderView,QSplitter)
from visionqc.configuration import ConfigurationRepository,ConfigurationRuntime,default_detector_registry
from visionqc.configuration.models import *
from visionqc.configuration.seed import sausage_batter_template
from visionqc.configuration.validator import validate_template
from visionqc.quality.validation import CalibrationRepository

class QualityConfigurationStudioPage(QWidget):
    """Zabbix-inspired no-code configuration studio for food quality monitoring."""
    def __init__(self):
        super().__init__(); self.repo=ConfigurationRepository(); self.registry=default_detector_registry(); self.runtime=ConfigurationRuntime(self.registry); self.current=None; self.calibration_repo=CalibrationRepository()
        if not self.repo.get_template("tpl.sausage_batter_mixing"): self.repo.save_template(sausage_batter_template(),"seed")
        root=QVBoxLayout(self)
        title=QLabel("VisionQC Studio — پیکربندی پایش کیفیت")
        title.setStyleSheet("font-size:22px;font-weight:700")
        sub=QLabel("الگوی آشنا برای کاربران Zabbix: Template ← Item/Metric ← Trigger ← Action ← Test")
        sub.setStyleSheet("color:#667085")
        root.addWidget(title); root.addWidget(sub)
        bar=QHBoxLayout(); self.template_combo=QComboBox(); self.template_combo.currentIndexChanged.connect(self.load_selected)
        for text,fn in [("Template جدید",self.new_template),("ذخیره",self.save_current),("اعتبارسنجی",self.validate_current),("انتشار Production",self.publish_current),("Export",self.export_current),("Import",self.import_template)]:
            b=QPushButton(text); b.clicked.connect(fn); bar.addWidget(b)
        bar.insertWidget(0,QLabel("Template:")); bar.insertWidget(1,self.template_combo,1); root.addLayout(bar)
        self.tabs=QTabWidget(); root.addWidget(self.tabs,1)
        self.tabs.addTab(self._template_tab(),"Template")
        self.tabs.addTab(self._metrics_tab(),"Items / شاخص‌ها")
        self.tabs.addTab(self._triggers_tab(),"Triggers")
        self.tabs.addTab(self._actions_tab(),"Actions")
        self.tabs.addTab(self._dryrun_tab(),"Test / Dry Run")
        self.tabs.addTab(self._diagnostics_tab(),"Diagnostics")
        self.refresh_templates()

    def _template_tab(self):
        w=QWidget(); f=QFormLayout(w)
        self.t_key=QLineEdit(); self.t_name=QLineEdit(); self.t_version=QLineEdit("1.0.0"); self.t_stage=QLineEdit(); self.t_lifecycle=QComboBox(); self.t_lifecycle.addItems(LIFECYCLE_STATES)
        self.t_product_weight=QDoubleSpinBox(); self.t_product_weight.setRange(0,100); self.t_product_weight.setValue(75)
        self.t_process_weight=QDoubleSpinBox(); self.t_process_weight.setRange(0,100); self.t_process_weight.setValue(25)
        self.t_ai=QDoubleSpinBox(); self.t_ai.setRange(0,100); self.t_ai.setValue(80)
        self.t_desc=QTextEdit(); self.t_desc.setMaximumHeight(120)
        for label,x in [("کلید فنی",self.t_key),("نام فارسی",self.t_name),("نسخه",self.t_version),("مرحله فرایند",self.t_stage),("Lifecycle",self.t_lifecycle),("وزن سلامت محصول",self.t_product_weight),("وزن سلامت فرایند",self.t_process_weight),("آستانه مراجعه به هوش مصنوعی",self.t_ai),("توضیحات",self.t_desc)]: f.addRow(label,x)
        return w

    def _metrics_tab(self):
        w=QWidget(); v=QVBoxLayout(w); self.metric_table=QTableWidget(0,9); self.metric_table.setHorizontalHeaderLabels(["کلید","نام","Detector","گروه","وزن","Scoring","Window","Lifecycle","فعال"]); self.metric_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        v.addWidget(self.metric_table,1); h=QHBoxLayout()
        for text,fn in [("افزودن Item",self.add_metric),("حذف",lambda:self._delete_row(self.metric_table)),("نمایش Detector Registry",self.show_detectors)]: b=QPushButton(text); b.clicked.connect(fn); h.addWidget(b)
        v.addLayout(h); return w
    def _triggers_tab(self):
        w=QWidget(); v=QVBoxLayout(w); self.trigger_table=QTableWidget(0,8); self.trigger_table.setHorizontalHeaderLabels(["کلید","نام","Severity","Metric","Function","Operator","Threshold","Persistence"]); self.trigger_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); v.addWidget(self.trigger_table,1)
        h=QHBoxLayout(); b=QPushButton("افزودن Trigger"); b.clicked.connect(self.add_trigger); h.addWidget(b); b=QPushButton("حذف"); b.clicked.connect(lambda:self._delete_row(self.trigger_table)); h.addWidget(b); v.addLayout(h); return w
    def _actions_tab(self):
        w=QWidget(); v=QVBoxLayout(w); self.action_table=QTableWidget(0,7); self.action_table.setHorizontalHeaderLabels(["کلید","نام","Trigger","نوع اقدام","گیرنده","پیام","Ack"]); self.action_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); v.addWidget(self.action_table,1)
        h=QHBoxLayout(); b=QPushButton("افزودن Action Step"); b.clicked.connect(self.add_action); h.addWidget(b); b=QPushButton("حذف"); b.clicked.connect(lambda:self._delete_row(self.action_table)); h.addWidget(b); v.addLayout(h); return w
    def _dryrun_tab(self):
        w=QWidget(); v=QVBoxLayout(w); h=QHBoxLayout(); self.test_path=QLineEdit(); b=QPushButton("انتخاب عکس/ویدئو"); b.clicked.connect(self.choose_test); run=QPushButton("اجرای Dry Run"); run.clicked.connect(self.run_dry); h.addWidget(self.test_path,1); h.addWidget(b); h.addWidget(run); v.addLayout(h); self.test_result=QTextEdit(); self.test_result.setReadOnly(True); v.addWidget(self.test_result,1); return w
    def _diagnostics_tab(self):
        w=QWidget(); v=QVBoxLayout(w); self.diag=QTextEdit(); self.diag.setReadOnly(True); v.addWidget(QLabel("در این بخش وضعیت واقعی اتصال Metric به Detector و خطاهای پیکربندی نمایش داده می‌شود.")); v.addWidget(self.diag,1); b=QPushButton("اجرای Diagnostics"); b.clicked.connect(self.refresh_diagnostics); v.addWidget(b); return w

    def refresh_templates(self):
        selected=self.current.key if self.current else None; self.template_combo.blockSignals(True); self.template_combo.clear()
        for t in self.repo.list_templates(): self.template_combo.addItem(f"{t.name_fa} [{t.lifecycle}]",t.key)
        self.template_combo.blockSignals(False)
        if selected:
            i=self.template_combo.findData(selected); self.template_combo.setCurrentIndex(max(0,i))
        elif self.template_combo.count(): self.template_combo.setCurrentIndex(0); self.load_selected()
    def load_selected(self):
        key=self.template_combo.currentData();
        if not key:return
        self.current=self.repo.get_template(key); self._render()
    def _render(self):
        t=self.current
        self.t_key.setText(t.key); self.t_name.setText(t.name_fa); self.t_version.setText(t.version); self.t_stage.setText(t.process_stage); self.t_lifecycle.setCurrentText(t.lifecycle); self.t_product_weight.setValue(t.product_weight); self.t_process_weight.setValue(t.process_weight); self.t_ai.setValue(t.ai_review_below); self.t_desc.setPlainText(t.description)
        self.metric_table.setRowCount(0)
        for m in t.metrics:
            r=self.metric_table.rowCount(); self.metric_table.insertRow(r); vals=[m.key,m.name_fa,m.detector_key,m.group_name,str(m.weight),m.scoring.mode,str(m.window_seconds),m.lifecycle,"1" if m.enabled else "0"]
            for c,x in enumerate(vals): self.metric_table.setItem(r,c,QTableWidgetItem(x))
        self.trigger_table.setRowCount(0)
        for tr in t.triggers:
            for cond in tr.conditions or [TriggerCondition("")]:
                r=self.trigger_table.rowCount(); self.trigger_table.insertRow(r); vals=[tr.key,tr.name_fa,tr.severity,cond.metric_key,cond.function,cond.operator,str(cond.threshold),str(tr.persistence_seconds)]
                for c,x in enumerate(vals): self.trigger_table.setItem(r,c,QTableWidgetItem(x))
        self.action_table.setRowCount(0)
        for a in t.actions:
            for s in a.steps:
                r=self.action_table.rowCount(); self.action_table.insertRow(r); vals=[a.key,a.name_fa,a.trigger_key,s.action_type,s.target,s.message,"1" if s.require_ack else "0"]
                for c,x in enumerate(vals): self.action_table.setItem(r,c,QTableWidgetItem(x))
        self.refresh_diagnostics()
    def _collect(self):
        t=InspectionTemplate(self.t_key.text().strip(),self.t_name.text().strip(),self.t_version.text().strip(),process_stage=self.t_stage.text().strip(),lifecycle=self.t_lifecycle.currentText(),description=self.t_desc.toPlainText(),product_weight=self.t_product_weight.value(),process_weight=self.t_process_weight.value(),ai_review_below=self.t_ai.value())
        for r in range(self.metric_table.rowCount()):
            x=lambda c:self.metric_table.item(r,c).text().strip() if self.metric_table.item(r,c) else ""
            t.metrics.append(MetricDefinition(x(0),x(1),x(2),x(3),weight=float(x(4) or 0),window_seconds=int(float(x(6) or 30)),lifecycle=x(7) or "Draft",enabled=x(8)!="0",scoring=ScoringRule(mode=x(5) or "higher_is_better",raw_min=0,raw_max=1)))
        trigger_map={}
        for r in range(self.trigger_table.rowCount()):
            x=lambda c:self.trigger_table.item(r,c).text().strip() if self.trigger_table.item(r,c) else ""
            tr=trigger_map.get(x(0)) or TriggerDefinition(x(0),x(1),x(2),persistence_seconds=int(float(x(7) or 10)))
            tr.conditions.append(TriggerCondition(x(3),x(4),x(5),float(x(6) or 0))); trigger_map[x(0)]=tr
        t.triggers=list(trigger_map.values()); action_map={}
        for r in range(self.action_table.rowCount()):
            x=lambda c:self.action_table.item(r,c).text().strip() if self.action_table.item(r,c) else ""
            a=action_map.get(x(0)) or ActionDefinition(x(0),x(1),x(2)); a.steps.append(ActionStep(len(a.steps)+1,x(3),x(4),x(5),require_ack=x(6)!="0")); action_map[x(0)]=a
        t.actions=list(action_map.values()); self.current=t; return t
    def new_template(self): self.current=InspectionTemplate("tpl.new","Template جدید"); self._render()
    def save_current(self):
        try:self.repo.save_template(self._collect()); self.refresh_templates(); QMessageBox.information(self,"ذخیره","Template ذخیره شد.")
        except Exception as e: QMessageBox.critical(self,"خطا",str(e))
    def validate_current(self):
        e=validate_template(self._collect(),self.registry); QMessageBox.information(self,"اعتبارسنجی","پیکربندی معتبر است." if not e else "\n".join(e))
    def publish_current(self):
        t=self._collect(); e=validate_template(t,self.registry)
        if e: QMessageBox.warning(self,"انتشار متوقف شد","\n".join(e)); return
        if not self.calibration_repo.has_approved_validation(t.key,t.version):
            QMessageBox.warning(self,"Production Gate","برای همین نسخه Template، اعتبارسنجی پاس‌شده و تأیید نهایی مسئول QC ثبت نشده است. از صفحه Calibration & Validation استفاده کنید.")
            return
        t.lifecycle="Production"; [setattr(m,"lifecycle","Production") for m in t.metrics]; self.repo.save_template(t,"publish_after_validation"); self.refresh_templates(); QMessageBox.information(self,"Production","Template پس از عبور از Calibration Gate منتشر شد.")
    def add_metric(self):
        r=self.metric_table.rowCount(); self.metric_table.insertRow(r); vals=["metric.new","شاخص جدید",self.registry.manifests()[0].key,"سلامت محصول","0","higher_is_better","30","Draft","1"]
        for c,x in enumerate(vals): self.metric_table.setItem(r,c,QTableWidgetItem(x))
    def add_trigger(self):
        r=self.trigger_table.rowCount(); self.trigger_table.insertRow(r); vals=["trigger.new","Trigger جدید","هشدار سطح متوسط","metric.new","avg","<","70","10"]
        for c,x in enumerate(vals): self.trigger_table.setItem(r,c,QTableWidgetItem(x))
    def add_action(self):
        r=self.action_table.rowCount(); self.action_table.insertRow(r); vals=["action.new","Action جدید","trigger.new","dashboard","مدیر QC","پیام اقدام","0"]
        for c,x in enumerate(vals): self.action_table.setItem(r,c,QTableWidgetItem(x))
    def _delete_row(self,table):
        if table.currentRow()>=0: table.removeRow(table.currentRow())
    def show_detectors(self): QMessageBox.information(self,"Detector Registry","\n".join(f"{m.key} — {m.name_fa} ({m.version})" for m in self.registry.manifests()))
    def choose_test(self):
        p,_=QFileDialog.getOpenFileName(self,"انتخاب داده آزمون","","Media (*.jpg *.jpeg *.png *.bmp *.webp *.mp4 *.avi *.mov *.mkv)"); self.test_path.setText(p)
    def run_dry(self):
        try:
            t=self._collect(); result=self.runtime.dry_run(self.test_path.text(),t); self.repo.record_validation(t.key,self.test_path.text(),result["mode"],result); self.test_result.setPlainText(json.dumps(result,ensure_ascii=False,indent=2))
        except Exception as e:self.test_result.setPlainText(f"Dry Run Failed\n{e}")
    def refresh_diagnostics(self):
        try:
            t=self._collect() if self.current else sausage_batter_template(); errors=validate_template(t,self.registry); lines=[f"Template: {t.key}",f"Lifecycle: {t.lifecycle}",f"Detectors registered: {len(self.registry.manifests())}",f"Metrics: {len(t.metrics)} | Triggers: {len(t.triggers)} | Actions: {len(t.actions)}",""]
            for m in t.metrics:
                try:self.registry.get(m.detector_key); lines.append(f"RUNNING  {m.key} → {m.detector_key}")
                except KeyError:lines.append(f"ERROR    {m.key} → detector missing")
            if errors: lines += ["","Validation:"]+[f"• {e}" for e in errors]
            else: lines += ["","Validation: PASS"]
            self.diag.setPlainText("\n".join(lines))
        except Exception as e:self.diag.setPlainText(str(e))
    def export_current(self):
        t=self._collect(); p,_=QFileDialog.getSaveFileName(self,"Export Template",f"{t.key}.json","JSON (*.json)");
        if p: Path(p).write_text(t.to_json(),encoding="utf-8")
    def import_template(self):
        p,_=QFileDialog.getOpenFileName(self,"Import Template","","JSON (*.json)");
        if p:
            t=InspectionTemplate.from_dict(json.loads(Path(p).read_text(encoding="utf-8"))); self.repo.save_template(t,"import"); self.refresh_templates()
