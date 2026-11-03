from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget, QLineEdit,
)

from visionqc.application.services.factory_learning_service import FactoryLearningService
from visionqc.application.services.factory_memory_service import FactoryMemoryService


class FactoryLearningPage(QWidget):
    """QC learning dashboard built from verified Factory Memory cases."""

    def __init__(self, learning: FactoryLearningService, memory: FactoryMemoryService) -> None:
        super().__init__()
        self.learning = learning
        self.memory = memory
        self._case_ids: list[int] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        title = QLabel("یادگیری کارخانه و اثربخشی اقدامات")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "این صفحه فقط از رخدادهای ثبت‌شده، علل تأییدشده توسط QC و نتیجه اقدامات اصلاحی استفاده می‌کند. "
            "خروجی‌ها رابطه و تجربه عملیاتی را نشان می‌دهند و به‌تنهایی اثبات علت علمی نیستند."
        )
        subtitle.setWordWrap(True)
        outer.addWidget(title)
        outer.addWidget(subtitle)

        controls = QHBoxLayout()
        self.product_filter = QComboBox(); self.product_filter.setMinimumWidth(260)
        self.product_filter.currentIndexChanged.connect(self.refresh_summary)
        refresh = QPushButton("به‌روزرسانی"); refresh.clicked.connect(self.refresh)
        controls.addWidget(QLabel("محصول:")); controls.addWidget(self.product_filter); controls.addStretch(1); controls.addWidget(refresh)
        outer.addLayout(controls)

        self.kpis = QLabel(); self.kpis.setWordWrap(True); self.kpis.setObjectName("summaryCard")
        outer.addWidget(self.kpis)

        tables = QHBoxLayout()
        self.cause_table = self._table(["علت تأییدشده", "تعداد", "سهم"])
        self.defect_table = self._table(["عیب", "تعداد", "سهم"])
        self.hotspot_table = self._table(["دستگاه/شیفت", "تعداد", "سهم", "نوع"])
        for label, table in (("علل پرتکرار", self.cause_table), ("عیوب پرتکرار", self.defect_table), ("نقاط داغ", self.hotspot_table)):
            box = QGroupBox(label); lay = QVBoxLayout(box); lay.addWidget(table); tables.addWidget(box, 1)
        outer.addLayout(tables, 2)

        action_box = QGroupBox("اثربخشی اقدامات اصلاحی")
        action_lay = QVBoxLayout(action_box)
        self.action_table = self._table(["اقدام", "دفعات", "موثر", "ناموثر", "نرخ اثربخشی", "آخرین نتیجه"])
        action_lay.addWidget(self.action_table)
        outer.addWidget(action_box, 2)

        recommendation_box = QGroupBox("پیشنهاد مبتنی بر موارد مشابه تأییدشده")
        rec_lay = QVBoxLayout(recommendation_box)
        row = QHBoxLayout()
        self.case_combo = QComboBox(); self.case_combo.setMinimumWidth(620)
        run = QPushButton("استخراج اقدامات مشابه"); run.clicked.connect(self.recommend)
        row.addWidget(QLabel("رخداد جاری:")); row.addWidget(self.case_combo, 1); row.addWidget(run)
        self.recommendations = QTextEdit(); self.recommendations.setReadOnly(True); self.recommendations.setMaximumHeight(180)
        rec_lay.addLayout(row); rec_lay.addWidget(self.recommendations)
        feedback=QHBoxLayout(); self.action_combo=QComboBox(); self.verifier=QLineEdit(); self.verifier.setPlaceholderText("نام تأییدکننده")
        self.action_result=QLineEdit(); self.action_result.setPlaceholderText("نتیجه اقدام")
        effective=QPushButton("ثبت موثر"); effective.clicked.connect(lambda: self.record_outcome(True))
        ineffective=QPushButton("ثبت ناموثر"); ineffective.clicked.connect(lambda: self.record_outcome(False))
        feedback.addWidget(QLabel("بازخورد اقدام:")); feedback.addWidget(self.action_combo,1); feedback.addWidget(self.verifier); feedback.addWidget(self.action_result,1); feedback.addWidget(effective); feedback.addWidget(ineffective)
        rec_lay.addLayout(feedback)
        self.case_combo.currentIndexChanged.connect(self._load_actions)
        outer.addWidget(recommendation_box)

        self.limitations = QLabel(); self.limitations.setWordWrap(True)
        outer.addWidget(self.limitations)

    @staticmethod
    def _table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers)); table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.NoEditTriggers); table.setSelectionBehavior(QTableWidget.SelectRows)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    def refresh(self) -> None:
        cases = self.memory.list_recent(5000)
        current = self.product_filter.currentText()
        products = sorted({c.product_name for c in cases if c.product_name.strip()})
        self.product_filter.blockSignals(True); self.product_filter.clear(); self.product_filter.addItem("همه محصولات")
        self.product_filter.addItems(products)
        if current in ["همه محصولات", *products]: self.product_filter.setCurrentText(current)
        self.product_filter.blockSignals(False)
        self.case_combo.clear(); self._case_ids=[]
        repo = getattr(self.memory, "_repository", None)
        for c in cases:
            if c.passed: continue
            cid = self._resolve_id(c.case_uuid)
            if cid is None: continue
            self._case_ids.append(cid)
            defects = ", ".join(d.defect_type for d in c.defects) or "بدون برچسب عیب"
            self.case_combo.addItem(f"#{cid} | {c.product_name} | {defects} | {c.created_at[:19]}")
        self._load_actions()
        self.refresh_summary()

    def _load_actions(self) -> None:
        self.action_combo.clear()
        idx=self.case_combo.currentIndex()
        if idx<0 or idx>=len(self._case_ids): return
        case=self.memory.get(self._case_ids[idx])
        if case is None: return
        for i,a in enumerate(case.corrective_actions):
            self.action_combo.addItem(f"{i+1}. {a.action_type}: {a.description}",i)

    def record_outcome(self,effective: bool) -> None:
        idx=self.case_combo.currentIndex()
        action_idx=self.action_combo.currentData()
        if idx<0 or idx>=len(self._case_ids) or action_idx is None:
            QMessageBox.information(self,"یادگیری کارخانه","برای این رخداد اقدام اصلاحی ثبت نشده است."); return
        try:
            self.memory.record_action_outcome(self._case_ids[idx],int(action_idx),result=self.action_result.text().strip(),verified_by=self.verifier.text().strip(),effective=effective)
        except Exception as exc:
            QMessageBox.critical(self,"یادگیری کارخانه",str(exc)); return
        QMessageBox.information(self,"یادگیری کارخانه","نتیجه اقدام ثبت شد و در محاسبات اثربخشی استفاده خواهد شد.")
        self.refresh()

    def refresh_summary(self) -> None:
        product = self.product_filter.currentText()
        summary = self.learning.summarize(product_name=None if product == "همه محصولات" else product)
        self.kpis.setText(
            f"کل موارد: {summary.total_cases}  |  مردود: {summary.rejected_cases}  |  علل تأییدشده QC: {summary.verified_cases}  |  "
            f"نرخ تأیید علت: {summary.verification_rate:.1f}%  |  نرخ تکرار عیب: {summary.recurrence_rate:.1f}%  |  "
            f"اثربخشی اقدامات دارای نتیجه: {summary.action_effectiveness_rate:.1f}%"
        )
        self._fill_ranked(self.cause_table, summary.top_causes)
        self._fill_ranked(self.defect_table, summary.top_defects)
        hotspots = [(x, "دستگاه") for x in summary.machine_hotspots] + [(x, "شیفت") for x in summary.shift_hotspots]
        self.hotspot_table.setRowCount(len(hotspots))
        for r, (item, kind) in enumerate(hotspots):
            for c, value in enumerate((item.label, str(item.count), f"{item.percentage:.1f}%", kind)):
                self.hotspot_table.setItem(r, c, QTableWidgetItem(value))
        self.action_table.setRowCount(len(summary.action_insights))
        for r, a in enumerate(summary.action_insights):
            vals=(a.action_type,str(a.attempts),str(a.effective),str(a.ineffective),f"{a.effectiveness_rate:.1f}%",a.last_result)
            for c,v in enumerate(vals): self.action_table.setItem(r,c,QTableWidgetItem(v))
        self.limitations.setText("محدودیت داده: " + (" | ".join(summary.limitations) if summary.limitations else "حجم داده اولیه برای نمایش روند کافی است؛ تأیید مهندس فرایند همچنان الزامی است."))

    @staticmethod
    def _fill_ranked(table: QTableWidget, items) -> None:
        table.setRowCount(len(items))
        for r,item in enumerate(items):
            for c,value in enumerate((item.label,str(item.count),f"{item.percentage:.1f}%")):
                table.setItem(r,c,QTableWidgetItem(value))

    def recommend(self) -> None:
        idx=self.case_combo.currentIndex()
        if idx<0 or idx>=len(self._case_ids):
            QMessageBox.information(self,"یادگیری کارخانه","رخداد مردودی برای بررسی وجود ندارد."); return
        try: rows=self.learning.recommend_actions(self._case_ids[idx],limit=6)
        except Exception as exc:
            QMessageBox.critical(self,"یادگیری کارخانه",str(exc)); return
        if not rows:
            self.recommendations.setPlainText("هنوز مورد مشابه تأییدشده با اقدام دارای نتیجه کافی وجود ندارد."); return
        lines=[]
        for i,row in enumerate(rows,1):
            lines.append(f"{i}. {row.action_type}: {row.description}\n   پشتیبانی: {row.support_count} مورد | اثربخشی ثبت‌شده: {row.effectiveness_rate:.1f}% | اطمینان پیشنهادی: {row.confidence:.1f}%")
            if row.evidence: lines.append("   شواهد: " + "؛ ".join(row.evidence))
        lines.append("\nاین پیشنهادها Advisory هستند و باید توسط QC/مهندس فرایند تأیید شوند.")
        self.recommendations.setPlainText("\n".join(lines))

    @staticmethod
    def _resolve_id(uuid: str) -> int | None:
        try:
            from visionqc.core.database import connect
            with connect() as conn:
                row=conn.execute("SELECT id FROM factory_memory_cases WHERE case_uuid=?",(uuid,)).fetchone()
                return int(row[0]) if row else None
        except Exception:
            return None
