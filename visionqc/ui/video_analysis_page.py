from __future__ import annotations

from pathlib import Path
import tempfile
from PySide6.QtCore import QThread
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDoubleSpinBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QMessageBox, QProgressBar, QPushButton, QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit,
    QVBoxLayout, QWidget)

from visionqc.core.exporter import export_json
from visionqc.ui.chart_widgets import PngPreview
from visionqc.ui.temporal_chart import TemporalChart
from visionqc.ui.video_worker import VideoAnalysisWorker
from visionqc.ui.ai_worker import GeminiWorker
from visionqc.ai.config import gemini_api_key
from visionqc.ai.speech import speak_text
from visionqc.ai.schemas import AIInspectionResult
from visionqc.application.services.hybrid_analysis_service import build_hybrid_video_payload
from visionqc.application.services.operator_alert_service import evaluate_video_alert, record_operator_event
from visionqc.ui.widgets import MetricCard
from visionqc.ui.gemini_review_panel import GeminiReviewPanel
from visionqc.ui.gemini_review_formatter import format_gemini_qc_summary, format_gemini_technical_report
from visionqc.ui.indicator_dashboard import QualityIndicatorDashboard
from visionqc.analysis.decision_fusion import classify_quality, executive_summary_fa, requires_ai_review
from visionqc.analysis.health_fusion import split_health_scores, managerial_reasons_fa, decision_action_fa
from visionqc.analysis.indicator_scoring import recommendations_fa, summarize_temporal_indicators


