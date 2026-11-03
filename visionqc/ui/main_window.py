from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QMainWindow, QMessageBox, QStackedWidget

from visionqc.bootstrap import ApplicationContext
from visionqc.core.settings import APP_NAME, APP_VERSION, load_settings
from visionqc.ui.theme import stylesheet_for
from visionqc.ui.batch_workspace_page import BatchWorkspacePage
from visionqc.ui.assistant_page import OperatorAssistantPage
from visionqc.ui.camera_page import CameraPage
from visionqc.ui.features_page import FeaturesPage
from visionqc.ui.history_page import HistoryPage
from visionqc.ui.knowledge_page import KnowledgePage
from visionqc.ui.factory_memory_page import FactoryMemoryPage
from visionqc.ui.management_dashboard_page import ManagementDashboardPage
from visionqc.ui.event_timeline_page import EventTimelinePage
from visionqc.ui.golden_batch_page import GoldenBatchPage
from visionqc.ui.home_page import HomePage
from visionqc.ui.image_analysis_page import ImageAnalysisPage
from visionqc.ui.reports_page import ReportsPage
from visionqc.ui.spc_page import SPCPage
from visionqc.ui.operations_page import OEEPage
from visionqc.ui.automation_page import AutomationCenterPage
from visionqc.ui.sync_page import SyncPage
from visionqc.ui.inspection_designer_page import InspectionDesignerPage
from visionqc.ui.quality_configuration_studio_page import QualityConfigurationStudioPage
from visionqc.ui.runtime_operations_page import RuntimeOperationsPage
from visionqc.ui.settings_page import SettingsPage
from visionqc.ui.video_analysis_page import VideoAnalysisPage
from visionqc.ui.voice_ai_page import VoiceAIPage
from visionqc.ui.root_cause_page import RootCausePage
from visionqc.ui.knowledge_graph_page import KnowledgeGraphPage
from visionqc.ui.predictive_quality_page import PredictiveQualityPage
from visionqc.ui.factory_engineer_page import AIFactoryEngineerPage
from visionqc.ui.release_candidate_page import ReleaseCandidatePage
from visionqc.ui.enterprise_integration_page import EnterpriseIntegrationPage
from visionqc.ui.industrial_automation_page import IndustrialAutomationPage
from visionqc.ui.commercial_edition_page import CommercialEditionPage
from visionqc.ui.audio_settings_dialog import AudioSettingsDialog
from visionqc.ui.factory_camera_center_page import FactoryCameraCenterPage
from visionqc.ui.factory_operations_dashboard_page import FactoryOperationsDashboardPage
from visionqc.ui.calibration_validation_page import CalibrationValidationPage
from visionqc.ui.factory_learning_page import FactoryLearningPage
from visionqc.ui.edge_runtime_health_page import EdgeRuntimeHealthPage
from visionqc.ui.security_governance_page import SecurityGovernancePage
from visionqc.ui.executive_reporting_page import ExecutiveReportingPage
from visionqc.ui.wake_word_dialog import WakeWordStatusDialog
from visionqc.voice.wake_word import WakeWordListener, WakeWordMatcher
from visionqc.voice.speech_recognition import recognize_once
from visionqc.ai.speech import speak_text


class _WakeQuestionWorker(QThread):
    completed = Signal(str, float)
    failed = Signal(str)

    def run(self) -> None:
        try:
            # Wait until the short acknowledgement has finished before opening the microphone.
            speak_text("بفرمایید. سؤال خود را بگویید.", wait=True)
            result = recognize_once(culture="fa-IR", timeout_seconds=10)
            if not result.text:
                # Fallback for Windows installations that only have the English recognizer.
                fallback = recognize_once(culture="en-US", timeout_seconds=8)
                if fallback.text:
                    result = fallback
            if result.text:
                self.completed.emit(result.text, result.confidence)
            else:
                self.failed.emit(result.error or "صدایی از اپراتور دریافت نشد.")
        except Exception as exc:
            self.failed.emit(str(exc))


