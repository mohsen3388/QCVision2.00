from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGridLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QLineEdit,
)

from visionqc.multicamera.factory_service import FactoryMonitoringService
from visionqc.ui.widgets import MetricCard


class FactoryOperationsDashboardPage(QWidget):
    """Factory-wide view inspired by Zabbix overview/problem screens."""

    def __init__(self, service: FactoryMonitoringService | None = None) -> None:
        super().__init__()
        self.service = service or FactoryMonitoringService()
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        title = QLabel("داشبورد عملیات کارخانه")
        title.setObjectName("PageTitle")
        subtitle = QLabel("نمای یکپارچه دوربین‌ها، سلامت ایستگاه‌ها و رخدادهای فعال؛ با منطق Overview و Problems مشابه Zabbix.")
        subtitle.setObjectName("PageSubtitle")
        root.addWidget(title)
        root.addWidget(subtitle)

        cards = QGridLayout()
        self.health_card = MetricCard("سلامت میانگین کارخانه")
        self.active_card = MetricCard("دوربین‌های فعال")
        self.problem_card = MetricCard("دوربین‌های رخداددار")
        self.event_card = MetricCard("رخدادهای فعال")
        self.critical_card = MetricCard("هشدار بالا/بحرانی")
        for index, card in enumerate((self.health_card, self.active_card, self.problem_card, self.event_card, self.critical_card)):
            cards.addWidget(card, 0, index)
        root.addLayout(cards)

        tools = QHBoxLayout()
        self.profile_filter = QComboBox()
        self.profile_filter.addItems(["همه پروفایل‌ها", "mixing", "incoming", "filling", "packaging", "hse", "general"])
        self.search = QLineEdit()
        self.search.setPlaceholderText("جست‌وجوی دوربین، ناحیه یا دستگاه…")
        self.refresh_btn = QPushButton("بازخوانی")
        self.refresh_btn.setObjectName("Secondary")
        tools.addWidget(QLabel("پروفایل:")); tools.addWidget(self.profile_filter)
        tools.addWidget(self.search, 1); tools.addWidget(self.refresh_btn)
        root.addLayout(tools)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels([
            "دوربین", "ناحیه", "دستگاه", "پروفایل", "وضعیت", "سلامت",
            "رخداد فعال", "شدت بیشینه", "آخرین رخداد", "شناسه",
        ])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnHidden(9, True)
        root.addWidget(self.table, 1)

        self.refresh_btn.clicked.connect(self.refresh)
        self.profile_filter.currentTextChanged.connect(self._render)
        self.search.textChanged.connect(self._render)

    def refresh(self) -> None:
        self.overview = self.service.overview()
        self.health_card.set_value("—" if self.overview.average_health is None else f"{self.overview.average_health:.1f}")
        self.active_card.set_value(f"{self.overview.enabled_cameras}/{self.overview.total_cameras}")
        self.problem_card.set_value(str(self.overview.cameras_with_events))
        self.event_card.set_value(str(self.overview.active_events))
        self.critical_card.set_value(str(self.overview.critical_cameras))
        self._render()

    def _render(self) -> None:
        profile = self.profile_filter.currentText()
        query = self.search.text().strip().lower()
        rows = list(self.overview.snapshots)
        if profile != "همه پروفایل‌ها":
            rows = [row for row in rows if row.profile_key == profile]
        if query:
            rows = [row for row in rows if query in " ".join((row.camera_name, row.area, row.asset, row.last_event)).lower()]
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values = [
                row.camera_name, row.area, row.asset, row.profile_key, row.status,
                "—" if row.health is None else f"{row.health:.1f}", row.active_events,
                row.highest_severity or "—", row.last_event, row.camera_id,
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if c in {5, 6}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(r, c, item)
