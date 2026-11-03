from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from visionqc.application.services.factory_memory_service import FactoryMemoryService
from visionqc.domain.factory_memory import (
    DefectObservation, FactoryMemoryCase, ProcessSnapshot, ProductionContext,
)


class FactoryMemoryPage(QWidget):
    """Operator-facing view for capturing and reviewing factory memory cases."""

    def __init__(self, service: FactoryMemoryService) -> None:
        super().__init__()
        self.service = service
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        title = QLabel("Factory Memory")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Turn inspections, process conditions and corrective actions into reusable factory knowledge.")
        subtitle.setWordWrap(True)
        outer.addWidget(title)
        outer.addWidget(subtitle)

        form_box = QGroupBox("Capture a factory memory case")
        form = QFormLayout(form_box)
        self.product = QLineEdit(); self.product.setPlaceholderText("e.g. Chicken Hot Dog")
        self.batch = QLineEdit(); self.line = QLineEdit(); self.shift = QLineEdit()
        self.operator = QLineEdit(); self.machine = QLineEdit(); self.recipe = QLineEdit()
        self.supplier = QLineEdit(); self.stage = QLineEdit()
        self.outcome = QComboBox(); self.outcome.addItems(["Rejected", "Accepted"])
        self.defect = QLineEdit(); self.defect.setPlaceholderText("e.g. Casing tear")
        self.severity = QComboBox(); self.severity.addItems(["Reject", "Critical", "Warning", "Information"])
        self.confidence = QDoubleSpinBox(); self.confidence.setRange(0,100); self.confidence.setValue(90); self.confidence.setSuffix(" %")
        self.temp = QDoubleSpinBox(); self.temp.setRange(-50,200); self.temp.setDecimals(2); self.temp.setSuffix(" °C")
        self.speed = QDoubleSpinBox(); self.speed.setRange(0,100000); self.speed.setDecimals(2)
        self.vacuum = QDoubleSpinBox(); self.vacuum.setRange(-10,10); self.vacuum.setDecimals(3); self.vacuum.setSuffix(" bar")
        self.notes = QTextEdit(); self.notes.setMaximumHeight(70)
        rows = [
            ("Product *", self.product), ("Batch code", self.batch), ("Production line", self.line),
            ("Shift", self.shift), ("Operator", self.operator), ("Machine", self.machine),
            ("Recipe", self.recipe), ("Supplier", self.supplier), ("Process stage", self.stage),
            ("Outcome", self.outcome), ("Defect", self.defect), ("Severity", self.severity),
            ("AI confidence", self.confidence), ("Dough temperature", self.temp),
            ("Line speed", self.speed), ("Vacuum", self.vacuum), ("Operator notes", self.notes),
        ]
        for label, widget in rows: form.addRow(label, widget)
        actions = QHBoxLayout()
        save = QPushButton("Save to Factory Memory"); save.clicked.connect(self.capture_case)
        clear = QPushButton("Clear"); clear.clicked.connect(self.clear_form)
        refresh = QPushButton("Refresh"); refresh.clicked.connect(self.refresh)
        actions.addWidget(save); actions.addWidget(clear); actions.addStretch(1); actions.addWidget(refresh)
        form.addRow(actions)
        outer.addWidget(form_box)

        self.summary = QLabel()
        outer.addWidget(self.summary)
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(["UUID", "Created", "Product", "Batch", "Line", "Machine", "Outcome", "Defects", "Status"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        outer.addWidget(self.table, 1)

    def capture_case(self) -> None:
        product = self.product.text().strip()
        if not product:
            QMessageBox.warning(self, "Factory Memory", "Product name is required.")
            return
        passed = self.outcome.currentText() == "Accepted"
        defects = []
        defect_name = self.defect.text().strip()
        if defect_name:
            defects.append(DefectObservation(
                defect_type=defect_name,
                severity=self.severity.currentText(),
                confidence=self.confidence.value()/100.0,
            ))
        case = FactoryMemoryCase(
            product_name=product,
            passed=passed,
            production=ProductionContext(
                batch_code=self.batch.text().strip(), production_line=self.line.text().strip(),
                shift_name=self.shift.text().strip(), operator_name=self.operator.text().strip(),
                machine_name=self.machine.text().strip(), recipe_name=self.recipe.text().strip(),
                supplier_name=self.supplier.text().strip(), process_stage=self.stage.text().strip(),
            ),
            process=ProcessSnapshot(
                dough_temperature_c=self.temp.value(), line_speed=self.speed.value(), vacuum_bar=self.vacuum.value(),
            ),
            defects=defects,
            operator_notes=self.notes.toPlainText().strip(),
        )
        try:
            case_id = self.service.capture(case)
        except Exception as exc:
            QMessageBox.critical(self, "Factory Memory", str(exc))
            return
        QMessageBox.information(self, "Factory Memory", f"Case #{case_id} was saved successfully.")
        self.clear_form(); self.refresh()

    def clear_form(self) -> None:
        for widget in (self.product,self.batch,self.line,self.shift,self.operator,self.machine,self.recipe,self.supplier,self.stage,self.defect):
            widget.clear()
        self.notes.clear(); self.outcome.setCurrentIndex(0); self.confidence.setValue(90)
        self.temp.setValue(0); self.speed.setValue(0); self.vacuum.setValue(0)

    def refresh(self) -> None:
        cases = self.service.list_recent(200)
        self.table.setRowCount(len(cases))
        rejected = sum(not case.passed for case in cases)
        verified = sum(case.qc_approved for case in cases)
        self.summary.setText(f"Stored cases: {len(cases)}   |   Rejected cases: {rejected}   |   QC-verified knowledge: {verified}")
        for row, case in enumerate(cases):
            values = [
                case.case_uuid[:8], case.created_at.replace("T", " ")[:19], case.product_name,
                case.production.batch_code, case.production.production_line, case.production.machine_name,
                "Accepted" if case.passed else "Rejected", ", ".join(d.defect_type for d in case.defects), str(case.status),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 6:
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, col, item)
