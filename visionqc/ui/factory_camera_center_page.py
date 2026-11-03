from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from visionqc.multicamera.models import CameraDefinition, CameraRegistry, profile_catalog, profile_by_key
from visionqc.ui.widgets import MetricCard


class CameraEditorDialog(QDialog):
    def __init__(self, camera: CameraDefinition | None = None, parent=None) -> None:
        super().__init__(parent)
        self.camera = camera
        self.setWindowTitle("تعریف دوربین و مسئولیت‌ها")
        self.setMinimumWidth(620)
        form = QFormLayout(self)
        self.name = QLineEdit(camera.name_fa if camera else "")
        self.area = QLineEdit(camera.area_fa if camera else "")
        self.asset = QLineEdit(camera.asset_fa if camera else "")
        self.profile = QComboBox()
        for item in profile_catalog():
            self.profile.addItem(item.title_fa, item.key)
        if camera:
            self.profile.setCurrentIndex(max(0, self.profile.findData(camera.profile_key)))
        self.source_type = QComboBox(); self.source_type.addItems(["RTSP", "USB", "فایل آزمایشی"])
        if camera:
            self.source_type.setCurrentText(camera.source_type)
        self.source = QLineEdit(camera.source_value if camera else "")
        self.source.setPlaceholderText("RTSP URL، شماره دوربین USB یا مسیر فایل")
        self.operator = QLineEdit(camera.operator_fa if camera else "")
        self.qc_manager = QLineEdit(camera.qc_manager_fa if camera else "")
        self.hse_owner = QLineEdit(camera.hse_owner_fa if camera else "")
        self.enabled = QCheckBox("فعال باشد"); self.enabled.setChecked(camera.enabled if camera else True)
        self.profile_help = QTextEdit(); self.profile_help.setReadOnly(True); self.profile_help.setMaximumHeight(105)
        form.addRow("نام دوربین", self.name); form.addRow("ناحیه کارخانه", self.area)
        form.addRow("دستگاه / ایستگاه", self.asset); form.addRow("پروفایل تحلیل", self.profile)
        form.addRow("نوع منبع", self.source_type); form.addRow("آدرس یا شناسه منبع", self.source)
        form.addRow("اپراتور مسئول", self.operator); form.addRow("مدیر کنترل کیفیت", self.qc_manager)
        form.addRow("مسئول HSE", self.hse_owner); form.addRow("وضعیت", self.enabled)
        form.addRow("منطق پروفایل", self.profile_help)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept); buttons.rejected.connect(self.reject); form.addRow(buttons)
        self.profile.currentIndexChanged.connect(self._update_profile_help); self._update_profile_help()

    def _update_profile_help(self) -> None:
        p = profile_by_key(str(self.profile.currentData()))
        indicators = "، ".join(p.primary_indicators_fa)
        targets = "، ".join(p.alert_targets_fa)
        self.profile_help.setPlainText(
            f"هدف: {p.purpose_fa}\nشاخص‌های اصلی: {indicators}\nمسیر هشدار پیش‌فرض: {targets}"
        )

    def _accept(self) -> None:
        if not self.name.text().strip() or not self.area.text().strip():
            QMessageBox.warning(self, "اطلاعات ناقص", "نام دوربین و ناحیه کارخانه الزامی است.")
            return
        self.accept()

    def value(self) -> CameraDefinition:
        current = self.camera
        return CameraDefinition(
            camera_id=current.camera_id if current else uuid4().hex[:12],
            name_fa=self.name.text().strip(), area_fa=self.area.text().strip(),
            asset_fa=self.asset.text().strip(), profile_key=str(self.profile.currentData()),
            source_type=self.source_type.currentText(), source_value=self.source.text().strip(),
            operator_fa=self.operator.text().strip(), qc_manager_fa=self.qc_manager.text().strip(),
            hse_owner_fa=self.hse_owner.text().strip(), enabled=self.enabled.isChecked(),
            status_fa=current.status_fa if current else "آماده اتصال",
            health_score=current.health_score if current else None,
            last_event_fa=current.last_event_fa if current else "—",
            last_seen_iso=current.last_seen_iso if current else None,
            metadata=current.metadata if current else {},
        )


