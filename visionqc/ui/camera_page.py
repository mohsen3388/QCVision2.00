from __future__ import annotations

from datetime import datetime
from pathlib import Path
import time
import json


from PySide6.QtCore import QThread, Qt, Slot
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTabWidget, QTableWidget, QTableWidgetItem,
    QTextEdit, QVBoxLayout, QWidget,
)

from visionqc.ai.config import gemini_api_key
from visionqc.analysis.live_stream import build_temporal_contact_sheet
from visionqc.ai.schemas import AIInspectionResult
from visionqc.ai.speech import speak_text
from visionqc.application.services.operator_alert_service import (
    OperatorAlertDecision, evaluate_image_alert, record_operator_event,
)
from visionqc.capture.sources import probe_source, validate_network_url
from visionqc.core.settings import app_data_dir
from visionqc.models.results import AnalysisResult
from visionqc.ui.ai_worker import GeminiWorker
from visionqc.ui.camera_worker import CameraWorker
from visionqc.ui.gemini_review_formatter import format_gemini_qc_summary, format_gemini_technical_report
from visionqc.ui.gemini_review_panel import GeminiReviewPanel
from visionqc.ui.temporal_chart import TemporalChart
from visionqc.ui.widgets import MetricCard
from visionqc.ui.indicator_dashboard import QualityIndicatorDashboard
from visionqc.analysis.indicator_scoring import score_indicators, recommendations_fa
from visionqc.analysis.decision_fusion import classify_quality, requires_ai_review, executive_summary_fa
from visionqc.analysis.health_fusion import split_health_scores, managerial_reasons_fa, decision_action_fa