class _WakeReplyWorker(QThread):
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, service, conversation_id: int, question: str, confidence: float) -> None:
        super().__init__()
        self.service = service
        self.conversation_id = conversation_id
        self.question = question
        self.confidence = confidence

    def run(self) -> None:
        try:
            response = self.service.ask(
                self.conversation_id, self.question, source="wake_word",
                speech_confidence=self.confidence,
            )
            speak_text(response.text, wait=True)
            self.completed.emit(response.text)
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    """Main window with the former space-heavy left navigation removed.

    Navigation now lives in compact menu-bar menus, leaving the full window
    width available to image/video/AI workspaces.
    """

    def __init__(self, context: ApplicationContext | None = None) -> None:
        super().__init__()
        self.context = context
        settings = context.settings if context is not None else load_settings()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION} — {settings['factory_name']}")
        self.resize(1550, 940)
        self.setMinimumSize(1180, 760)
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.page_by_name: dict[str, int] = {}
        self._wake_listener: WakeWordListener | None = None
        self._wake_reply_worker: _WakeReplyWorker | None = None
        self._wake_question_worker: _WakeQuestionWorker | None = None
        self._wake_matcher = WakeWordMatcher("Vision", conversation_timeout=30.0)
        self._wake_status = "Starting"
        self._wake_debug = "No microphone event received yet."

        self.home = HomePage(); self.image = ImageAnalysisPage(); self.video = VideoAnalysisPage()
        self.live = CameraPage(False); self.ip = CameraPage(True); self.camera_center = FactoryCameraCenterPage(); self.batch = BatchWorkspacePage()
        self.golden = GoldenBatchPage(); self.assistant = OperatorAssistantPage(); self.knowledge = KnowledgePage()
        self.voice_ai = VoiceAIPage(context.container.resolve("voice_assistant_service"), context.container.resolve("factory_memory_service"), settings) if context is not None else None
        self.factory_memory = FactoryMemoryPage(context.container.resolve("factory_memory_service")) if context is not None else None
        self.root_cause = RootCausePage(context.container.resolve("root_cause_service"), context.container.resolve("factory_memory_service")) if context is not None else None
        self.factory_learning = FactoryLearningPage(context.container.resolve("factory_learning_service"), context.container.resolve("factory_memory_service")) if context is not None else None
        self.knowledge_graph = KnowledgeGraphPage(context.container.resolve("knowledge_graph_service")) if context is not None else None
        self.predictive_quality = PredictiveQualityPage(context.container.resolve("predictive_quality_service")) if context is not None else None
        self.factory_engineer = AIFactoryEngineerPage(context.container.resolve("factory_engineer_service"), context.container.resolve("factory_memory_service")) if context is not None else None
        self.release_candidate = ReleaseCandidatePage(context.container.resolve("release_readiness_service")) if context is not None else None
        self.enterprise_integration = EnterpriseIntegrationPage(context.container.resolve("enterprise_integration_service"), context.container.resolve("rest_server")) if context is not None else None
        self.industrial_automation = IndustrialAutomationPage(context.container.resolve("industrial_automation_service")) if context is not None else None
        self.commercial_edition = CommercialEditionPage(context.container.resolve("commercial_edition_service")) if context is not None else None
        self.events = EventTimelinePage(); self.history = HistoryPage(); self.reports = ReportsPage()
        self.management = ManagementDashboardPage(); self.executive_reporting = ExecutiveReportingPage(); self.spc = SPCPage(); self.operations = OEEPage()
        self.automation = AutomationCenterPage(); self.sync = SyncPage(); self.inspection = InspectionDesignerPage()
        self.quality_studio = QualityConfigurationStudioPage()
        self.runtime_operations = RuntimeOperationsPage()
        self.factory_operations = FactoryOperationsDashboardPage()
        self.calibration_validation = CalibrationValidationPage()
        self.edge_runtime_health = EdgeRuntimeHealthPage()
        self.security_governance = SecurityGovernancePage(context.container.resolve("security_service"), context.container.resolve("audit_repository")) if context is not None else None
        self.settings = SettingsPage(); self.features = FeaturesPage()

        pages = [
            ("Home Dashboard", self.home), ("Deep Image Analysis", self.image),
            ("Video Analysis", self.video), ("Live Camera", self.live),
            ("Phone / IP Camera", self.ip), ("Factory Camera Center", self.camera_center),
            ("Batch Workspace", self.batch),
            ("Golden Batch", self.golden), ("Operator Assistant", self.assistant),
            *(([("Voice AI Copilot", self.voice_ai)] if self.voice_ai is not None else [])),
            *(([("Factory Memory", self.factory_memory)] if self.factory_memory is not None else [])),
            *(([("Root Cause Intelligence", self.root_cause)] if self.root_cause is not None else [])),
            *(([("Factory Learning", self.factory_learning)] if self.factory_learning is not None else [])),
            *(([("Factory Knowledge Graph", self.knowledge_graph)] if self.knowledge_graph is not None else [])),
            *(([("Predictive Quality", self.predictive_quality)] if self.predictive_quality is not None else [])),
            *(([("AI Factory Engineer", self.factory_engineer)] if self.factory_engineer is not None else [])),
            *(([("Release Candidate", self.release_candidate)] if self.release_candidate is not None else [])),
            *(([("Enterprise Integration", self.enterprise_integration)] if self.enterprise_integration is not None else [])),
            *(([("Industrial Automation", self.industrial_automation)] if self.industrial_automation is not None else [])),
            *(([("Commercial Edition", self.commercial_edition)] if self.commercial_edition is not None else [])),
            ("Factory Knowledge", self.knowledge), ("Event Timeline", self.events),
            ("History & Replay", self.history), ("PDF Reports", self.reports),
            ("Management Dashboard", self.management), ("Executive Reporting & KPI", self.executive_reporting), ("Statistical Process Control", self.spc),
            ("Production Operations & OEE", self.operations), ("Automation Center", self.automation),
            ("Secure Synchronization", self.sync), ("Visual Inspection Designer", self.inspection),
            ("Quality Configuration Studio", self.quality_studio),
            ("Runtime Operations Center", self.runtime_operations),
            ("Factory Operations Dashboard", self.factory_operations),
            ("Calibration & Validation", self.calibration_validation),
            ("Edge Runtime Health", self.edge_runtime_health),
            ("Security & Governance", self.security_governance),
            ("Settings & Diagnostics", self.settings), ("All Features", self.features),
        ]
        for name, page in pages:
            self._add_page(name, page)

        self._build_navigation_menus()
        self.settings.theme_changed.connect(self._apply_theme)
        self.assistant.navigate.connect(self.show_name)
        self.features.navigate.connect(self.show_name)
        self.home.open_features.connect(lambda: self.show_name("All Features"))
        self.home.open_analysis.connect(lambda: self.show_name("Deep Image Analysis"))
        self.camera_center.open_camera.connect(self._open_registered_camera)
        self.show_name("Home Dashboard")
        if self.voice_ai is not None:
            self._set_wake_word_enabled(True)

    def _build_navigation_menus(self) -> None:
        navigate = self.menuBar().addMenu("Navigate")
        groups = [
            ("Core", ["Home Dashboard", "Deep Image Analysis", "Video Analysis", "Live Camera", "Phone / IP Camera", "Factory Camera Center", "Operator Assistant", "Voice AI Copilot"] if self.voice_ai is not None else ["Home Dashboard", "Deep Image Analysis", "Video Analysis", "Live Camera", "Phone / IP Camera", "Factory Camera Center", "Operator Assistant"]),
            ("Quality", ["Batch Workspace", "Golden Batch", "Factory Memory", "Root Cause Intelligence", "Factory Learning", "Factory Knowledge Graph", "Predictive Quality", "AI Factory Engineer", "Release Candidate", "Factory Knowledge", "Event Timeline", "History & Replay", "PDF Reports"] if self.factory_memory is not None else ["Batch Workspace", "Golden Batch", "Factory Knowledge", "Event Timeline", "History & Replay", "PDF Reports"]),
            ("Management", ["Management Dashboard", "Executive Reporting & KPI", "Statistical Process Control", "Production Operations & OEE", "Automation Center", "Industrial Automation"] if self.industrial_automation is not None else ["Management Dashboard", "Executive Reporting & KPI", "Statistical Process Control", "Production Operations & OEE", "Automation Center"]),
            ("Configuration", ["Enterprise Integration", "Commercial Edition", "Secure Synchronization", "Visual Inspection Designer", "Quality Configuration Studio", "Runtime Operations Center", "Factory Operations Dashboard", "Calibration & Validation", "Edge Runtime Health", "Security & Governance", "Settings & Diagnostics", "All Features"] if self.enterprise_integration is not None else ["Secure Synchronization", "Visual Inspection Designer", "Quality Configuration Studio", "Runtime Operations Center", "Factory Operations Dashboard", "Calibration & Validation", "Edge Runtime Health", "Security & Governance", "Settings & Diagnostics", "All Features"]),
        ]
        shortcuts = {"Home Dashboard": "Ctrl+1", "Deep Image Analysis": "Ctrl+2", "Video Analysis": "Ctrl+3", "Operator Assistant": "Ctrl+4", "Voice AI Copilot": "Ctrl+5", "Settings & Diagnostics": "Ctrl+,", "All Features": "Ctrl+M"}
        for group_name, names in groups:
            submenu = navigate.addMenu(group_name)
            for name in names:
                action = QAction(name, self)
                if name in shortcuts:
                    action.setShortcut(shortcuts[name])
                action.triggered.connect(lambda checked=False, n=name: self.show_name(n))
                submenu.addAction(action)
        tools_menu = self.menuBar().addMenu("Tools")
        audio_settings = QAction("Audio Settings & Headset Test", self)
        audio_settings.triggered.connect(self._open_audio_settings)
        tools_menu.addAction(audio_settings)
        self.wake_word_action = QAction("Enable Wake Word Conversation", self)
        self.wake_word_action.setCheckable(True)
        self.wake_word_action.setChecked(True)
        self.wake_word_action.toggled.connect(self._set_wake_word_enabled)
        tools_menu.addAction(self.wake_word_action)
        wake_status = QAction("Wake Word Status", self)
        wake_status.triggered.connect(self._open_wake_word_status)
        tools_menu.addAction(wake_status)

        help_menu = self.menuBar().addMenu("Help")
        about = QAction("About VisionQC", self); about.triggered.connect(self._about); help_menu.addAction(about)

    def _add_page(self, name: str, page) -> None:
        self.page_by_name[name] = self.stack.addWidget(page)

    def show_name(self, name: str) -> None:
        aliases = {"Overview": "Home Dashboard", "Quality": "All Features"}
        name = aliases.get(name, name)
        if name not in self.page_by_name:
            name = "All Features"
        self.stack.setCurrentIndex(self.page_by_name[name])
        self.statusBar().showMessage(name)
        if name == "Factory Camera Center": self.camera_center.refresh()
        if name == "Security & Governance" and self.security_governance is not None: self.security_governance.refresh()
        if name == "Factory Memory" and self.factory_memory is not None: self.factory_memory.refresh()
        if name == "Voice AI Copilot" and self.voice_ai is not None: self.voice_ai.refresh_cases()
        if name == "Root Cause Intelligence" and self.root_cause is not None: self.root_cause.refresh_cases()
        if name == "Factory Learning" and self.factory_learning is not None: self.factory_learning.refresh()
        if name == "Predictive Quality" and self.predictive_quality is not None: self.predictive_quality.refresh_scopes()
        if name == "AI Factory Engineer" and self.factory_engineer is not None: self.factory_engineer.refresh_cases()
        if name == "Release Candidate" and self.release_candidate is not None: self.release_candidate.refresh()
        if name == "Enterprise Integration" and self.enterprise_integration is not None: self.enterprise_integration.refresh()
        if name == "Industrial Automation" and self.industrial_automation is not None: self.industrial_automation.refresh()
        if name == "Commercial Edition" and self.commercial_edition is not None: self.commercial_edition.refresh()
        if name == "History & Replay": self.history.refresh()
        if name == "PDF Reports": self.reports.refresh()
        if name == "Management Dashboard": self.management.refresh()
        if name == "Executive Reporting & KPI": self.executive_reporting.refresh()
        if name == "Statistical Process Control": self.spc.reload_sources(); self.spc.refresh()
        if name == "Production Operations & OEE": self.operations.reload(); self.operations.refresh()
        if name == "Automation Center": self.automation.reload()
        if name == "Secure Synchronization": self.sync.refresh()
        if name == "Visual Inspection Designer": self.inspection.reload()
        if name == "Quality Configuration Studio": self.quality_studio.refresh_templates()
        if name == "Runtime Operations Center": self.runtime_operations.refresh()
        if name == "Factory Operations Dashboard": self.factory_operations.refresh()
        if name == "Calibration & Validation": self.calibration_validation.refresh_templates()
        if name == "Edge Runtime Health": self.edge_runtime_health.refresh()

    def _open_registered_camera(self, camera) -> None:
        page = self.ip if camera.source_type == "RTSP" else self.live
        page.configure_registered_camera(camera)
        self.show_name("Phone / IP Camera" if camera.source_type == "RTSP" else "Live Camera")

    def _apply_theme(self, name: str) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.instance().setStyleSheet(stylesheet_for(name))

    def _open_audio_settings(self) -> None:
        AudioSettingsDialog(self).exec()

    def _set_wake_word_enabled(self, enabled: bool) -> None:
        if self.voice_ai is None:
            return
        if enabled:
            if self._wake_listener is not None and self._wake_listener.isRunning():
                return
            self._wake_listener = WakeWordListener(culture="auto", timeout_seconds=5)
            self._wake_listener.heard.connect(self._handle_wake_word_text)
            self._wake_listener.state_changed.connect(self._update_wake_status)
            self._wake_listener.debug_event.connect(self._update_wake_debug)
            self._wake_listener.start()
            self._wake_status = "Listening for wake word: Vision"
        else:
            if self._wake_listener is not None:
                self._wake_listener.stop()
                self._wake_listener.wait(6500)
                self._wake_listener = None
            self._wake_matcher.reset()
            self._wake_status = "Disabled"
        if hasattr(self, "wake_word_action") and self.wake_word_action.isChecked() != enabled:
            self.wake_word_action.blockSignals(True)
            self.wake_word_action.setChecked(enabled)
            self.wake_word_action.blockSignals(False)

    def _update_wake_status(self, status: str) -> None:
        self._wake_status = status
        self.statusBar().showMessage(status, 4000)

    def _update_wake_debug(self, message: str) -> None:
        self._wake_debug = message
        self.statusBar().showMessage(message, 4000)

    def _handle_wake_word_text(self, text: str, confidence: float) -> None:
        result = self._wake_matcher.feed(text)
        if not result.activated:
            return
        if self._wake_listener is not None:
            self._wake_listener.pause_listening()
        if not result.question:
            self._wake_status = "Wake word detected; capturing operator question"
            self._wake_question_worker = _WakeQuestionWorker()
            self._wake_question_worker.completed.connect(self._wake_question_captured)
            self._wake_question_worker.failed.connect(self._wake_question_failed)
            self._wake_question_worker.start()
            return
        self._wake_status = f"Question received: {result.question}"
        self._wake_reply_worker = _WakeReplyWorker(
            self.voice_ai.service, self.voice_ai.conversation_id, result.question, confidence
        )
        self._wake_reply_worker.completed.connect(self._wake_reply_completed)
        self._wake_reply_worker.failed.connect(self._wake_reply_failed)
        self._wake_reply_worker.start()

    def _wake_question_captured(self, question: str, confidence: float) -> None:
        self._wake_debug = f"Heard operator question: {question}"
        self._wake_status = f"Question received: {question}"
        self._wake_question_worker = None
        self._wake_reply_worker = _WakeReplyWorker(
            self.voice_ai.service, self.voice_ai.conversation_id, question, confidence
        )
        self._wake_reply_worker.completed.connect(self._wake_reply_completed)
        self._wake_reply_worker.failed.connect(self._wake_reply_failed)
        self._wake_reply_worker.start()

    def _wake_question_failed(self, error: str) -> None:
        self._wake_question_worker = None
        self._wake_debug = f"Question capture failed: {error}"
        speak_text("صدای شما دریافت نشد. دوباره ویژن را بگویید.", wait=False)
        self._wake_status = "Question was not captured; listening for Vision"
        self._resume_wake_listener()

    def _wake_reply_completed(self, answer: str) -> None:
        if self.voice_ai is not None:
            self.voice_ai._append("operator", "[Wake word question]")
            self.voice_ai._append("assistant", answer)
        self._wake_status = "Conversation completed; listening for Vision"
        self._resume_wake_listener()

    def _wake_reply_failed(self, error: str) -> None:
        speak_text("پردازش درخواست انجام نشد. لطفاً دوباره تلاش کنید.", wait=False)
        self._wake_status = f"Wake word request failed: {error}"
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2500, self._resume_wake_listener)

    def _resume_wake_listener(self) -> None:
        if self._wake_listener is not None:
            self._wake_listener.resume_listening()

    def _open_wake_word_status(self) -> None:
        enabled = self._wake_listener is not None and self._wake_listener.isRunning()
        WakeWordStatusDialog(enabled=enabled, status=self._wake_status, debug_text=self._wake_debug, parent=self).exec()

    def _about(self) -> None:
        QMessageBox.information(self, "About VisionQC", f"VisionQC {APP_VERSION}\nIndustrial visual quality intelligence\nGemini-enabled decision support\n\nIt does not replace laboratory or qualified QC assessment.")

    def closeEvent(self, event) -> None:
        if self._wake_listener is not None:
            self._wake_listener.stop()
            self._wake_listener.wait(6500)
            self._wake_listener = None
        if self.context is not None:
            try: self.context.container.resolve("rest_server").stop()
            except Exception: pass
        for page in (self.live, self.ip):
            if page.worker:
                page.worker.stop()
        super().closeEvent(event)
