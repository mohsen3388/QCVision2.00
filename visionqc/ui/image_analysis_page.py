from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QProgressBar, QPushButton, QSplitter, QTabWidget, QTableWidget,
    QTableWidgetItem, QTextEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from visionqc.core.exporter import export_json
from visionqc.ai.config import gemini_api_key
from visionqc.ai.speech import speak_text
from visionqc.ai.schemas import AIInspectionResult
from visionqc.application.services.hybrid_analysis_service import build_hybrid_payload
from visionqc.application.services.operator_alert_service import evaluate_image_alert, record_operator_event
from visionqc.models.results import AnalysisResult
from visionqc.ui.chart_widgets import HistogramWidget, PngPreview
from visionqc.ui.roi_label import RoiImageLabel
from visionqc.ui.widgets import MetricCard
from visionqc.ui.gemini_review_panel import GeminiReviewPanel
from visionqc.ui.worker import AnalysisWorker
from visionqc.ui.ai_worker import GeminiWorker
from visionqc.ui.gemini_review_formatter import format_gemini_qc_summary, format_gemini_technical_report
from visionqc.ui.indicator_dashboard import QualityIndicatorDashboard
from visionqc.analysis.indicator_scoring import score_still_indicators, recommendations_fa
from visionqc.analysis.decision_fusion import classify_quality, executive_summary_fa, requires_ai_review
from visionqc.analysis.health_fusion import split_health_scores, managerial_reasons_fa, decision_action_fa


class ImageAnalysisPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.image_path: str | None = None
        self.result: AnalysisResult | None = None
        self.thread: QThread | None = None
        self.worker: AnalysisWorker | None = None
        self.ai_thread: QThread | None = None
        self.ai_worker: GeminiWorker | None = None
        self.ai_result: AIInspectionResult | None = None
        self.operator_decision = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        title = QLabel("Deep Image Analysis"); title.setObjectName("PageTitle")
        subtitle = QLabel("ROI analysis with expanded acquisition, color, GLCM, LBP, surface and explainability data."); subtitle.setObjectName("PageSubtitle")
        root.addWidget(title); root.addWidget(subtitle)
        toolbar = QHBoxLayout()
        self.load_btn = QPushButton("Load Image")
        self.clear_roi_btn = QPushButton("Clear ROI"); self.clear_roi_btn.setObjectName("Secondary")
        self.analyze_btn = QPushButton("Analyze Deeply")
        self.export_btn = QPushButton("Export JSON"); self.export_btn.setObjectName("Secondary"); self.export_btn.setEnabled(False)
        for b in (self.load_btn, self.clear_roi_btn, self.analyze_btn, self.export_btn): toolbar.addWidget(b)
        toolbar.addStretch(); root.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QFrame(); left.setObjectName("Card"); left_layout = QVBoxLayout(left)
        self.image_label = RoiImageLabel(); self.roi_label = QLabel("ROI: Full image"); self.roi_label.setObjectName("Muted")
        left_layout.addWidget(self.image_label, 1); left_layout.addWidget(self.roi_label); splitter.addWidget(left)

        right = QWidget(); right_layout = QVBoxLayout(right)
        cards = QGridLayout()
        self.health_card = MetricCard("سلامت محصول"); self.confidence_card = MetricCard("قابلیت ارزیابی تصویر")
        self.status_card = MetricCard("وضعیت"); self.finding_card = MetricCard("یافته‌های تأییدشده")
        cards.addWidget(self.health_card,0,0); cards.addWidget(self.confidence_card,0,1); cards.addWidget(self.status_card,1,0); cards.addWidget(self.finding_card,1,1)
        right_layout.addLayout(cards)
        self.tabs = QTabWidget()
        self.summary = QTextEdit(); self.summary.setReadOnly(True)
        self.gemini_review = GeminiReviewPanel()
        self.gemini_summary = QTextEdit(); self.gemini_summary.setReadOnly(True)
        self.gemini_summary.setPlaceholderText("Operator alerts appear only when action is required. Healthy results are recorded silently.")

        metric_tab = QWidget(); metric_layout = QVBoxLayout(metric_tab)
        filter_row = QHBoxLayout(); self.metric_search = QLineEdit(); self.metric_search.setPlaceholderText("Search metrics…")
        self.group_filter = QComboBox(); self.group_filter.addItem("All groups")
        filter_row.addWidget(self.metric_search,1); filter_row.addWidget(self.group_filter); metric_layout.addLayout(filter_row)
        self.metrics_table = QTableWidget(0,3); self.metrics_table.setHorizontalHeaderLabels(["Group","Metric","Value"]); self.metrics_table.horizontalHeader().setStretchLastSection(True)
        metric_layout.addWidget(self.metrics_table)

        self.rules_tree = QTreeWidget(); self.rules_tree.setHeaderLabels(["Rule / Evidence","Value"]); self.rules_tree.header().setStretchLastSection(True)
        self.histogram = HistogramWidget()
        visual_tab = QWidget(); visual_layout = QVBoxLayout(visual_tab)
        vis_row = QHBoxLayout(); vis_row.addWidget(QLabel("Diagnostic view:")); self.visual_selector = QComboBox(); vis_row.addWidget(self.visual_selector); vis_row.addStretch(); visual_layout.addLayout(vis_row)
        self.visual_preview = PngPreview(); visual_layout.addWidget(self.visual_preview,1)

        self.tabs.addTab(self.summary,"خلاصه مدیریتی"); self.tabs.addTab(self.gemini_review,"بازبینی هوش مصنوعی"); self.tabs.addTab(self.gemini_summary,"هشدار اپراتور"); self.tabs.addTab(metric_tab,"Technical Metrics")
        self.tabs.addTab(self.histogram,"Histograms"); self.tabs.addTab(visual_tab,"Heatmaps & Overlays"); self.tabs.addTab(self.rules_tree,"Rule Traceability")
        right_layout.addWidget(self.tabs,1); splitter.addWidget(right); splitter.setSizes([650,750]); root.addWidget(splitter,1)
        self.indicator_dashboard = QualityIndicatorDashboard(); root.addWidget(self.indicator_dashboard)

        progress_row = QHBoxLayout(); self.progress = QProgressBar(); self.activity = QLabel("Ready")
        progress_row.addWidget(self.progress,1); progress_row.addWidget(self.activity,1); root.addLayout(progress_row)
        self.load_btn.clicked.connect(self.load_image); self.clear_roi_btn.clicked.connect(self.image_label.clear_roi)
        self.analyze_btn.clicked.connect(self.start_analysis); self.export_btn.clicked.connect(self.export_result)
        self.image_label.roi_changed.connect(self.on_roi_changed); self.metric_search.textChanged.connect(self._filter_metrics)
        self.group_filter.currentTextChanged.connect(self._filter_metrics); self.visual_selector.currentTextChanged.connect(self._show_visual)

    def load_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self,"Select image","","Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)")
        if not path: return
        pixmap = QPixmap(path)
        if pixmap.isNull(): QMessageBox.warning(self,"Invalid image","The image could not be displayed."); return
        self.image_path = path; self.image_label.set_source_pixmap(pixmap); self.activity.setText(f"Loaded: {Path(path).name}")
        self.progress.setValue(0); self.result = None; self.ai_result = None; self.operator_decision = None; self.export_btn.setEnabled(False); self._clear_results()

    def on_roi_changed(self, roi) -> None:
        self.roi_label.setText("ROI: Full image" if roi is None else f"ROI: x={roi[0]}, y={roi[1]}, w={roi[2]}, h={roi[3]}")

    def start_analysis(self) -> None:
        if not self.image_path: QMessageBox.information(self,"No image","Load an image before analysis."); return
        self._set_busy(True); self.progress.setValue(0); self.thread = QThread(self)
        self.worker = AnalysisWorker(self.image_path, self.image_label.image_roi()); self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run); self.worker.progress.connect(self.on_progress); self.worker.completed.connect(self.on_completed)
        self.worker.failed.connect(self.on_failed); self.worker.finished.connect(self.thread.quit); self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater); self.thread.start()

    def on_progress(self, value: int, message: str) -> None: self.progress.setValue(value); self.activity.setText(message)
    def on_completed(self, result: AnalysisResult) -> None:
        from types import SimpleNamespace
        self.result = result
        sample = SimpleNamespace(
            visual_health_score=result.visual_health_score, color_uniformity=result.metrics.get("Color",{}).get("color_uniformity",100),
            texture_uniformity=result.metrics.get("Texture",{}).get("texture_uniformity",100),
            bubble_candidate_density=result.metrics.get("Surface",{}).get("bubble_candidate_density",0),
            oily_region_candidate_percent=result.metrics.get("Surface",{}).get("oily_region_candidate_percent",0),
            motion_stability=100.0, mixing_coverage=100.0,
        )
        scores=score_still_indicators(result,sample)
        breakdown=split_health_scores(scores, still_image=True)
        critical_override=any(f.triggered and str(f.severity).lower()=="critical" for f in result.findings)
        # A still image may trigger a critical override only when at least two
        # product indicators corroborate the finding. This prevents a single
        # circle/reflection detector from declaring a healthy product critical.
        critical_override = critical_override and breakdown.product_weak_count >= 2 and breakdown.product_health < 50
        decision=classify_quality(breakdown.final_score,critical_override=critical_override)
        result.visual_health_score=decision.score; result.status=decision.status_fa
        self._render_result(result)
        self.health_card.set_value(f"{breakdown.product_health:.1f}%")
        self.confidence_card.set_value(f"{breakdown.process_health:.1f}%")
        reasons = managerial_reasons_fa(scores, breakdown)
        actions = decision_action_fa(decision.level, still_image=True)
        if decision.level in {"high", "critical"}:
            actions = recommendations_fa(scores)[:2] + actions[:1]
        self.summary.setPlainText(executive_summary_fa(decision,reasons,actions,result.analysis_confidence, breakdown.product_health, breakdown.process_health, "قابلیت ارزیابی تصویر"))
        self.indicator_dashboard.update_scores(scores,actions)
        self.progress.setValue(82)
        if gemini_api_key() and requires_ai_review(decision.score,critical_override=critical_override):
            self.activity.setText("تحلیل داخلی تکمیل شد. مورد برای بازبینی تخصصی هوش مصنوعی ارسال می‌شود…")
            self._start_gemini_analysis(result)
        else:
            if decision.requires_ai and not gemini_api_key():
                self.gemini_review.set_reports(format_gemini_qc_summary(None, "دسترسی هوش مصنوعی تنظیم نشده است."), format_gemini_technical_report(None, "دسترسی هوش مصنوعی تنظیم نشده است."))
            self._finalize_operator_alert(result, None, "تحلیل تکمیل شد")

    def _start_gemini_analysis(self, result: AnalysisResult) -> None:
        self.ai_thread = QThread(self)
        self.ai_worker = GeminiWorker(
            "inspect",
            "gemini-3.6-flash",
            self.image_path,
            process_data={"source": "Deep Image Analysis", "roi": result.roi},
            local_context=result.to_dict(),
        )
        self.ai_worker.moveToThread(self.ai_thread)
        self.ai_thread.started.connect(self.ai_worker.run)
        self.ai_worker.completed.connect(self._on_gemini_completed)
        self.ai_worker.failed.connect(self._on_gemini_failed)
        self.ai_worker.finished.connect(self.ai_thread.quit)
        self.ai_worker.finished.connect(self.ai_worker.deleteLater)
        self.ai_thread.finished.connect(self.ai_thread.deleteLater)
        self.ai_thread.finished.connect(lambda: self._set_busy(False))
        self.ai_thread.start()

    def _on_gemini_completed(self, result: AIInspectionResult) -> None:
        self.ai_result = result
        self.gemini_review.set_reports(format_gemini_qc_summary(result), format_gemini_technical_report(result))
        self._finalize_operator_alert(self.result, result, "Analysis completed")

    def _on_gemini_failed(self, message: str) -> None:
        self.ai_result = None
        self.gemini_review.set_reports(format_gemini_qc_summary(None, message), format_gemini_technical_report(None, message))
        self._finalize_operator_alert(self.result, None, "Local analysis completed — بازبینی هوش مصنوعی در دسترس نیست")

    def _finalize_operator_alert(self, local_result: AnalysisResult | None, ai_result: AIInspectionResult | None, activity_text: str) -> None:
        if local_result is None:
            return
        decision = evaluate_image_alert(local_result, ai_result)
        self.operator_decision = decision
        record_operator_event("image", local_result, ai_result, decision)
        if decision.level == "silent":
            self.gemini_summary.setPlainText(
                "وضعیت پایدار است. نتیجه ثبت شد و پیام صوتی برای اپراتور پخش نشد."
            )
        else:
            lines = [
                f"سطح هشدار اپراتور: {decision.level.upper()}",
                f"پیام کوتاه هدست: {decision.voice_message_fa}",
            ]
            if decision.immediate_actions_fa:
                lines.extend(["", "اقدام پیشنهادی اول:", f"1. {decision.immediate_actions_fa[0]}"])
            self.gemini_summary.setPlainText("\n".join(lines))
            speak_text(decision.voice_message_fa)
        self.export_btn.setEnabled(True)
        self.progress.setValue(100)
        self.activity.setText(activity_text)

    def on_failed(self, message: str) -> None: QMessageBox.critical(self,"تحلیل ناموفق بود",message); self.activity.setText("تحلیل ناموفق بود")
    def _set_busy(self,busy:bool)->None:
        for b in (self.load_btn,self.analyze_btn,self.clear_roi_btn): b.setEnabled(not busy)

    def _clear_results(self)->None:
        for c in (self.health_card,self.confidence_card,self.status_card,self.finding_card): c.set_value("—")
        self.metrics_table.setRowCount(0); self.rules_tree.clear(); self.summary.clear(); self.gemini_review.clear(); self.gemini_summary.clear(); self.histogram.set_series({})
        self.visual_selector.clear(); self.visual_preview.setText("نمایش تشخیصی در دسترس نیست")

    def _render_result(self,result:AnalysisResult)->None:
        triggered=[f for f in result.findings if f.triggered]
        self.health_card.set_value(f"{result.visual_health_score:.1f}%"); self.confidence_card.set_value(f"{result.analysis_confidence:.1f}%")
        self.status_card.set_value(result.status); self.finding_card.set_value(str(len(triggered)))
        metric_count=sum(len(v) for v in result.metrics.values())
        lines=[f"وضعیت: {result.status}",f"سلامت بصری: {result.visual_health_score:.2f}%",f"اطمینان تحلیل: {result.analysis_confidence:.2f}%",
               f"تعداد اندازه‌گیری‌های فنی: {metric_count}",f"تعداد نمایش‌های تشخیصی: {len(result.visualization_png)}","",
               "تفسیر: این موارد شاخص‌های بصری قابل توضیح هستند و نتیجه قطعی آزمایشگاهی کیفیت مواد غذایی محسوب نمی‌شوند.","","یافته‌های فعال‌شده:"]
        if not triggered: lines.append("هیچ قاعده موقتی فعال نشد.")
        for f in triggered: lines += [f"• [{f.severity}] {f.title}",f"  علت: {f.reason}",f"  میزان اطمینان: {f.confidence:.1f}%",f"  اقدام پیشنهادی: {f.recommendation}"]
        self.summary.setPlainText("\n".join(lines))
        self.metrics_table.setRowCount(metric_count); self.group_filter.blockSignals(True); self.group_filter.clear(); self.group_filter.addItem("All groups")
        self.group_filter.addItems(result.metrics.keys()); self.group_filter.blockSignals(False)
        i=0
        for group,values in result.metrics.items():
            for name,value in values.items():
                self.metrics_table.setItem(i,0,QTableWidgetItem(group)); self.metrics_table.setItem(i,1,QTableWidgetItem(name.replace("_"," ").title())); self.metrics_table.setItem(i,2,QTableWidgetItem(f"{value:.3f}")); i+=1
        self.metrics_table.resizeColumnsToContents(); self.histogram.set_series(result.distributions)
        self.visual_selector.blockSignals(True); self.visual_selector.clear(); self.visual_selector.addItems(result.visualization_png.keys()); self.visual_selector.blockSignals(False)
        if self.visual_selector.count(): self.visual_selector.setCurrentIndex(0); self._show_visual(self.visual_selector.currentText())
        self.rules_tree.clear(); severity_colors={"Critical":"#b71c1c","Warning":"#e65100","Attention":"#a36b00"}
        for f in result.findings:
            root=QTreeWidgetItem([f"{f.rule_id} — {f.title}","TRIGGERED" if f.triggered else "Not triggered"])
            if f.triggered: root.setForeground(0,QColor(severity_colors.get(f.severity,"#555")))
            for k,v in [("Severity",f.severity),("Confidence",f"{f.confidence:.2f}%"),("Reason",f.reason),("Recommendation",f.recommendation),("Knowledge source",f.source)]: root.addChild(QTreeWidgetItem([k,str(v)]))
            ev=QTreeWidgetItem(["Evidence",""])
            for k,v in f.evidence.items(): ev.addChild(QTreeWidgetItem([str(k),str(v)]))
            root.addChild(ev); self.rules_tree.addTopLevelItem(root)
        self.rules_tree.expandToDepth(0)

    def _filter_metrics(self,*args)->None:
        text=self.metric_search.text().strip().lower(); group=self.group_filter.currentText()
        for row in range(self.metrics_table.rowCount()):
            g=self.metrics_table.item(row,0).text(); n=self.metrics_table.item(row,1).text().lower()
            self.metrics_table.setRowHidden(row, not ((group=="All groups" or g==group) and (not text or text in n or text in g.lower())))

    def _show_visual(self,name:str)->None:
        if self.result and name in self.result.visualization_png: self.visual_preview.set_png(self.result.visualization_png[name])

    def export_result(self)->None:
        if not self.result: return
        default=Path(self.result.source_path).stem+"_visionqc_hybrid_analysis.json"
        path,_=QFileDialog.getSaveFileName(self,"Export hybrid analysis",default,"JSON (*.json)")
        if path:
            import json
            payload = build_hybrid_payload(self.result, self.ai_result)
            payload["operator_alert"] = self.operator_decision.to_dict() if self.operator_decision else None
            Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            QMessageBox.information(self,"Export completed",f"Hybrid analysis exported to:\n{path}")