class CameraPage(QWidget):
    """Continuous camera monitoring using the same hybrid path as Deep Image Analysis."""

    GEMINI_COOLDOWN_SECONDS = 12.0
    GEMINI_NORMAL_INTERVAL_SECONDS = 20.0
    ROLLING_FRAME_COUNT = 6
    HEADSET_COOLDOWN_SECONDS = 30.0
    PERSISTENCE_SAMPLES = 3

    def __init__(self, network: bool = False) -> None:
        super().__init__()
        self.network = network
        self.thread = None
        self.worker = None
        self.samples = []
        self.ai_thread: QThread | None = None
        self.ai_worker: GeminiWorker | None = None
        self._ai_busy = False
        self._latest_local: AnalysisResult | None = None
        self._latest_sample = None
        self._last_status = ""
        self._status_streak = 0
        self._last_gemini_at = 0.0
        self._last_headset_at = 0.0
        self._last_spoken_level = "silent"
        self._pending_frame_path: Path | None = None
        self._rolling_frames: list[tuple[float, bytes]] = []
        self._rolling_metrics: list[dict] = []
        self._previous_gemini_summary = ""
        self._stream_started_at = 0.0
        self._gemini_review_count = 0
        self._pending_local_result: AnalysisResult | None = None
        self._pending_predictive = False
        self._last_chart_update = 0.0
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        title = QLabel("Phone / IP Camera" if self.network else "Live USB Camera")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Continuous hybrid monitoring: local analysis runs periodically; فریم‌های معنادار در شرایط لازم توسط هوش مصنوعی بازبینی می‌شوند."
            if not self.network else
            "Continuous hybrid monitoring of an RTSP/HTTP stream with local analysis and بازبینی رویدادمحور هوش مصنوعی."
        )
        subtitle.setObjectName("PageSubtitle")
        root.addWidget(title)
        root.addWidget(subtitle)
        self.registered_context = QLabel("")
        self.registered_context.setObjectName("InfoPanel")
        self.registered_context.setWordWrap(True)
        self.registered_context.hide()
        root.addWidget(self.registered_context)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Stream URL:" if self.network else "Camera index:"))
        self.source = QLineEdit()
        self.source.setPlaceholderText("rtsp://user:password@192.168.1.50:554/stream" if self.network else "0")
        self.source.setText("" if self.network else "0")
        self.probe = QPushButton("Test Connection")
        self.start = QPushButton("Start Monitoring")
        self.stop = QPushButton("Stop")
        self.stop.setObjectName("Secondary")
        self.stop.setEnabled(False)
        bar.addWidget(self.source, 1)
        bar.addWidget(QLabel("Analyze every"))
        self.interval = QDoubleSpinBox()
        self.interval.setRange(.5, 30)
        self.interval.setValue(2)
        self.interval.setSuffix(" s")
        bar.addWidget(self.interval)
        bar.addWidget(self.probe)
        bar.addWidget(self.start)
        bar.addWidget(self.stop)
        root.addLayout(bar)

        if self.network:
            hint = QLabel("Phone option: use a trusted local stream. Credentials and analysis remain local به‌جز بازبینی‌های انتخابی هوش مصنوعی.")
            hint.setWordWrap(True)
            hint.setObjectName("InfoPanel")
            root.addWidget(hint)

        content = QHBoxLayout()
        preview_card = QFrame()
        preview_card.setObjectName("Card")
        pv = QVBoxLayout(preview_card)
        self.preview = QLabel("Camera preview")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(640, 420)
        self.preview.setStyleSheet("background:#101820;color:#b8c7d1;border-radius:8px;")
        self.connection = QLabel("Disconnected")
        self.connection.setObjectName("Muted")
        pv.addWidget(self.preview, 1)
        pv.addWidget(self.connection)
        content.addWidget(preview_card, 3)

        self.tabs = QTabWidget()
        overview = QWidget()
        right = QVBoxLayout(overview)
        cards = QGridLayout()
        self.health = MetricCard("سلامت محصول")
        self.process_health = MetricCard("سلامت فرایند")
        self.conf = MetricCard("اطمینان تحلیل")
        self.texture = self.process_health
        self.status_card = MetricCard("وضعیت")
        for i, card in enumerate((self.health, self.process_health, self.conf, self.status_card)):
            cards.addWidget(card, i // 2, i % 2)
        right.addLayout(cards)
        self.chart = TemporalChart()
        right.addWidget(self.chart, 1)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["زمان", "امتیاز تصمیم", "اطمینان", "بافت", "وضعیت"])
        self.table.horizontalHeader().setStretchLastSection(True)
        right.addWidget(self.table, 1)

        self.gemini_review = GeminiReviewPanel()
        self.operator_alert = QTextEdit()
        self.operator_alert.setReadOnly(True)
        self.operator_alert.setPlaceholderText("All detected alerts appear here and are spoken briefly through the operator headset.")
        self.timeline = QTableWidget(0, 5)
        self.timeline.setHorizontalHeaderLabels(["Time", "Source", "Level", "Event", "Headset"])
        self.timeline.horizontalHeader().setStretchLastSection(True)

        self.tabs.addTab(overview, "Live Trends")
        self.tabs.addTab(self.gemini_review, "بررسی هوش مصنوعی")
        self.tabs.addTab(self.operator_alert, "Operator Alert")
        self.tabs.addTab(self.timeline, "Event Timeline")
        content.addWidget(self.tabs, 2)
        root.addLayout(content, 1)
        self.indicator_dashboard = QualityIndicatorDashboard()
        root.addWidget(self.indicator_dashboard)

        self.probe.clicked.connect(self.test_connection)
        self.start.clicked.connect(self.start_monitoring)
        self.stop.clicked.connect(self.stop_monitoring)

    def configure_registered_camera(self, camera) -> None:
        """Load topology and responsibility context from Factory Camera Center."""
        if camera.source_type == "RTSP" and self.network:
            self.source.setText(camera.source_value)
        elif camera.source_type == "USB" and not self.network:
            self.source.setText(camera.source_value or "0")
        profile = camera.profile
        owners = [x for x in (camera.operator_fa, camera.qc_manager_fa, camera.hse_owner_fa) if x]
        self.registered_context.setText(
            f"دوربین ثبت‌شده: {camera.name_fa} | ناحیه: {camera.area_fa} | دستگاه: {camera.asset_fa or '—'} | "
            f"پروفایل: {profile.title_fa} | مسئولان: {'، '.join(owners) if owners else profile.default_owner_role_fa}"
        )
        self.registered_context.show()
        self.connection.setText(f"آماده اتصال — {camera.name_fa}")

    def _validated_source(self):
        value = self.source.text().strip()
        if self.network:
            ok, msg = validate_network_url(value)
            if not ok:
                QMessageBox.warning(self, "Invalid stream URL", msg)
                return None
            return value
        if not value.isdigit():
            QMessageBox.warning(self, "Invalid camera index", "Enter 0 for the first camera, 1 for the second, and so on.")
            return None
        return int(value)

    def test_connection(self):
        source = self._validated_source()
        if source is None:
            return
        self.connection.setText("در حال آزمایش اتصال…")
        info = probe_source(source)
        if info.opened:
            QMessageBox.information(self, "Connection successful", f"{info.message}\nResolution: {info.width} × {info.height}\nReported FPS: {info.fps:.1f}")
            self.connection.setText(f"در دسترس: {info.width}×{info.height}, {info.fps:.1f} FPS")
        else:
            QMessageBox.warning(self, "اتصال ناموفق بود", info.message)
            self.connection.setText("اتصال ناموفق بود")

    def start_monitoring(self):
        source = self._validated_source()
        if source is None:
            return
        self.samples = []
        self.table.setRowCount(0)
        self.timeline.setRowCount(0)
        self.chart.set_series({})
        self.gemini_review.clear()
        self.operator_alert.clear()
        self.indicator_dashboard.reset()
        self._last_status = ""
        self._status_streak = 0
        self._last_gemini_at = 0.0
        self._last_headset_at = 0.0
        self._last_spoken_level = "silent"
        self._rolling_frames = []
        self._rolling_metrics = []
        self._previous_gemini_summary = ""
        self._stream_started_at = time.monotonic()
        self._gemini_review_count = 0
        self._busy(True)
        self.thread = QThread(self)
        self.worker = CameraWorker(source, self.interval.value())
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.frame_ready.connect(self.on_frame)
        self.worker.sample_ready.connect(self.on_sample)
        self.worker.analysis_ready.connect(self.on_local_analysis)
        self.worker.status.connect(self.connection.setText)
        self.worker.failed.connect(self.on_failed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(lambda: self._busy(False))
        self.thread.start()

    def stop_monitoring(self):
        if self.worker:
            self.worker.stop()
            self.connection.setText("در حال توقف…")

    def _busy(self, busy):
        self.start.setEnabled(not busy)
        self.probe.setEnabled(not busy)
        self.source.setEnabled(not busy)
        self.interval.setEnabled(not busy)
        self.stop.setEnabled(busy)

    def on_frame(self, data, width, height):
        pix = QPixmap()
        pix.loadFromData(data)
        self.preview.setPixmap(pix.scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation))

    def on_sample(self, sample):
        self.samples.append(sample)
        self.samples = self.samples[-120:]
        row = self.table.rowCount()
        self.table.insertRow(row)
        for index, value in enumerate([
            f"{sample.timestamp_seconds:.1f}s",
            f"{sample.visual_health_score:.1f}",
            f"{sample.analysis_confidence:.1f}",
            f"{sample.texture_uniformity:.1f}",
            sample.status,
        ]):
            self.table.setItem(row, index, QTableWidgetItem(value))
        if self.table.rowCount() > 120:
            self.table.removeRow(0)
        now = time.monotonic()
        if now - self._last_chart_update >= 0.5:
            self.chart.set_series({
                "Health": [(x.timestamp_seconds, x.visual_health_score) for x in self.samples],
                "Confidence": [(x.timestamp_seconds, x.analysis_confidence) for x in self.samples],
                "Texture": [(x.timestamp_seconds, x.texture_uniformity) for x in self.samples],
            })
            self._last_chart_update = now

    def on_local_analysis(self, result: AnalysisResult, sample, jpeg: bytes) -> None:
        self._latest_local = result
        self._latest_sample = sample
        now = time.monotonic()
        if jpeg:
            self._rolling_frames.append((now, jpeg))
            self._rolling_frames = self._rolling_frames[-self.ROLLING_FRAME_COUNT:]
        self._rolling_metrics.append({
            "elapsed_seconds": round(now - self._stream_started_at, 2) if self._stream_started_at else 0.0,
            "status": str(result.status or ""),
            "visual_health": round(float(sample.visual_health_score), 2),
            "analysis_confidence": round(float(sample.analysis_confidence), 2),
            "texture_uniformity": round(float(sample.texture_uniformity), 2),
            "triggered_findings": len(getattr(result, "findings", []) or []),
        })
        self._rolling_metrics = self._rolling_metrics[-30:]
        indicator_scores = score_indicators(result, sample, self.samples)
        breakdown = split_health_scores(indicator_scores, still_image=False)
        overall_score = breakdown.final_score
        critical_override = any(f.triggered and str(f.severity).lower() == "critical" for f in result.findings)
        quality_decision = classify_quality(overall_score, critical_override=critical_override)
        result.visual_health_score = quality_decision.score
        result.status = quality_decision.status_fa
        sample.visual_health_score = quality_decision.score
        sample.status = quality_decision.status_fa
        self.health.set_value(f"{breakdown.product_health:.1f}%")
        self.process_health.set_value(f"{breakdown.process_health:.1f}%")
        self.conf.set_value(f"{sample.analysis_confidence:.1f}%")
        self.status_card.set_value(quality_decision.status_fa)
        actions = decision_action_fa(quality_decision.level)
        if quality_decision.level in {"high", "critical"}:
            actions = recommendations_fa(indicator_scores)[:2] + actions[:1]
        self.indicator_dashboard.update_scores(indicator_scores, actions)
        status = str(result.status or "").strip().lower()
        if status == self._last_status:
            self._status_streak += 1
        else:
            self._last_status = status
            self._status_streak = 1

        predictive = self._predictive_deterioration()
        local_decision = evaluate_image_alert(result, None)
        should_review = self._should_request_gemini(local_decision, predictive, overall_score, critical_override)
        self._append_timeline(
            "Local",
            "predictive" if predictive else local_decision.level,
            "تحلیل محلی پیوسته انجام شد",
            "در انتظار بررسی ترکیبی" if should_review else "Silent",
        )

        if predictive and not should_review:
            self._finalize_alert(result, None, self._predictive_decision(), "روند پیش‌بینانه محلی")

        if should_review and jpeg:
            self._start_gemini_review(result, jpeg, predictive)
        elif not gemini_api_key() and (local_decision.level in {"high", "critical"} or predictive):
            decision = self._predictive_decision() if predictive and local_decision.level not in {"high", "critical"} else local_decision
            self._finalize_alert(result, None, decision, "رخداد فقط محلی")

    def _should_request_gemini(self, decision: OperatorAlertDecision, predictive: bool, overall_score: float, critical_override: bool = False) -> bool:
        if not gemini_api_key() or self._ai_busy:
            return False
        if not requires_ai_review(overall_score, critical_override=critical_override, predictive=predictive):
            return False
        now = time.monotonic()
        elapsed = now - self._last_gemini_at
        urgent = decision.level in {"high", "critical"} or predictive or overall_score < 70.0
        persistent = self._status_streak >= self.PERSISTENCE_SAMPLES
        return urgent or (persistent and elapsed >= self.GEMINI_COOLDOWN_SECONDS)

    def _predictive_deterioration(self) -> bool:
        if len(self.samples) < 5:
            return False
        recent = self.samples[-5:]
        health_drop = recent[0].visual_health_score - recent[-1].visual_health_score
        texture_drop = recent[0].texture_uniformity - recent[-1].texture_uniformity
        declining = sum(1 for a, b in zip(recent, recent[1:]) if b.visual_health_score < a.visual_health_score) >= 3
        return declining and (health_drop >= 10.0 or texture_drop >= 12.0 or recent[-1].visual_health_score < 65.0)

    def _predictive_decision(self) -> OperatorAlertDecision:
        return OperatorAlertDecision(
            level="high",
            should_speak=True,
            voice_message_fa="هشدار پیش‌بینانه کیفیت. کیفیت محصول در حال نزدیک‌شدن به محدوده نامطلوب است. نمونه‌برداری را افزایش داده و شرایط فرایند را بررسی کنید.",
            immediate_actions_fa=[
                "نمونه‌برداری را مطابق دستورالعمل مصوب افزایش دهید.",
                "تنظیمات فعلی فرایند را با دستور ساخت مصوب مقایسه کنید.",
                "در صورت ادامه روند نزولی، واحد کنترل کیفیت را مطلع کنید.",
            ],
            reason="افت پایدار در سلامت بصری یا یکنواختی بافتِ پایش زنده تشخیص داده شد.",
            predictive=True,
        )

    def _start_gemini_review(self, result: AnalysisResult, jpeg: bytes, predictive: bool) -> None:
        self._ai_busy = True
        self._last_gemini_at = time.monotonic()
        folder = app_data_dir() / "live_camera_frames"
        folder.mkdir(parents=True, exist_ok=True)
        frame_path = folder / f"live_stream_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
        frame_path.write_bytes(build_temporal_contact_sheet([payload for _, payload in self._rolling_frames], jpeg, max_frames=self.ROLLING_FRAME_COUNT))
        self._pending_frame_path = frame_path
        self.connection.setText("جلسه پایش پیوسته فعال است. فریم‌های اخیر و داده‌های روند برای هوش مصنوعی ارسال شد…")
        self.ai_thread = QThread(self)
        self.ai_worker = GeminiWorker(
            "inspect",
            "gemini-3.6-flash",
            str(frame_path),
            process_data={
                "source": "Live Camera",
                "continuous_monitoring": True,
                "temporal_contact_sheet": True,
                "frames_are_chronological_left_to_right": True,
                "predictive_deterioration": predictive,
                "sample_count": len(self.samples),
                "gemini_review_sequence": self._gemini_review_count + 1,
                "rolling_metrics": self._rolling_metrics[-12:],
                "previous_gemini_summary": self._previous_gemini_summary,
                "required_temporal_assessment": {
                    "compare_current_with_prior_frames": True,
                    "classify_trend": "stable | improving | deteriorating | rapidly_deteriorating",
                    "identify_onset_and_progression": True,
                    "predict_near_term_quality_risk": True,
                    "avoid_treating_reflection_or_motion_as_a_confirmed_defect": True,
                },
            },
            local_context=result.to_dict(),
        )
        # Keep the local context on the page. Direct Qt slots below are queued back
        # to the GUI thread, so no widget is ever touched from the هوش مصنوعی worker.
        self._pending_local_result = result
        self._pending_predictive = predictive
        self.ai_worker.moveToThread(self.ai_thread)
        self.ai_thread.started.connect(self.ai_worker.run)
        self.ai_worker.completed.connect(self._on_gemini_completed_signal)
        self.ai_worker.failed.connect(self._on_gemini_failed_signal)
        self.ai_worker.finished.connect(self.ai_thread.quit)
        self.ai_worker.finished.connect(self.ai_worker.deleteLater)
        self.ai_thread.finished.connect(self.ai_thread.deleteLater)
        self.ai_thread.finished.connect(self._finish_ai_cycle)
        self.ai_thread.start()

    @Slot(object)
    def _on_gemini_completed_signal(self, ai: AIInspectionResult) -> None:
        local = self._pending_local_result
        if local is None:
            return
        self._on_gemini_completed(local, ai, self._pending_predictive)

    @Slot(str)
    def _on_gemini_failed_signal(self, message: str) -> None:
        local = self._pending_local_result
        if local is None:
            return
        self._on_gemini_failed(local, message, self._pending_predictive)

    def _on_gemini_completed(self, local: AnalysisResult, ai: AIInspectionResult, predictive: bool) -> None:
        self._gemini_review_count += 1
        self._previous_gemini_summary = ai.operator_summary_fa
        if hasattr(self, "indicator_dashboard"):
            self.indicator_dashboard.update_scores([], [], ai.operator_summary_fa)
        self.gemini_review.set_reports(format_gemini_qc_summary(ai), format_gemini_technical_report(ai))
        decision = evaluate_image_alert(local, ai)
        if predictive and decision.level not in {"critical"}:
            decision = self._predictive_decision()
        self._append_timeline("هوش مصنوعی", decision.level, "بررسی ترکیبی هوش مصنوعی تکمیل شد", "مجاز برای هشدار" if decision.should_speak else "Silent")
        self._finalize_alert(local, ai, decision, "رخداد ترکیبی دوربین زنده")

    def _on_gemini_failed(self, local: AnalysisResult, message: str, predictive: bool) -> None:
        self.gemini_review.set_reports(format_gemini_qc_summary(None, message), format_gemini_technical_report(None, message))
        decision = evaluate_image_alert(local, None)
        if predictive and decision.level not in {"high", "critical"}:
            decision = self._predictive_decision()
        self._append_timeline("هوش مصنوعی", decision.level, f"هوش مصنوعی در دسترس نیست: {message}", "سیاست محلی اعمال شد")
        self._finalize_alert(local, None, decision, "رخداد جایگزین محلی")

    @Slot()
    def _finish_ai_cycle(self) -> None:
        self._ai_busy = False
        self._pending_local_result = None
        self._pending_predictive = False
        self.ai_worker = None
        self.ai_thread = None
        self.connection.setText("متصل است. تحلیل محلی پیوسته فعال است.")

    def _finalize_alert(self, local: AnalysisResult, ai: AIInspectionResult | None, decision: OperatorAlertDecision, event_name: str) -> None:
        record_operator_event("live_camera", local, ai, decision)
        if decision.level == "silent":
            self.operator_alert.setPlainText(
                "وضعیت پایدار است. نتیجه در سابقه ثبت شد و هدست ساکت ماند."
            )
            return

        lines = [
            f"سطح هشدار اپراتور: {decision.level.upper()}",
            f"پیام کوتاه هدست: {decision.voice_message_fa}",
        ]
        if decision.immediate_actions_fa:
            lines.extend(["", "اقدام پیشنهادی اول:", f"1. {decision.immediate_actions_fa[0]}"])
        self.operator_alert.setPlainText("\n".join(lines))

        now = time.monotonic()
        rank = {"silent": 0, "warning": 1, "high": 2, "critical": 3}
        escalated = rank.get(decision.level, 0) > rank.get(self._last_spoken_level, 0)
        cooldown_elapsed = now - self._last_headset_at >= self.HEADSET_COOLDOWN_SECONDS
        if escalated or cooldown_elapsed or decision.predictive:
            speak_text(decision.voice_message_fa)
            self._last_headset_at = now
            self._last_spoken_level = decision.level
            headset = "پخش شد"
        else:
            headset = "به دلیل فاصله زمانی هشدار پخش نشد"
        self._append_timeline("Decision Engine", decision.level, event_name, headset)

    def _append_timeline(self, source: str, level: str, event: str, headset: str) -> None:
        row = self.timeline.rowCount()
        self.timeline.insertRow(row)
        values = [datetime.now().strftime("%H:%M:%S"), source, str(level).upper(), event, headset]
        for column, value in enumerate(values):
            self.timeline.setItem(row, column, QTableWidgetItem(value))
        if self.timeline.rowCount() > 200:
            self.timeline.removeRow(0)
        self.timeline.scrollToBottom()

    def on_failed(self, message):
        QMessageBox.critical(self, "خطای دوربین", message)
        self.connection.setText("خطای دوربین")
