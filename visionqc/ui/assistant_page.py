from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QSplitter, QTabWidget, QTableWidget,
    QTableWidgetItem, QTextBrowser, QTextEdit, QVBoxLayout, QWidget,
)

from visionqc.ai.config import gemini_api_key
from visionqc.ai.decision_engine import make_final_decision
from visionqc.ai.schemas import AIChatAnswer, AIInspectionResult
from visionqc.ai.speech import speak_text
from visionqc.analysis.custom_rules import CustomRule, RuleCondition, evaluate_custom_rules
from visionqc.assistant import AssistantContext, answer_question
from visionqc.core.rule_repository import delete_rule, list_rules, save_rule, set_rule_enabled
from visionqc.ui.ai_worker import GeminiWorker


METRICS = {
    "Image Quality": ["brightness", "focus_score", "snr_proxy_db", "dark_clipping_percent", "light_clipping_percent"],
    "Color": ["color_uniformity", "lab_chroma_std", "low_saturation_percent", "hue_concentration"],
    "Texture": ["texture_uniformity", "glcm_contrast", "glcm_homogeneity", "lbp_entropy"],
    "Surface": ["bubble_candidate_density", "oily_region_candidate_percent", "specular_reflection_percent"],
}


class OperatorAssistantPage(QWidget):
    navigate = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.context = AssistantContext()
        self.image_path: str | None = None
        self.ai_inspection: AIInspectionResult | None = None
        self.ai_thread: QThread | None = None
        self.ai_worker: GeminiWorker | None = None
        self.tabs = QTabWidget()
        self.tabs.addTab(self._assistant_tab(), "Gemini Inspection & Conversation")
        self.tabs.addTab(self._rules_tab(), "Factory Rule Builder")
        root = QVBoxLayout(self)
        title = QLabel("VisionQC AI Operator Assistant")
        title.setObjectName("PageTitle")
        root.addWidget(title)
        root.addWidget(QLabel("Gemini interprets the image; VisionQC validates the response and exposes only controlled actions. Responses can be spoken by the computer."))
        root.addWidget(self.tabs, 1)
        self.refresh_rules()
        self._refresh_api_state()

    def _assistant_tab(self) -> QWidget:
        page = QWidget(); root = QVBoxLayout(page)
        top = QHBoxLayout()
        self.api_state = QLabel()
        self.model = QComboBox(); self.model.addItems(["gemini-3.6-flash", "gemini-3.1-flash-lite"])
        self.speak = QCheckBox("Speak AI responses"); self.speak.setChecked(True)
        open_settings = QPushButton("API key help"); open_settings.clicked.connect(self._show_key_help)
        top.addWidget(self.api_state); top.addStretch(); top.addWidget(QLabel("Model:")); top.addWidget(self.model); top.addWidget(self.speak); top.addWidget(open_settings)
        root.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        source = QGroupBox("Inspection input"); source_layout = QVBoxLayout(source)
        self.image_preview = QLabel("No image selected"); self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter); self.image_preview.setMinimumSize(360,260); self.image_preview.setStyleSheet("border:1px solid #9aa4b2; border-radius:6px;")
        source_layout.addWidget(self.image_preview,1)
        image_row = QHBoxLayout(); choose=QPushButton("Choose image"); choose.clicked.connect(self.choose_image); clear=QPushButton("Clear"); clear.clicked.connect(self.clear_image); image_row.addWidget(choose); image_row.addWidget(clear); source_layout.addLayout(image_row)
        form=QFormLayout()
        self.process_product=QLineEdit(); self.process_product.setPlaceholderText("Example: Beef sausage batter")
        self.process_stage=QComboBox(); self.process_stage.setEditable(True); self.process_stage.addItems(["Unknown", "Before vacuum", "During mixing", "After vacuum", "Ready for discharge"])
        self.temperature=QLineEdit(); self.temperature.setPlaceholderText("Optional °C")
        self.mixing_time=QLineEdit(); self.mixing_time.setPlaceholderText("Optional minutes")
        self.vacuum=QComboBox(); self.vacuum.addItems(["Unknown", "ON", "OFF"])
        self.notes=QTextEdit(); self.notes.setPlaceholderText("Optional recipe, speed, lighting, operator observations..."); self.notes.setMaximumHeight(80)
        for label,widget in [("Product / recipe",self.process_product),("Process stage",self.process_stage),("Temperature",self.temperature),("Mixing time",self.mixing_time),("Vacuum",self.vacuum),("Notes",self.notes)]: form.addRow(label,widget)
        source_layout.addLayout(form)
        local_row=QHBoxLayout(); load=QPushButton("Load VisionQC JSON"); load.clicked.connect(self.load_context); open_analysis=QPushButton("Open local image analysis"); open_analysis.clicked.connect(lambda:self.navigate.emit("Deep Image Analysis")); local_row.addWidget(load); local_row.addWidget(open_analysis); source_layout.addLayout(local_row)
        self.context_label=QLabel("No local OpenCV analysis loaded"); self.context_label.setWordWrap(True); source_layout.addWidget(self.context_label)
        self.inspect_btn=QPushButton("Analyze image with Gemini"); self.inspect_btn.clicked.connect(self.start_ai_inspection); source_layout.addWidget(self.inspect_btn)
        splitter.addWidget(source)

        console=QGroupBox("Operator console"); console_layout=QVBoxLayout(console)
        self.conversation=QTextBrowser(); self.conversation.setOpenExternalLinks(False); console_layout.addWidget(self.conversation,1)
        quick=QHBoxLayout()
        for text in ("چرا این نتیجه ثبت شد؟", "مشکلات بصری را توضیح بده", "چه اقدام ایمنی انجام دهیم؟"):
            button=QPushButton(text); button.clicked.connect(lambda checked=False,q=text:self.ask(q)); quick.addWidget(button)
        console_layout.addLayout(quick)
        ask_row=QHBoxLayout(); self.question=QLineEdit(); self.question.setPlaceholderText("پیام یا سؤال کاربر را اینجا وارد کنید..."); self.question.returnPressed.connect(lambda:self.ask(self.question.text()))
        self.ask_btn=QPushButton("Send to Gemini"); self.ask_btn.clicked.connect(lambda:self.ask(self.question.text())); ask_row.addWidget(self.question,1); ask_row.addWidget(self.ask_btn); console_layout.addLayout(ask_row)
        self.activity=QLabel("Ready"); console_layout.addWidget(self.activity)
        splitter.addWidget(console); splitter.setSizes([520,760]); root.addWidget(splitter,1)
        return page

    def _refresh_api_state(self) -> None:
        configured=bool(gemini_api_key())
        self.api_state.setText("● Gemini API configured" if configured else "● Gemini API key not configured")
        self.api_state.setStyleSheet("color:#237a3b;font-weight:600" if configured else "color:#b45309;font-weight:600")

    def _show_key_help(self) -> None:
        QMessageBox.information(self,"Gemini API key", "Create a file named .env in the same folder as main.py.\n\nAdd exactly one line:\nGEMINI_API_KEY=PASTE_YOUR_KEY_HERE\n\nSave the file and restart VisionQC. Do not add quotes and do not share the key.")

    def choose_image(self) -> None:
        path,_=QFileDialog.getOpenFileName(self,"Select kettle / sausage batter image","","Images (*.png *.jpg *.jpeg *.bmp *.webp *.tif *.tiff)")
        if not path:return
        pix=QPixmap(path)
        if pix.isNull(): QMessageBox.warning(self,"Invalid image","The selected image could not be opened."); return
        self.image_path=path; self.image_preview.setPixmap(pix.scaled(self.image_preview.size(),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)); self.image_preview.setToolTip(path); self.ai_inspection=None
        self.activity.setText(f"Selected: {Path(path).name}")

    def clear_image(self) -> None:
        self.image_path=None; self.ai_inspection=None; self.image_preview.clear(); self.image_preview.setText("No image selected"); self.activity.setText("Ready")

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if self.image_path:
            pix=QPixmap(self.image_path)
            if not pix.isNull(): self.image_preview.setPixmap(pix.scaled(self.image_preview.size(),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))

    def _process_data(self) -> dict:
        return {"product_or_recipe":self.process_product.text().strip(),"process_stage":self.process_stage.currentText().strip(),"temperature_c":self.temperature.text().strip() or None,"mixing_time_minutes":self.mixing_time.text().strip() or None,"vacuum_status":self.vacuum.currentText(),"operator_notes":self.notes.toPlainText().strip()}

    def _local_context(self) -> dict:
        return {"status":self.context.status,"visual_health_score":self.context.visual_health_score,"analysis_confidence":self.context.analysis_confidence,"metrics":self.context.metrics,"findings":self.context.findings,"product_name":self.context.product_name,"process_stage":self.context.process_stage,"golden_similarity":self.context.golden_similarity}

    def start_ai_inspection(self) -> None:
        self._refresh_api_state()
        if not self.image_path: QMessageBox.information(self,"No image","Choose an image first."); return
        self.conversation.append(f"<p><b>اپراتور:</b> تحلیل تصویر {Path(self.image_path).name}</p>")
        self._start_worker("inspect",process_data=self._process_data(),local_context=self._local_context())

    def ask(self, question: str) -> None:
        question=question.strip()
        if not question:return
        self.conversation.append(f"<p><b>اپراتور:</b> {question}</p>")
        self.question.clear()
        if not gemini_api_key():
            local=answer_question(question,self.context)
            self._append_local_answer(local)
            return
        self._start_worker("chat",question=question,local_context=self._local_context(),inspection=self.ai_inspection)

    def _start_worker(self,mode:str,question:str="",process_data:dict|None=None,local_context:dict|None=None,inspection:AIInspectionResult|None=None)->None:
        if self.ai_thread and self.ai_thread.isRunning(): QMessageBox.information(self,"AI busy","Wait for the current Gemini request to finish."); return
        self._set_busy(True); self.activity.setText("در حال ارتباط با جمنای…")
        self.ai_thread=QThread(self); self.ai_worker=GeminiWorker(mode,self.model.currentText(),self.image_path,question,process_data,local_context,inspection)
        self.ai_worker.moveToThread(self.ai_thread); self.ai_thread.started.connect(self.ai_worker.run); self.ai_worker.completed.connect(self._on_ai_completed); self.ai_worker.failed.connect(self._on_ai_failed); self.ai_worker.finished.connect(self.ai_thread.quit); self.ai_worker.finished.connect(self.ai_worker.deleteLater); self.ai_thread.finished.connect(self.ai_thread.deleteLater); self.ai_thread.finished.connect(lambda:self._set_busy(False)); self.ai_thread.start()

    def _set_busy(self,busy:bool)->None:
        self.inspect_btn.setEnabled(not busy); self.ask_btn.setEnabled(not busy); self.question.setEnabled(not busy)

    def _on_ai_completed(self,result:object)->None:
        self.activity.setText("پاسخ جمنای دریافت شد")
        if isinstance(result,AIInspectionResult):
            self.ai_inspection=result; decision=make_final_decision(result)
            findings="".join(f"<li><b>{f.title_fa}</b> — {f.evidence_fa} (اعتماد {f.confidence:.0f}٪)</li>" for f in result.visual_findings) or "<li>یافته مشخصی ثبت نشد.</li>"
            actions="".join(f"<li>{x}</li>" for x in decision.approved_actions_fa)
            warnings="".join(f"<li>{x}</li>" for x in decision.warnings_fa)
            html=f"<p><b>VisionQC / Gemini — وضعیت نهایی: {decision.status}</b><br>{decision.summary_fa}</p><b>یافته‌های بصری</b><ul>{findings}</ul><b>اقدامات کنترل‌شده VisionQC</b><ul>{actions}</ul>"
            if warnings: html+=f"<b>هشدار</b><ul>{warnings}</ul>"
            html+=f"<small>اعتماد: {decision.confidence:.0f}٪ — این تحلیل جایگزین آزمایش یا تأیید مسئول QC نیست.</small><hr>"
            self.conversation.append(html)
            if self.speak.isChecked(): speak_text(decision.summary_fa+" "+" ".join(decision.approved_actions_fa[:3]))
        elif isinstance(result,AIChatAnswer):
            evidence="".join(f"<li>{x}</li>" for x in result.evidence_fa); actions="".join(f"<li>{x}</li>" for x in result.suggested_actions_fa)
            self.conversation.append(f"<p><b>VisionQC / Gemini:</b> {result.answer_fa}</p><b>شواهد</b><ul>{evidence}</ul><b>پیشنهادها</b><ul>{actions}</ul><small>اعتماد: {result.confidence:.0f}٪ — {result.safety_note_fa}</small><hr>")
            if self.speak.isChecked(): speak_text(result.answer_fa)

    def _on_ai_failed(self,message:str)->None:
        self.activity.setText("درخواست جمنای ناموفق بود"); self.conversation.append(f"<p><b>خطای VisionQC:</b> {message}</p><hr>"); QMessageBox.warning(self,"درخواست جمنای ناموفق بود",message)

    def _append_local_answer(self,answer)->None:
        reasons="".join(f"<li>{item}</li>" for item in answer.reasons); actions="".join(f"<li>{item}</li>" for item in answer.actions)
        self.conversation.append(f"<p><b>دستیار محلی VisionQC — {answer.title}</b><br>{answer.summary}</p><b>شواهد</b><ul>{reasons}</ul><b>اقدامات پیشنهادی</b><ul>{actions}</ul><small>میزان اطمینان: {answer.confidence:.1f}% — {answer.safety_note}</small><hr>")
        if self.speak.isChecked(): speak_text(answer.summary)

    def load_context(self) -> None:
        path,_=QFileDialog.getOpenFileName(self,"Load VisionQC analysis","","JSON files (*.json)")
        if not path:return
        try:
            data=json.loads(Path(path).read_text(encoding="utf-8")); findings=data.get("findings",[])
            self.context=AssistantContext(metrics=data.get("metrics",{}),findings=findings,visual_health_score=data.get("visual_health_score"),analysis_confidence=data.get("analysis_confidence"),status=data.get("status","Unknown"),product_name=data.get("product_name",""),process_stage=data.get("process_stage",""),golden_similarity=data.get("golden_similarity"))
            self.context.custom_rule_results=evaluate_custom_rules(list_rules(True),self.context.metrics,product_name=self.context.product_name,process_stage=self.context.process_stage)
            triggered=sum(1 for item in self.context.custom_rule_results if item.triggered); self.context_label.setText(f"Loaded: {Path(path).name} — {triggered} factory rule(s) triggered"); self.conversation.append("<b>VisionQC:</b> Local OpenCV analysis context loaded.")
        except Exception as exc: QMessageBox.critical(self,"Load failed",str(exc))

    def _rules_tab(self) -> QWidget:
        page=QWidget(); root=QHBoxLayout(page)
        editor=QGroupBox("Create a single-condition rule"); form=QFormLayout(editor)
        self.rule_name=QLineEdit(); self.rule_name.setPlaceholderText("Example: High bubbles with low uniformity")
        self.group=QComboBox(); self.group.addItems(METRICS); self.group.currentTextChanged.connect(self._group_changed)
        self.metric=QComboBox(); self.operator=QComboBox(); self.operator.addItems([">", ">=", "<", "<=", "==", "!=", "between"])
        self.value=QLineEdit("0"); self.second_value=QLineEdit(); self.second_value.setPlaceholderText("Only for between")
        self.severity=QComboBox(); self.severity.addItems(["Information", "Attention", "Warning", "Critical"])
        self.message=QLineEdit("Configured factory condition triggered.")
        self.recommendation=QLineEdit("Request operator and QC review.")
        self.product=QLineEdit(); self.product.setPlaceholderText("Optional product scope")
        self.stage=QLineEdit(); self.stage.setPlaceholderText("Optional process-stage scope")
        self.enabled=QCheckBox("Enabled"); self.enabled.setChecked(True)
        for label,widget in [("Rule name",self.rule_name),("Metric group",self.group),("Metric",self.metric),("Operator",self.operator),("Value",self.value),("Second value",self.second_value),("Severity",self.severity),("Message",self.message),("Recommendation",self.recommendation),("Product",self.product),("Process stage",self.stage)]: form.addRow(label,widget)
        form.addRow(self.enabled)
        save=QPushButton("Save Factory Rule"); save.clicked.connect(self.save_rule); form.addRow(save)
        root.addWidget(editor, 1)
        listing=QGroupBox("Saved factory rules"); right=QVBoxLayout(listing)
        self.rule_table=QTableWidget(0,6); self.rule_table.setHorizontalHeaderLabels(["ID","Name","Metric","Condition","Severity","Enabled"]); self.rule_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        right.addWidget(self.rule_table)
        row=QHBoxLayout(); toggle=QPushButton("Toggle Enabled"); toggle.clicked.connect(self.toggle_rule); remove=QPushButton("Delete Rule"); remove.clicked.connect(self.remove_rule); refresh=QPushButton("Refresh"); refresh.clicked.connect(self.refresh_rules)
        row.addWidget(toggle); row.addWidget(remove); row.addWidget(refresh); right.addLayout(row); root.addWidget(listing,2)
        self._group_changed(self.group.currentText())
        return page

    def _group_changed(self, group: str) -> None:
        self.metric.clear(); self.metric.addItems(METRICS.get(group, []))

    def load_context(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load VisionQC analysis", "", "JSON files (*.json)")
        if not path: return
        try:
            data=json.loads(Path(path).read_text(encoding="utf-8"))
            findings=data.get("findings", [])
            self.context=AssistantContext(metrics=data.get("metrics", {}), findings=findings,
                visual_health_score=data.get("visual_health_score"), analysis_confidence=data.get("analysis_confidence"), status=data.get("status", "Unknown"),
                product_name=data.get("product_name", ""), process_stage=data.get("process_stage", ""), golden_similarity=data.get("golden_similarity"))
            self.context.custom_rule_results=evaluate_custom_rules(list_rules(True), self.context.metrics, product_name=self.context.product_name, process_stage=self.context.process_stage)
            triggered=sum(1 for item in self.context.custom_rule_results if item.triggered)
            self.context_label.setText(f"Loaded: {Path(path).name} — {triggered} factory rule(s) triggered")
            self.conversation.append("<b>VisionQC:</b> Analysis context loaded. Ask a diagnostic question.")
        except Exception as exc:
            QMessageBox.critical(self, "Load failed", str(exc))

    def ask(self, question: str) -> None:
        if not question.strip(): return
        answer=answer_question(question, self.context)
        reasons="".join(f"<li>{item}</li>" for item in answer.reasons)
        actions="".join(f"<li>{item}</li>" for item in answer.actions)
        self.conversation.append(f"<p><b>اپراتور:</b> {question}</p><p><b>VisionQC — {answer.title}</b><br>{answer.summary}</p><b>شواهد</b><ul>{reasons}</ul><b>اقدامات پیشنهادی</b><ul>{actions}</ul><small>میزان اطمینان: {answer.confidence:.1f}% — {answer.safety_note}</small><hr>")
        self.question.clear()

    def save_rule(self) -> None:
        try:
            value=float(self.value.text()); second=float(self.second_value.text()) if self.second_value.text().strip() else None
            rule=CustomRule(name=self.rule_name.text(), conditions=[RuleCondition(self.group.currentText(),self.metric.currentText(),self.operator.currentText(),value,second)], severity=self.severity.currentText(), message=self.message.text(), recommendation=self.recommendation.text(), enabled=self.enabled.isChecked(), product_name=self.product.text(), process_stage=self.stage.text())
            save_rule(rule); self.rule_name.clear(); self.refresh_rules(); QMessageBox.information(self,"Rule saved","The factory rule was saved locally.")
        except Exception as exc: QMessageBox.warning(self,"Invalid rule",str(exc))

    def refresh_rules(self) -> None:
        rules=list_rules(); self.rule_table.setRowCount(len(rules))
        for row,rule in enumerate(rules):
            c=rule.conditions[0]
            values=[rule.rule_id,rule.name,f"{c.metric_group}.{c.metric_name}",f"{c.operator} {c.value}" + (f" and {c.second_value}" if c.second_value is not None else ""),rule.severity,"Yes" if rule.enabled else "No"]
            for col,value in enumerate(values): self.rule_table.setItem(row,col,QTableWidgetItem(str(value)))
        self.rule_table.resizeColumnsToContents()

    def _selected_id(self) -> int | None:
        row=self.rule_table.currentRow()
        return int(self.rule_table.item(row,0).text()) if row >= 0 else None

    def toggle_rule(self) -> None:
        rule_id=self._selected_id()
        if rule_id is None: return
        enabled=self.rule_table.item(self.rule_table.currentRow(),5).text() != "Yes"; set_rule_enabled(rule_id,enabled); self.refresh_rules()

    def remove_rule(self) -> None:
        rule_id=self._selected_id()
        if rule_id is None: return
        if QMessageBox.question(self,"Delete rule","Delete the selected factory rule?") == QMessageBox.StandardButton.Yes:
            delete_rule(rule_id); self.refresh_rules()
