from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class PlaceholderPage(QWidget):
    def __init__(self, title: str, description: str, delivery: str) -> None:
        super().__init__(); layout = QVBoxLayout(self); layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h = QLabel(title); h.setObjectName("PlaceholderTitle"); h.setAlignment(Qt.AlignmentFlag.AlignCenter)
        d = QLabel(description); d.setWordWrap(True); d.setMaximumWidth(720); d.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge = QLabel(delivery); badge.setObjectName("RoadmapBadge"); badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        back = QPushButton("Open All Features Menu"); back.setObjectName("Secondary")
        layout.addWidget(h); layout.addWidget(d); layout.addWidget(badge); layout.addWidget(back)
        self.back_button = back
