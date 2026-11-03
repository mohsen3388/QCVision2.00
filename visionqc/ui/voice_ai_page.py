from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTextBrowser, QVBoxLayout, QWidget,
)

from visionqc.ai.speech import speak_text
from visionqc.application.services.voice_assistant_service import VoiceAssistantService
from visionqc.voice.speech_recognition import recognize_once


class _ListenWorker(QThread):
    finished_result = Signal(object)
    def __init__(self, culture: str) -> None:
        super().__init__(); self.culture = culture
    def run(self) -> None:
        self.finished_result.emit(recognize_once(culture=self.culture))


class VoiceAIPage(QWidget):
    def __init__(self, service: VoiceAssistantService, memory_service, settings: dict) -> None:
        super().__init__(); self.service=service; self.memory=memory_service; self.settings=settings
        self.conversation_id, _ = service.new_conversation(factory_name=settings.get("factory_name", ""))
        self.worker: _ListenWorker | None = None
        root=QVBoxLayout(self)
        title=QLabel("VisionQC Voice AI — Factory Quality Copilot"); title.setObjectName("PageTitle")
        root.addWidget(title)
        root.addWidget(QLabel("Offline-first, evidence-grounded operator conversation. Typed mode always remains available."))

        ctx=QGroupBox("Conversation context"); form=QFormLayout(ctx)
        self.case_combo=QComboBox(); self.case_combo.currentIndexChanged.connect(self._case_changed)
        self.language=QComboBox(); self.language.addItem("English (Windows offline)","en-US"); self.language.addItem("Persian (installed Windows recognizer required)","fa-IR")
        self.auto_speak=QComboBox(); self.auto_speak.addItems(["Speak responses","Silent responses"])
        form.addRow("Factory Memory case",self.case_combo); form.addRow("Microphone language",self.language); form.addRow("Output",self.auto_speak)
        root.addWidget(ctx)

        self.chat=QTextBrowser(); self.chat.setOpenExternalLinks(False); root.addWidget(self.chat,1)
        row=QHBoxLayout(); self.input=QLineEdit(); self.input.setPlaceholderText("Ask about this case, similar history, rejects, defects, or recommended checks…"); self.input.returnPressed.connect(self.send)
        self.listen=QPushButton("🎙 Push to talk"); self.listen.clicked.connect(self.start_listening)
        send=QPushButton("Send"); send.clicked.connect(self.send)
        row.addWidget(self.input,1); row.addWidget(self.listen); row.addWidget(send); root.addLayout(row)
        prompts=QHBoxLayout()
        for text in ("Summarize this case","Find similar cases","Show recent reject activity","What should I check first?"):
            b=QPushButton(text); b.clicked.connect(lambda checked=False,t=text:self._ask(t,"shortcut")); prompts.addWidget(b)
        root.addLayout(prompts)
        self.refresh_cases(); self._append("assistant","Voice AI is ready. Select a Factory Memory case for case-specific answers.")

    def refresh_cases(self) -> None:
        current=self.case_combo.currentData(); self.case_combo.blockSignals(True); self.case_combo.clear(); self.case_combo.addItem("No case selected",None)
        for case in self.memory.list_recent(200):
            case_id=self._find_case_id(case)
            if case_id is not None:
                state="PASS" if case.passed else "REJECT"; self.case_combo.addItem(f"#{case_id} · {case.product_name} · {state} · {case.production.batch_code or 'no batch'}",case_id)
        idx=self.case_combo.findData(current); self.case_combo.setCurrentIndex(max(0,idx)); self.case_combo.blockSignals(False)
    def _find_case_id(self, case):
        repo=getattr(self.memory,"_repository",None)
        if repo is None: return None
        try:
            from visionqc.core.database import connect
            with connect() as conn:
                row=conn.execute("SELECT id FROM factory_memory_cases WHERE case_uuid=?",(case.case_uuid,)).fetchone(); return int(row[0]) if row else None
        except Exception: return None
    def _case_changed(self) -> None:
        try:self.service.select_case(self.conversation_id,self.case_combo.currentData())
        except Exception as exc: QMessageBox.warning(self,"Case selection",str(exc))
    def send(self) -> None:
        text=self.input.text().strip()
        if text:self.input.clear(); self._ask(text,"typed")
    def _ask(self,text:str,source:str,confidence:float=1.0) -> None:
        self._append("operator",text)
        try:
            response=self.service.ask(self.conversation_id,text,source=source,speech_confidence=confidence)
            body=response.text
            if response.evidence: body += "\n\nEvidence:\n• " + "\n• ".join(response.evidence)
            body += "\n\n" + response.safety_note
            self._append("assistant",body)
            if self.auto_speak.currentIndex()==0:speak_text(response.text)
        except Exception as exc: QMessageBox.critical(self,"Voice AI",str(exc))
    def start_listening(self) -> None:
        if self.worker and self.worker.isRunning(): return
        self.listen.setEnabled(False); self.listen.setText("Listening…")
        self.worker=_ListenWorker(self.language.currentData()); self.worker.finished_result.connect(self._heard); self.worker.start()
    def _heard(self,result) -> None:
        self.listen.setEnabled(True); self.listen.setText("🎙 Push to talk")
        if result.text:self._ask(result.text,"microphone",result.confidence)
        else: QMessageBox.information(self,"Microphone",result.error or "No speech was detected. Typed mode is still available.")
    def _append(self,role:str,text:str) -> None:
        label="Operator" if role=="operator" else "VisionQC"
        safe=text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace("\n","<br>")
        self.chat.append(f"<p><b>{label}</b><br>{safe}</p>")
