from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox,QGroupBox,QHBoxLayout,QHeaderView,QLabel,
    QPushButton,QTableWidget,QTableWidgetItem,QTextEdit,QVBoxLayout,QWidget)

from visionqc.application.services.predictive_quality_service import PredictiveQualityService


class PredictiveQualityPage(QWidget):
    def __init__(self, service: PredictiveQualityService) -> None:
        super().__init__(); self.service=service; self._forecast=None; self._build(); self.refresh_scopes()

    def _build(self):
        layout=QVBoxLayout(self)
        title=QLabel("Predictive Quality"); title.setObjectName("pageTitle")
        sub=QLabel("Explainable early warning from Factory Memory. Forecasts quality risk for the next comparable production window; they do not replace QC judgement."); sub.setWordWrap(True)
        layout.addWidget(title); layout.addWidget(sub)
        row=QHBoxLayout(); self.product=QComboBox(); self.line=QComboBox(); self.machine=QComboBox()
        run=QPushButton("Generate Forecast"); run.clicked.connect(self.run_forecast)
        refresh=QPushButton("Refresh Scopes"); refresh.clicked.connect(self.refresh_scopes)
        for label,widget in (("Product",self.product),("Line",self.line),("Machine",self.machine)):
            row.addWidget(QLabel(label+":")); row.addWidget(widget)
        row.addStretch(1); row.addWidget(run); row.addWidget(refresh); layout.addLayout(row)
        self.banner=QLabel("Choose a scope and generate a forecast."); self.banner.setWordWrap(True); self.banner.setObjectName("statusCard"); layout.addWidget(self.banner)
        self.table=QTableWidget(0,4); self.table.setHorizontalHeaderLabels(["Risk driver","Contribution","Evidence","Explanation"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers); self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeToContents); self.table.horizontalHeader().setSectionResizeMode(3,QHeaderView.Stretch)
        layout.addWidget(self.table,1)
        box=QGroupBox("Recommended actions and limitations"); v=QVBoxLayout(box); self.detail=QTextEdit(); self.detail.setReadOnly(True); v.addWidget(self.detail); layout.addWidget(box,1)

    def refresh_scopes(self):
        scopes=self.service.available_scopes()
        self._fill(self.product,"All products",scopes["products"]); self._fill(self.line,"All lines",scopes["lines"]); self._fill(self.machine,"All machines",scopes["machines"])

    @staticmethod
    def _fill(combo,all_label,values):
        current=combo.currentText(); combo.clear(); combo.addItem(all_label,None)
        for value in values: combo.addItem(value,value)
        idx=combo.findText(current)
        if idx>=0: combo.setCurrentIndex(idx)

    def run_forecast(self):
        self._forecast=self.service.forecast(product_name=self.product.currentData(),line=self.line.currentData(),machine=self.machine.currentData())
        f=self._forecast
        self.banner.setText(f"{f.risk_band} risk — score {f.risk_score*100:.1f}% | predicted reject {f.predicted_reject_rate*100:.1f}% | current {f.current_reject_rate*100:.1f}% | baseline {f.baseline_reject_rate*100:.1f}% | trend {f.trend} | confidence {f.confidence*100:.1f}%")
        self.table.setRowCount(len(f.drivers))
        for r,d in enumerate(f.drivers):
            vals=[d.name,f"{d.contribution*100:.1f}%",str(d.evidence_count),d.explanation]
            for c,val in enumerate(vals):
                item=QTableWidgetItem(val); item.setTextAlignment(Qt.AlignLeft|Qt.AlignVCenter if c in {0,3} else Qt.AlignCenter); self.table.setItem(r,c,item)
        lines=["RECOMMENDED ACTIONS"]+[f"{i+1}. {x}" for i,x in enumerate(f.recommended_actions)]
        lines += ["","LIMITATIONS"]+[f"• {x}" for x in f.limitations]
        self.detail.setPlainText("\n".join(lines))
