from __future__ import annotations

from collections import defaultdict
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget
from visionqc.ui.feature_catalog import FEATURES


class FeaturesPage(QWidget):
    navigate = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        title = QLabel("All VisionQC Capabilities")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Open available modules and see the complete product roadmap from one menu.")
        subtitle.setObjectName("PageSubtitle")
        root.addWidget(title); root.addWidget(subtitle)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget(); body_layout = QVBoxLayout(body)
        grouped = defaultdict(list)
        for category, name, desc, status in FEATURES:
            grouped[category].append((name, desc, status))
        for category, entries in grouped.items():
            heading = QLabel(category); heading.setObjectName("SectionTitle"); body_layout.addWidget(heading)
            grid = QGridLayout(); grid.setHorizontalSpacing(14); grid.setVerticalSpacing(14)
            for i, (name, desc, status) in enumerate(entries):
                card = QFrame(); card.setObjectName("FeatureCard")
                lay = QVBoxLayout(card)
                top = QHBoxLayout(); nm = QLabel(name); nm.setObjectName("FeatureTitle")
                badge = QLabel({"available":"AVAILABLE", "next":"NEXT SPRINT", "planned":"PLANNED"}[status]); badge.setObjectName(f"Badge_{status}")
                top.addWidget(nm); top.addStretch(); top.addWidget(badge); lay.addLayout(top)
                d = QLabel(desc); d.setWordWrap(True); d.setObjectName("FeatureDescription"); lay.addWidget(d)
                btn = QPushButton("Open" if status == "available" else "View plan")
                if status != "available": btn.setObjectName("Secondary")
                btn.clicked.connect(lambda checked=False, n=name: self.navigate.emit(n))
                lay.addWidget(btn)
                grid.addWidget(card, i // 3, i % 3)
            body_layout.addLayout(grid)
        body_layout.addStretch(); scroll.setWidget(body); root.addWidget(scroll)
