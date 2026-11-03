from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget
from visionqc.ui.widgets import MetricCard


class HomePage(QWidget):
    open_features = Signal()
    open_analysis = Signal()
    def __init__(self) -> None:
        super().__init__(); layout=QVBoxLayout(self)
        title=QLabel("VisionQC Dashboard"); title.setObjectName("PageTitle")
        subtitle=QLabel("Offline-first industrial visual quality intelligence"); subtitle.setObjectName("PageSubtitle")
        layout.addWidget(title); layout.addWidget(subtitle)
        grid=QGridLayout(); grid.addWidget(MetricCard("Application Version","0.2.2"),0,0); grid.addWidget(MetricCard("Deep Metrics","70+"),0,1)
        grid.addWidget(MetricCard("Diagnostic Views","4"),1,0); grid.addWidget(MetricCard("System State","Ready"),1,1); layout.addLayout(grid)
        note=QLabel("Sprint 2.2 expands analysis depth with percentiles, noise/SNR proxies, multi-space color statistics, GLCM, LBP, histograms, heatmaps, surface overlays and additional explainable rules.")
        note.setWordWrap(True); note.setObjectName("InfoPanel"); layout.addWidget(note)
        actions=QGridLayout(); analyze=QPushButton("Open Deep Image Analysis"); menu=QPushButton("☰ Show All Software Capabilities"); menu.setObjectName("MenuPrimary")
        analyze.clicked.connect(self.open_analysis); menu.clicked.connect(self.open_features); actions.addWidget(analyze,0,0); actions.addWidget(menu,0,1); layout.addLayout(actions); layout.addStretch()