class VideoAnalysisPage(QWidget):
    def __init__(self) -> None:
        super().__init__(); self.path=None; self.result=None; self.thread=None; self.worker=None; self.ai_thread=None; self.ai_worker=None; self.ai_result=None; self.ai_snapshot_path=None; self.operator_decision=None; self._sample_history=[]; self._build()

    def _build(self):
        root=QVBoxLayout(self); title=QLabel("Video & Temporal Analysis"); title.setObjectName("PageTitle")
        subtitle=QLabel("Analyze MP4, AVI, MOV and MKV files across time, detect instability and preserve key snapshots."); subtitle.setObjectName("PageSubtitle")
        root.addWidget(title); root.addWidget(subtitle)
        bar=QHBoxLayout(); self.load=QPushButton("Load Video"); self.start=QPushButton("Start Temporal Analysis")
        self.cancel=QPushButton("Cancel"); self.cancel.setObjectName("Secondary"); self.cancel.setEnabled(False)
        self.export=QPushButton("Export JSON"); self.export.setObjectName("Secondary"); self.export.setEnabled(False)
        bar.addWidget(self.load); bar.addWidget(QLabel("Sampling interval:")); self.interval=QDoubleSpinBox(); self.interval.setRange(.2,30); self.interval.setValue(1); self.interval.setSuffix(" s")
        bar.addWidget(self.interval); bar.addWidget(self.start); bar.addWidget(self.cancel); bar.addWidget(self.export); bar.addStretch(); root.addLayout(bar)
        self.file_info=QLabel("No video selected"); self.file_info.setObjectName("InfoPanel"); root.addWidget(self.file_info)
        cards=QGridLayout(); self.health=MetricCard("سلامت محصول"); self.process_health=MetricCard("سلامت فرایند"); self.conf=MetricCard("اطمینان تحلیل"); self.status=MetricCard("وضعیت")
        self.stability = self.process_health
        for i,c in enumerate((self.health,self.process_health,self.conf,self.status)): cards.addWidget(c,i//4,i%4)
        root.addLayout(cards)
        tabs=QTabWidget(); self.summary=QTextEdit(); self.summary.setReadOnly(True); self.gemini_review=GeminiReviewPanel(); self.gemini_summary=QTextEdit(); self.gemini_summary.setReadOnly(True); self.gemini_summary.setPlaceholderText("Operator alerts appear only when action is required."); self.chart=TemporalChart()
        self.samples=QTableWidget(0,9); self.samples.setHorizontalHeaderLabels(["Time","Health","Confidence","Status","Brightness","Color Uniformity","Texture Uniformity","Bubble Density","Oil Candidate %"])
        self.samples.horizontalHeader().setStretchLastSection(True)
        self.events=QTableWidget(0,5); self.events.setHorizontalHeaderLabels(["Time","Type","Severity","Message","Value"]); self.events.horizontalHeader().setStretchLastSection(True)
        snap=QWidget(); sl=QVBoxLayout(snap); self.snapshot_selector=QTableWidget(0,2); self.snapshot_selector.setHorizontalHeaderLabels(["Snapshot","Preview"]); self.snapshot_selector.horizontalHeader().setStretchLastSection(True); sl.addWidget(self.snapshot_selector)
        tabs.addTab(self.summary,"Local Summary"); tabs.addTab(self.gemini_review,"بررسی هوش مصنوعی"); tabs.addTab(self.gemini_summary,"Operator Alert"); tabs.addTab(self.chart,"Timeline"); tabs.addTab(self.samples,"Samples"); tabs.addTab(self.events,"Events"); tabs.addTab(snap,"Snapshots")
        root.addWidget(tabs,1)
        self.indicator_dashboard=QualityIndicatorDashboard(); root.addWidget(self.indicator_dashboard)
        row=QHBoxLayout(); self.progress=QProgressBar(); self.activity=QLabel("Ready"); row.addWidget(self.progress,1); row.addWidget(self.activity,1); root.addLayout(row)
        self.load.clicked.connect(self.load_video); self.start.clicked.connect(self.start_analysis); self.cancel.clicked.connect(self.cancel_analysis); self.export.clicked.connect(self.export_result)

    def load_video(self):
        path,_=QFileDialog.getOpenFileName(self,"Select production video","","Video (*.mp4 *.avi *.mov *.mkv *.m4v)")
        if not path:return
        self.path=path; self.operator_decision=None; self.file_info.setText(f"انتخاب‌شده: {Path(path).name}\nتحلیل زمانی بر پایه نمونه‌برداری است و ویدئوی اصلی تغییر نمی‌کند."); self.result=None; self.ai_result=None; self.export.setEnabled(False); self._clear()

    def _clear(self):
        for c in (self.health,self.process_health,self.conf,self.status): c.set_value("—")
        self._sample_history=[]; self.indicator_dashboard.reset(); self.summary.clear(); self.gemini_review.clear(); self.gemini_summary.clear(); self.samples.setRowCount(0); self.events.setRowCount(0); self.snapshot_selector.setRowCount(0); self.chart.set_series({}); self.progress.setValue(0)

    def start_analysis(self):
        if not self.path: QMessageBox.information(self,"No video","Load a video before analysis."); return
        self._clear(); self._busy(True); self.thread=QThread(self); self.worker=VideoAnalysisWorker(self.path,self.interval.value()); self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run); self.worker.progress.connect(self.on_progress); self.worker.sample.connect(self.on_sample); self.worker.completed.connect(self.on_completed); self.worker.failed.connect(self.on_failed)
        self.worker.finished.connect(self.thread.quit); self.worker.finished.connect(self.worker.deleteLater); self.thread.finished.connect(self.thread.deleteLater); self.thread.start()

    def cancel_analysis(self):
        if self.worker: self.worker.cancel(); self.activity.setText("درخواست توقف ثبت شد…")

    def _busy(self,b):
        self.load.setEnabled(not b); self.start.setEnabled(not b); self.interval.setEnabled(not b); self.cancel.setEnabled(b)

    def on_progress(self,v,m): self.progress.setValue(v); self.activity.setText(m)
    def on_sample(self,s):
        self._sample_history.append(s); self._sample_history=self._sample_history[-120:]
        r=self.samples.rowCount(); self.samples.insertRow(r)
        vals=[f"{s.timestamp_seconds:.1f}s",f"{s.visual_health_score:.1f}",f"{s.analysis_confidence:.1f}",s.status,f"{s.brightness:.1f}",f"{s.color_uniformity:.1f}",f"{s.texture_uniformity:.1f}",f"{s.bubble_candidate_density:.2f}",f"{s.oily_region_candidate_percent:.2f}"]
        for i,v in enumerate(vals): self.samples.setItem(r,i,QTableWidgetItem(v))
        from types import SimpleNamespace
        from visionqc.analysis.indicator_scoring import IndicatorScore, recommendations_fa
        focus=max(0,min(100,s.sharpness/4)); exposure=max(0,100-abs(s.brightness-128)*0.75)
        recent=self._sample_history[-60:]; variation=(max(x.visual_health_score for x in recent)-min(x.visual_health_score for x in recent)) if recent else 0
        scores=[
            IndicatorScore("image","کیفیت تصویر",.55*focus+.45*exposure,""), IndicatorScore("color","ثبات رنگ",s.color_uniformity,""),
            IndicatorScore("texture","یکنواختی بافت",s.texture_uniformity,""), IndicatorScore("surface","سلامت سطح",max(0,100-s.oily_region_candidate_percent*3.4),""),
            IndicatorScore("aeration","سلامت هوادهی",max(0,100-s.bubble_candidate_density*4),""), IndicatorScore("motion","ثبات حرکت",s.motion_stability,""),
            IndicatorScore("mixing","پوشش اختلاط",s.mixing_coverage,""), IndicatorScore("reference","تطابق با مرجع",s.visual_health_score,""),
            IndicatorScore("process","ثبات فرایند",max(0,100-variation*1.8),""), IndicatorScore("lighting","نوردهی",exposure,""),
            IndicatorScore("focus","وضوح تصویر",focus,""), IndicatorScore("risk","کنترل ریسک",s.visual_health_score,""),
        ]
        self.indicator_dashboard.update_scores(scores,recommendations_fa(scores))

    def on_completed(self,r):
        self.result=r; self.export.setEnabled(True)
        final_scores = summarize_temporal_indicators(r.samples)
        breakdown = split_health_scores(final_scores, still_image=False) if final_scores else None
        fused_score = breakdown.final_score if breakdown else r.overall_health_score
        decision=classify_quality(fused_score, critical_override=False)
        r.status=decision.status_fa; r.overall_health_score=decision.score
        product_health = breakdown.product_health if breakdown else decision.score
        process_health = breakdown.process_health if breakdown else r.process_stability
        self.health.set_value(f"{product_health:.1f}%"); self.process_health.set_value(f"{process_health:.1f}%"); self.conf.set_value(f"{r.overall_confidence:.1f}%"); self.status.set_value(decision.status_fa)
        significant=[e for e in r.events if str(e.severity).lower() in {"warning","high","critical"}]
        reasons = managerial_reasons_fa(final_scores, breakdown) if breakdown else ["اطلاعات کافی برای تفکیک سلامت محصول و فرایند در دسترس نبود."]
        actions = decision_action_fa(decision.level)
        if decision.level in {"high", "critical"}:
            actions = recommendations_fa(final_scores)[:2] + actions[:1]
        self.summary.setPlainText(executive_summary_fa(decision,reasons,actions,r.overall_confidence, product_health, process_health)+f"\n\nمنبع: {Path(r.source_path).name} | فریم‌های تحلیل‌شده: {r.analyzed_frames} | رخدادهای معنادار: {len(significant)}")
        if final_scores:
            self.indicator_dashboard.update_scores(final_scores, actions)
        self.chart.set_series({"Health":[(s.timestamp_seconds,s.visual_health_score) for s in r.samples],"Confidence":[(s.timestamp_seconds,s.analysis_confidence) for s in r.samples],"Texture":[(s.timestamp_seconds,s.texture_uniformity) for s in r.samples]})
        self.events.setRowCount(len(r.events))
        for row,e in enumerate(r.events):
            for col,v in enumerate([f"{e.timestamp_seconds:.1f}s",e.event_type,e.severity,e.message,"" if e.value is None else f"{e.value:.2f}"]): self.events.setItem(row,col,QTableWidgetItem(v))
        self.snapshot_selector.setRowCount(len(r.snapshots_jpeg))
        for row,(name,data) in enumerate(r.snapshots_jpeg.items()):
            self.snapshot_selector.setItem(row,0,QTableWidgetItem(name)); label=QLabel(); pix=QPixmap(); pix.loadFromData(data); label.setPixmap(pix.scaled(220,125)); self.snapshot_selector.setCellWidget(row,1,label); self.snapshot_selector.setRowHeight(row,135)
        if gemini_api_key() and r.snapshots_jpeg and requires_ai_review(decision.score, critical_override=decision.level=="critical"):
            self.progress.setValue(92)
            self.activity.setText("تحلیل زمانی تکمیل شد. فریم نماینده و شاخص‌های روند برای هوش مصنوعی ارسال می‌شوند…")
            self._start_gemini_review(r)
        else:
            if decision.score >= 80.0:
                note = "امتیاز نهایی ۸۰ یا بیشتر است؛ طبق سیاست مصرف، نیازی به بازبینی هوش مصنوعی نبود."
            else:
                note = "بازبینی هوش مصنوعی در دسترس نیست یا فریم نماینده وجود ندارد."
            self.gemini_review.set_reports(format_gemini_qc_summary(None, note), format_gemini_technical_report(None, note))
            self._finalize_operator_alert(r, None, "تحلیل زمانی تکمیل شد")
            self._busy(False)

    def _start_gemini_review(self, result):
        name, data = next(iter(result.snapshots_jpeg.items()))
        handle = tempfile.NamedTemporaryFile(prefix="visionqc_video_frame_", suffix=".jpg", delete=False)
        handle.write(data); handle.close()
        self.ai_snapshot_path = handle.name
        context = result.to_dict()
        context["representative_snapshot"] = name
        self.ai_thread = QThread(self)
        self.ai_worker = GeminiWorker(
            "inspect", "gemini-3.6-flash", self.ai_snapshot_path,
            process_data={"source": "Video & Temporal Analysis", "video_name": Path(result.source_path).name},
            local_context=context,
        )
        self.ai_worker.moveToThread(self.ai_thread)
        self.ai_thread.started.connect(self.ai_worker.run)
        self.ai_worker.completed.connect(self._on_gemini_completed)
        self.ai_worker.failed.connect(self._on_gemini_failed)
        self.ai_worker.finished.connect(self.ai_thread.quit)
        self.ai_worker.finished.connect(self.ai_worker.deleteLater)
        self.ai_thread.finished.connect(self.ai_thread.deleteLater)
        self.ai_thread.finished.connect(self._cleanup_ai_snapshot)
        self.ai_thread.finished.connect(lambda: self._busy(False))
        self.ai_thread.start()

    def _on_gemini_completed(self, result: AIInspectionResult):
        self.ai_result = result
        self.indicator_dashboard.update_scores([], [], result.operator_summary_fa)
        self.gemini_review.set_reports(format_gemini_qc_summary(result), format_gemini_technical_report(result))
        self._finalize_operator_alert(self.result, result, "Video analysis completed")

    def _on_gemini_failed(self, message):
        self.ai_result = None
        self.gemini_review.set_reports(format_gemini_qc_summary(None, message), format_gemini_technical_report(None, message))
        self._finalize_operator_alert(self.result, None, "Temporal analysis completed — بازبینی هوش مصنوعی در دسترس نیست")

    def _finalize_operator_alert(self, local_result, ai_result, activity_text):
        if local_result is None:
            return
        decision = evaluate_video_alert(local_result, ai_result)
        self.operator_decision = decision
        record_operator_event("video", local_result, ai_result, decision)
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
        self.export.setEnabled(True)
        self.progress.setValue(100)
        self.activity.setText(activity_text)

    def _cleanup_ai_snapshot(self):
        if self.ai_snapshot_path:
            try: Path(self.ai_snapshot_path).unlink(missing_ok=True)
            except OSError: pass
            self.ai_snapshot_path = None

    def on_failed(self,msg): QMessageBox.critical(self,"تحلیل ویدئو ناموفق بود",msg); self.activity.setText("تحلیل ویدئو ناموفق بود"); self._busy(False)
    def export_result(self):
        if not self.result:return
        path,_=QFileDialog.getSaveFileName(self,"Export hybrid temporal result",Path(self.result.source_path).stem+"_hybrid_temporal.json","JSON (*.json)")
        if path:
            import json
            payload = build_hybrid_video_payload(self.result, self.ai_result)
            payload["operator_alert"] = self.operator_decision.to_dict() if self.operator_decision else None
            Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            QMessageBox.information(self,"Export completed",path)
