from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget)


class AIFactoryEngineerPage(QWidget):
    def __init__(self, service, memory) -> None:
        super().__init__()
        self.service = service
        self.memory = memory
        self._case_ids: list[int | None] = []
        self._build()
        self.refresh_cases()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("AI Factory Engineer")
        title.setObjectName("pageTitle")
        subtitle = QLabel("One evidence-backed operational briefing across Factory Memory, Root Cause Intelligence, Knowledge Graph and Predictive Quality. Human approval remains mandatory.")
        subtitle.setWordWrap(True)
        layout.addWidget(title); layout.addWidget(subtitle)

        row = QHBoxLayout()
        row.addWidget(QLabel("Factory Memory case:"))
        self.case_combo = QComboBox()
        row.addWidget(self.case_combo, 1)
        refresh = QPushButton("Refresh Cases"); refresh.clicked.connect(self.refresh_cases)
        run = QPushButton("Generate Operational Briefing"); run.clicked.connect(self.generate)
        row.addWidget(refresh); row.addWidget(run)
        layout.addLayout(row)

        self.banner = QLabel("Select a case or generate a factory-wide briefing.")
        self.banner.setWordWrap(True); self.banner.setObjectName("statusCard")
        layout.addWidget(self.banner)

        summary_box = QGroupBox("Engineer briefing")
        summary_layout = QVBoxLayout(summary_box)
        self.summary = QTextEdit(); self.summary.setReadOnly(True)
        summary_layout.addWidget(self.summary)
        layout.addWidget(summary_box, 1)

        self.actions = QTableWidget(0, 6)
        self.actions.setHorizontalHeaderLabels(["#","Action","Owner","Rationale","Verification","Source"])
        self.actions.setEditTriggers(QTableWidget.NoEditTriggers)
        self.actions.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.actions.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.actions.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.actions.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.actions.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.actions.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        layout.addWidget(self.actions, 2)

        gates_box = QGroupBox("Evidence, decision gates and limitations")
        gates_layout = QVBoxLayout(gates_box)
        self.details = QTextEdit(); self.details.setReadOnly(True)
        gates_layout.addWidget(self.details)
        layout.addWidget(gates_box, 1)

    def refresh_cases(self) -> None:
        current = self.case_combo.currentData()
        self.case_combo.clear()
        self.case_combo.addItem("Factory-wide briefing", None)
        for case_id, case in self._cases_with_ids():
            state = "PASS" if case.passed else "REJECT"
            defects = ", ".join(d.defect_type for d in case.defects) or "no defect"
            self.case_combo.addItem(f"#{case_id} | {state} | {case.product_name} | {defects}", case_id)
        idx = self.case_combo.findData(current)
        if idx >= 0: self.case_combo.setCurrentIndex(idx)

    def _cases_with_ids(self):
        repository = getattr(self.memory, "_repository", None)
        if repository is None:
            return []
        # Repository exposes payloads but not ids through the service. Obtain ids
        # conservatively from SQLite implementation when available.
        try:
            import sqlite3
            from visionqc.core.database import database_path
            conn = sqlite3.connect(database_path())
            ids = [row[0] for row in conn.execute("SELECT id FROM factory_memory_cases ORDER BY id DESC LIMIT 100")]
            conn.close()
            result = []
            for case_id in ids:
                case = self.memory.get(case_id)
                if case is not None: result.append((case_id, case))
            return result
        except Exception:
            return []

    def generate(self) -> None:
        briefing = self.service.generate_briefing(case_id=self.case_combo.currentData())
        self.banner.setText(f"{briefing.priority.value} — {briefing.scope}")
        self.summary.setPlainText("\n\n".join([
            briefing.executive_summary,
            "QUALITY STATUS\n" + briefing.quality_status,
            "FORECAST\n" + briefing.forecast_summary,
            "ROOT CAUSE\n" + briefing.root_cause_summary,
        ]))
        self.actions.setRowCount(len(briefing.actions))
        for r, action in enumerate(briefing.actions):
            values = [str(action.priority), action.title, action.owner_role, action.rationale, action.verification, action.source]
            for c, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignCenter if c == 0 else Qt.AlignLeft | Qt.AlignVCenter)
                self.actions.setItem(r, c, item)
        lines = ["EVIDENCE"] + [f"• {x}" for x in briefing.evidence]
        lines += ["", "DECISION GATES"] + [f"• {x}" for x in briefing.decision_gates]
        lines += ["", "LIMITATIONS"] + [f"• {x}" for x in briefing.limitations]
        self.details.setPlainText("\n".join(lines))
