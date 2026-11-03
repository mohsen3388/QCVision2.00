from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QTextEdit, QMessageBox
)

from visionqc.configuration.runtime_repository import RuntimeRepository
from visionqc.capture.sources import probe_source


class EdgeRuntimeHealthPage(QWidget):
    """Camera connectivity and edge telemetry view, inspired by Zabbix host availability."""

    def __init__(self):
        super().__init__()
        self.repo = RuntimeRepository()
        self._build()
        self.refresh()

    def _build(self):
        root = QVBoxLayout(self)
        title = QLabel("سلامت Edge و اتصال دوربین‌ها")
        title.setObjectName("PageTitle")
        root.addWidget(title)
        subtitle = QLabel("پایش اتصال RTSP/USB، نرخ فریم، تازگی تصویر، تلاش‌های اتصال مجدد و خطاهای دریافت فریم")
        subtitle.setObjectName("PageSubtitle")
        root.addWidget(subtitle)

        bar = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh")
        self.probe_btn = QPushButton("Probe Selected Source")
        self.details_btn = QPushButton("Show Diagnostics")
        for button in (self.refresh_btn, self.probe_btn, self.details_btn):
            bar.addWidget(button)
        bar.addStretch()
        root.addLayout(bar)

        headers = [
            "Camera", "Source", "State", "Backend", "Resolution", "FPS",
            "Last Frame", "Reconnects", "Failures", "Received", "Analyzed", "Message"
        ]
        self.table = QTableWidget(0, len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        root.addWidget(self.table, 1)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(170)
        root.addWidget(self.log)

        self.refresh_btn.clicked.connect(self.refresh)
        self.probe_btn.clicked.connect(self.probe_selected)
        self.details_btn.clicked.connect(self.show_diagnostics)

    def refresh(self):
        assignments = {a["camera_id"]: a for a in self.repo.assignments()}
        health = {h["camera_id"]: h for h in self.repo.camera_health_all()}
        camera_ids = sorted(set(assignments) | set(health))
        self.table.setRowCount(len(camera_ids))
        for row, camera_id in enumerate(camera_ids):
            assignment = assignments.get(camera_id, {})
            item = health.get(camera_id, {})
            values = [
                assignment.get("camera_name", camera_id),
                assignment.get("source_type", item.get("source_type", "—")),
                item.get("state", "NO DATA"),
                item.get("backend", "—") or "—",
                f"{item.get('width',0)}×{item.get('height',0)}" if item.get("width") else "—",
                item.get("measured_fps", 0),
                item.get("last_frame_at") or "—",
                item.get("reconnect_count", 0),
                item.get("consecutive_failures", 0),
                item.get("frames_received", 0),
                item.get("frames_analyzed", 0),
                item.get("message", ""),
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setData(Qt.ItemDataRole.UserRole, camera_id)
                self.table.setItem(row, column, cell)
        self.log.setPlainText(
            f"Assignments: {len(assignments)}\nHealth records: {len(health)}\n"
            "RUNNING = stream healthy; RECONNECTING = transient failure; FAILED = retry limit reached."
        )

    def _selected_camera_id(self):
        row = self.table.currentRow()
        if row < 0 or self.table.item(row, 0) is None:
            return None
        return self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def probe_selected(self):
        camera_id = self._selected_camera_id()
        assignment = self.repo.assignment(camera_id) if camera_id else None
        if not assignment:
            QMessageBox.information(self, "Probe", "یک دوربین دارای Assignment را انتخاب کنید.")
            return
        source = assignment["source_value"]
        if assignment["source_type"].upper() == "USB":
            try:
                source = int(source or 0)
            except ValueError:
                source = 0
        result = probe_source(source, timeout_frames=10)
        text = (
            f"Camera: {assignment['camera_name']}\nOpened: {result.opened}\n"
            f"Resolution: {result.width}×{result.height}\nFPS: {result.fps:.2f}\n{result.message}"
        )
        self.log.setPlainText(text)

    def show_diagnostics(self):
        now = datetime.now(timezone.utc)
        lines = ["Edge Runtime Diagnostics", ""]
        for assignment in self.repo.assignments():
            health = self.repo.camera_health(assignment["camera_id"])
            if not health:
                lines.append(f"{assignment['camera_name']}: NO HEALTH DATA")
                continue
            age = "unknown"
            if health.get("last_frame_at"):
                try:
                    timestamp = datetime.fromisoformat(health["last_frame_at"].replace("Z", "+00:00"))
                    age = f"{max(0,(now-timestamp).total_seconds()):.1f}s"
                except Exception:
                    pass
            lines.append(
                f"{assignment['camera_name']}: {health['state']} | backend={health.get('backend') or '—'} | "
                f"fps={health.get('measured_fps',0)} | frame_age={age} | reconnects={health.get('reconnect_count',0)}"
            )
        self.log.setPlainText("\n".join(lines))