class FactoryCameraCenterPage(QWidget):
    open_camera = Signal(object)

    def __init__(self, registry: CameraRegistry | None = None) -> None:
        super().__init__()
        self.registry = registry or CameraRegistry()
        self.cameras: list[CameraDefinition] = []
        self._build_ui(); self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        title = QLabel("مرکز مدیریت دوربین‌های کارخانه"); title.setObjectName("PageTitle")
        subtitle = QLabel("تعریف هر دوربین با پروفایل تخصصی، مسئولان جداگانه و مسیر هشدار کنترل‌شده.")
        subtitle.setObjectName("PageSubtitle")
        root.addWidget(title); root.addWidget(subtitle)

        cards = QGridLayout()
        self.total_card = MetricCard("کل دوربین‌ها"); self.active_card = MetricCard("فعال")
        self.warning_card = MetricCard("نیازمند توجه"); self.health_card = MetricCard("سلامت کارخانه")
        cards.addWidget(self.total_card,0,0); cards.addWidget(self.active_card,0,1)
        cards.addWidget(self.warning_card,0,2); cards.addWidget(self.health_card,0,3)
        root.addLayout(cards)

        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("افزودن دوربین"); self.edit_btn = QPushButton("ویرایش")
        self.delete_btn = QPushButton("حذف"); self.delete_btn.setObjectName("Danger")
        self.open_btn = QPushButton("بازکردن پایش دوربین")
        self.refresh_btn = QPushButton("بازخوانی"); self.refresh_btn.setObjectName("Secondary")
        self.profile_filter = QComboBox(); self.profile_filter.addItem("همه پروفایل‌ها", "")
        for p in profile_catalog(): self.profile_filter.addItem(p.title_fa, p.key)
        self.area_filter = QLineEdit(); self.area_filter.setPlaceholderText("فیلتر ناحیه یا مسئول…")
        for w in (self.add_btn,self.edit_btn,self.delete_btn,self.open_btn,self.refresh_btn): toolbar.addWidget(w)
        toolbar.addStretch(); toolbar.addWidget(QLabel("پروفایل:")); toolbar.addWidget(self.profile_filter)
        toolbar.addWidget(self.area_filter); root.addLayout(toolbar)

        body = QHBoxLayout()
        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels([
            "دوربین", "ناحیه", "دستگاه", "پروفایل", "منبع", "اپراتور",
            "مدیر QC / HSE", "وضعیت", "سلامت", "آخرین رخداد",
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)
        body.addWidget(self.table, 4)

        info = QFrame(); info.setObjectName("Card"); info_layout = QVBoxLayout(info)
        info_title = QLabel("منطق بهره‌برداری"); info_title.setObjectName("CardTitle")
        self.info = QTextEdit(); self.info.setReadOnly(True)
        self.info.setPlainText(
            "۱. هر دوربین فقط با پروفایل متناسب با وظیفه خودش تحلیل می‌شود.\n\n"
            "۲. اپراتور فقط هشدارهای دوربین‌های تخصیص‌یافته به خودش را دریافت می‌کند.\n\n"
            "۳. مدیر کنترل کیفیت نمای مواد اولیه، دیگ‌ها، پرکن و بسته‌بندی را می‌بیند؛ "
            "هشدارهای HSE برای مسئول HSE و سرپرست شیفت ارسال می‌شوند.\n\n"
            "۴. امتیاز کارخانه از دوربین‌های فعال محاسبه می‌شود، اما رخداد بحرانی هر ایستگاه "
            "به‌صورت مستقل قابل مشاهده باقی می‌ماند.\n\n"
            "۵. برای کاهش فشار سیستم، پیش‌نمایش همه دوربین‌ها هم‌زمان باز نمی‌شود؛ "
            "موتور پایش در پس‌زمینه کار می‌کند و کاربر فقط دوربین منتخب یا رخداددار را باز می‌کند."
        )
        self.profile_details = QTextEdit(); self.profile_details.setReadOnly(True); self.profile_details.setMaximumHeight(180)
        info_layout.addWidget(info_title); info_layout.addWidget(self.info,1)
        info_layout.addWidget(QLabel("پروفایل دوربین انتخاب‌شده")); info_layout.addWidget(self.profile_details)
        body.addWidget(info, 2); root.addLayout(body, 1)

        self.add_btn.clicked.connect(self.add_camera); self.edit_btn.clicked.connect(self.edit_camera)
        self.delete_btn.clicked.connect(self.delete_camera); self.open_btn.clicked.connect(self.open_selected)
        self.refresh_btn.clicked.connect(self.refresh); self.profile_filter.currentIndexChanged.connect(self._render)
        self.area_filter.textChanged.connect(self._render); self.table.itemSelectionChanged.connect(self._show_selected_profile)
        self.table.doubleClicked.connect(lambda _: self.open_selected())

    def refresh(self) -> None:
        self.cameras = self.registry.list(); self._render()

    def _filtered(self) -> list[CameraDefinition]:
        key = str(self.profile_filter.currentData() or "")
        text = self.area_filter.text().strip().lower()
        items = [c for c in self.cameras if not key or c.profile_key == key]
        if text:
            items = [c for c in items if text in " ".join([
                c.name_fa,c.area_fa,c.asset_fa,c.operator_fa,c.qc_manager_fa,c.hse_owner_fa
            ]).lower()]
        return items

    def _render(self) -> None:
        items = self._filtered(); self.table.setRowCount(len(items))
        for row, camera in enumerate(items):
            owner = camera.hse_owner_fa if camera.profile_key == "hse" else camera.qc_manager_fa
            values = [camera.name_fa,camera.area_fa,camera.asset_fa,camera.profile.title_fa,
                      camera.source_type,camera.operator_fa or "—",owner or "—",camera.status_fa,
                      "—" if camera.health_score is None else f"{camera.health_score:.1f}",camera.last_event_fa]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value)); item.setData(Qt.ItemDataRole.UserRole, camera.camera_id)
                if col == 7:
                    if "بحرانی" in camera.status_fa or "بالا" in camera.status_fa: item.setForeground(QColor("#b71c1c"))
                    elif "هشدار" in camera.status_fa or "پایش" in camera.status_fa: item.setForeground(QColor("#e65100"))
                    elif "پایدار" in camera.status_fa: item.setForeground(QColor("#1b5e20"))
                self.table.setItem(row,col,item)
        active = [c for c in self.cameras if c.enabled]
        scores = [c.health_score for c in active if c.health_score is not None]
        attention = sum(1 for c in active if c.health_score is not None and c.health_score < 80)
        self.total_card.set_value(str(len(self.cameras))); self.active_card.set_value(str(len(active)))
        self.warning_card.set_value(str(attention)); self.health_card.set_value("—" if not scores else f"{sum(scores)/len(scores):.1f}%")
        self._show_selected_profile()

    def _selected(self) -> CameraDefinition | None:
        row = self.table.currentRow()
        if row < 0 or self.table.item(row,0) is None: return None
        camera_id = str(self.table.item(row,0).data(Qt.ItemDataRole.UserRole))
        return next((c for c in self.cameras if c.camera_id == camera_id), None)

    def _show_selected_profile(self) -> None:
        camera = self._selected()
        if camera is None:
            self.profile_details.setPlainText("برای دیدن منطق تحلیل و مسیر هشدار، یک دوربین را انتخاب کنید.")
            return
        p = camera.profile
        self.profile_details.setPlainText(
            f"{p.title_fa}\nهدف: {p.purpose_fa}\nشاخص‌ها: {'، '.join(p.primary_indicators_fa)}\n"
            f"مسئول پیش‌فرض: {p.default_owner_role_fa}\nگیرندگان هشدار: {'، '.join(p.alert_targets_fa)}"
        )

    def add_camera(self) -> None:
        dialog = CameraEditorDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.registry.upsert(dialog.value()); self.refresh()

    def edit_camera(self) -> None:
        camera = self._selected()
        if camera is None: QMessageBox.information(self,"انتخاب دوربین","یک دوربین را انتخاب کنید."); return
        dialog = CameraEditorDialog(camera,parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.registry.upsert(dialog.value()); self.refresh()

    def delete_camera(self) -> None:
        camera = self._selected()
        if camera is None: return
        answer = QMessageBox.question(self,"حذف دوربین",f"دوربین «{camera.name_fa}» حذف شود؟")
        if answer == QMessageBox.StandardButton.Yes:
            self.registry.delete(camera.camera_id); self.refresh()

    def open_selected(self) -> None:
        camera = self._selected()
        if camera is None: QMessageBox.information(self,"انتخاب دوربین","یک دوربین را انتخاب کنید."); return
        if not camera.enabled: QMessageBox.warning(self,"دوربین غیرفعال","ابتدا دوربین را فعال کنید."); return
        self.open_camera.emit(camera)
