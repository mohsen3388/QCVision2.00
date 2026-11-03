from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox, QPushButton,
    QLineEdit, QTextEdit, QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QTabWidget, QSpinBox, QDoubleSpinBox, QGroupBox, QInputDialog,
)

from visionqc.configuration import ConfigurationRepository, ConfigurationRuntime
from visionqc.quality.validation import CalibrationRepository, ValidationService
from visionqc.quality.validation.models import CalibrationSample, QUALITY_CLASSES


class CalibrationValidationPage(QWidget):
    """Scientific calibration, validation and production approval workflow."""

    def __init__(self) -> None:
        super().__init__()
        self.config_repo = ConfigurationRepository()
        self.calibration_repo = CalibrationRepository()
        self.service = ValidationService(ConfigurationRuntime(), self.calibration_repo)
        self.current_summary = None

        root = QVBoxLayout(self)
        title = QLabel("Calibration & Validation — کالیبراسیون و اعتبارسنجی علمی")
        title.setStyleSheet("font-size:22px;font-weight:700")
        root.addWidget(title)
        root.addWidget(QLabel("فرایند: داده برچسب‌خورده ← اجرای Runtime واقعی ← ماتریس خطا ← Production Gate ← تأیید QC"))

        top = QHBoxLayout()
        self.template_combo = QComboBox(); self.template_combo.currentIndexChanged.connect(self.refresh_samples)
        refresh = QPushButton("بازخوانی Templateها"); refresh.clicked.connect(self.refresh_templates)
        top.addWidget(QLabel("Template:")); top.addWidget(self.template_combo, 1); top.addWidget(refresh)
        root.addLayout(top)

        tabs = QTabWidget(); root.addWidget(tabs, 1)
        tabs.addTab(self._dataset_tab(), "Dataset / نمونه‌ها")
        tabs.addTab(self._validation_tab(), "Validation Report")
        tabs.addTab(self._metrics_tab(), "Metric Calibration")
        tabs.addTab(self._gate_tab(), "Production Gate")
        self.refresh_templates()

    def _dataset_tab(self):
        w = QWidget(); v = QVBoxLayout(w)
        box = QGroupBox("افزودن نمونه برچسب‌خورده"); f = QFormLayout(box)
        self.path_edit = QLineEdit(); choose = QPushButton("انتخاب فایل"); choose.clicked.connect(self.choose_files)
        row = QHBoxLayout(); row.addWidget(self.path_edit, 1); row.addWidget(choose); f.addRow("عکس/ویدئو:", row)
        self.label_combo = QComboBox(); self.label_combo.addItems(QUALITY_CLASSES); f.addRow("نظر کارشناس:", self.label_combo)
        self.expert_edit = QLineEdit(); f.addRow("نام کارشناس QC:", self.expert_edit)
        self.batch_edit = QLineEdit(); f.addRow("کد Batch:", self.batch_edit)
        self.notes_edit = QLineEdit(); f.addRow("یادداشت:", self.notes_edit)
        add = QPushButton("ثبت نمونه"); add.clicked.connect(self.add_sample); f.addRow(add)
        v.addWidget(box)
        self.samples_table = QTableWidget(0, 7)
        self.samples_table.setHorizontalHeaderLabels(["ID", "فایل", "برچسب مرجع", "کارشناس", "Batch", "یادداشت", "زمان"])
        self.samples_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        v.addWidget(self.samples_table, 1)
        h = QHBoxLayout(); delete = QPushButton("حذف نمونه انتخاب‌شده"); delete.clicked.connect(self.delete_sample); h.addWidget(delete); h.addStretch(); v.addLayout(h)
        return w

    def _validation_tab(self):
        w = QWidget(); v = QVBoxLayout(w)
        controls = QGroupBox("معیارهای اعتبارسنجی"); f = QFormLayout(controls)
        self.minimum_samples = QSpinBox(); self.minimum_samples.setRange(2, 10000); self.minimum_samples.setValue(10)
        self.minimum_per_class = QSpinBox(); self.minimum_per_class.setRange(0, 1000); self.minimum_per_class.setValue(1)
        self.minimum_accuracy = QDoubleSpinBox(); self.minimum_accuracy.setRange(0, 100); self.minimum_accuracy.setValue(70); self.minimum_accuracy.setSuffix(" %")
        self.maximum_fnr = QDoubleSpinBox(); self.maximum_fnr.setRange(0, 100); self.maximum_fnr.setValue(20); self.maximum_fnr.setSuffix(" %")
        f.addRow("حداقل کل نمونه‌ها:", self.minimum_samples); f.addRow("حداقل نمونه هر کلاس:", self.minimum_per_class)
        f.addRow("حداقل توافق با کارشناس:", self.minimum_accuracy); f.addRow("حداکثر نرخ از دست‌رفتن عیب:", self.maximum_fnr)
        run = QPushButton("اجرای اعتبارسنجی کامل"); run.clicked.connect(self.run_validation); f.addRow(run)
        v.addWidget(controls)
        self.summary_text = QTextEdit(); self.summary_text.setReadOnly(True); v.addWidget(self.summary_text, 1)
        self.confusion_table = QTableWidget(len(QUALITY_CLASSES), len(QUALITY_CLASSES))
        self.confusion_table.setHorizontalHeaderLabels(list(QUALITY_CLASSES)); self.confusion_table.setVerticalHeaderLabels(list(QUALITY_CLASSES))
        self.confusion_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        v.addWidget(QLabel("ماتریس آشفتگی — سطر: نظر کارشناس، ستون: تصمیم VisionQC")); v.addWidget(self.confusion_table)
        return w

    def _metrics_tab(self):
        w = QWidget(); v = QVBoxLayout(w)
        self.metrics_table = QTableWidget(0, 10)
        self.metrics_table.setHorizontalHeaderLabels(["Metric", "سالم", "انحراف جزئی", "متوسط", "بالا", "بحرانی", "آستانه هشدار", "آستانه بالا", "جداسازی", "کیفیت"])
        self.metrics_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        v.addWidget(QLabel("آستانه‌ها فقط پیشنهاد هستند و خودکار وارد Production نمی‌شوند.")); v.addWidget(self.metrics_table, 1)
        return w

    def _gate_tab(self):
        w = QWidget(); v = QVBoxLayout(w)
        self.gate_status = QLabel("هنوز اعتبارسنجی اجرا نشده است."); self.gate_status.setStyleSheet("font-size:18px;font-weight:700")
        self.gate_reasons = QTextEdit(); self.gate_reasons.setReadOnly(True)
        self.approver_edit = QLineEdit(); approve = QPushButton("تأیید نهایی توسط QC"); approve.clicked.connect(self.approve_run)
        v.addWidget(self.gate_status); v.addWidget(self.gate_reasons, 1)
        h = QHBoxLayout(); h.addWidget(QLabel("نام تأییدکننده:")); h.addWidget(self.approver_edit, 1); h.addWidget(approve); v.addLayout(h)
        return w

    def refresh_templates(self):
        current = self.template_combo.currentData()
        self.template_combo.blockSignals(True); self.template_combo.clear()
        for template in self.config_repo.list_templates():
            self.template_combo.addItem(f"{template.name_fa} — v{template.version} [{template.lifecycle}]", template.key)
        self.template_combo.blockSignals(False)
        if current:
            index = self.template_combo.findData(current); self.template_combo.setCurrentIndex(max(0, index))
        elif self.template_combo.count(): self.template_combo.setCurrentIndex(0)
        self.refresh_samples()

    def template_key(self) -> str:
        return str(self.template_combo.currentData() or "")

    def choose_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "انتخاب نمونه‌ها", "", "Media (*.jpg *.jpeg *.png *.bmp *.webp *.mp4 *.avi *.mov *.mkv)")
        if paths: self.path_edit.setText(";".join(paths))

    def add_sample(self):
        key = self.template_key(); paths = [x.strip() for x in self.path_edit.text().split(";") if x.strip()]
        if not key or not paths:
            QMessageBox.warning(self, "اطلاعات ناقص", "Template و حداقل یک فایل را انتخاب کنید."); return
        try:
            for path in paths:
                self.calibration_repo.add_sample(CalibrationSample(None, key, path, self.label_combo.currentText(), self.expert_edit.text(), self.notes_edit.text(), self.batch_edit.text()))
            self.path_edit.clear(); self.refresh_samples()
        except Exception as exc: QMessageBox.critical(self, "خطا", str(exc))

    def refresh_samples(self):
        key = self.template_key(); self.samples_table.setRowCount(0)
        if not key: return
        for sample in self.calibration_repo.list_samples(key):
            row = self.samples_table.rowCount(); self.samples_table.insertRow(row)
            values = [sample.id, Path(sample.source_path).name, sample.expert_label, sample.expert_name, sample.batch_code, sample.notes, sample.created_at]
            for col, value in enumerate(values): self.samples_table.setItem(row, col, QTableWidgetItem(str(value)))

    def delete_sample(self):
        row = self.samples_table.currentRow()
        if row < 0: return
        try:
            self.calibration_repo.delete_sample(int(self.samples_table.item(row, 0).text())); self.refresh_samples()
        except Exception as exc: QMessageBox.critical(self, "خطا", str(exc))

    def run_validation(self):
        template = self.config_repo.get_template(self.template_key())
        if not template: return
        self.summary_text.setPlainText("در حال اجرای Detectorها روی داده‌های مرجع...")
        try:
            summary = self.service.validate(
                template, minimum_samples=self.minimum_samples.value(), minimum_per_class=self.minimum_per_class.value(),
                minimum_accuracy=self.minimum_accuracy.value() / 100.0, maximum_false_negative_rate=self.maximum_fnr.value() / 100.0,
            )
            self.current_summary = summary; self.render_summary(summary)
        except Exception as exc:
            self.summary_text.setPlainText(f"Validation Failed\n{exc}")

    def render_summary(self, summary):
        lines = [
            f"Run ID: {summary.run_id}", f"Template: {summary.template_key} v{summary.template_version}",
            f"Samples: {summary.sample_count}", f"Expert Agreement / Accuracy: {summary.accuracy:.1%}",
            f"Precision: {summary.precision:.1%}", f"Recall: {summary.recall:.1%}", f"Specificity: {summary.specificity:.1%}",
            f"F1: {summary.f1:.1%}", f"False Positive Rate: {summary.false_positive_rate:.1%}",
            f"False Negative Rate: {summary.false_negative_rate:.1%}", "", "Class counts:",
        ] + [f"• {key}: {value}" for key, value in summary.class_counts.items()]
        self.summary_text.setPlainText("\n".join(lines))
        for r, actual in enumerate(QUALITY_CLASSES):
            for c, predicted in enumerate(QUALITY_CLASSES):
                self.confusion_table.setItem(r, c, QTableWidgetItem(str(summary.confusion_matrix[actual][predicted])))
        self.metrics_table.setRowCount(0)
        for metric in summary.metric_results:
            row = self.metrics_table.rowCount(); self.metrics_table.insertRow(row)
            values = [metric.metric_name] + [metric.class_medians.get(label) for label in QUALITY_CLASSES] + [metric.suggested_warning_threshold, metric.suggested_high_threshold, metric.class_separation, metric.quality]
            for col, value in enumerate(values): self.metrics_table.setItem(row, col, QTableWidgetItem("—" if value is None else str(value)))
        if summary.production_ready:
            self.gate_status.setText("✓ معیارهای فنی Production Gate پاس شده‌اند؛ تأیید انسانی QC هنوز الزامی است.")
            self.gate_status.setStyleSheet("font-size:18px;font-weight:700;color:#087A3E")
            self.gate_reasons.setPlainText("هیچ مانع فنی ثبت نشد. نتایج، نمونه‌ها و آستانه‌های پیشنهادی باید توسط مسئول QC بازبینی شوند.")
        else:
            self.gate_status.setText("✗ Template هنوز برای Production آماده نیست.")
            self.gate_status.setStyleSheet("font-size:18px;font-weight:700;color:#B42318")
            self.gate_reasons.setPlainText("\n".join(f"• {x}" for x in summary.gate_reasons))

    def approve_run(self):
        if not self.current_summary or not self.current_summary.run_id:
            QMessageBox.warning(self, "بدون اعتبارسنجی", "ابتدا یک اعتبارسنجی اجرا کنید."); return
        try:
            self.calibration_repo.approve_run(self.current_summary.run_id, self.approver_edit.text())
            QMessageBox.information(self, "تأیید شد", "تأیید QC ثبت شد. این تأیید به‌معنی تغییر خودکار Threshold یا انتشار Template نیست.")
        except Exception as exc: QMessageBox.warning(self, "تأیید متوقف شد", str(exc))
