from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QWidget


class HistogramWidget(QWidget):
    def __init__(self) -> None:
        super().__init__(); self.setMinimumHeight(230); self.series: dict[str, list[float]] = {}

    def set_series(self, series: dict[str, list[float]]) -> None:
        self.series = series; self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self); p.fillRect(self.rect(), QColor("white")); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = self.rect().adjusted(38, 18, -18, -30)
        p.setPen(QPen(QColor("#ccd7df"), 1)); p.drawRect(area)
        colors = ["#455a64", "#d84315", "#2e7d32", "#1565c0", "#8e24aa", "#ef6c00"]
        for idx, (name, values) in enumerate(self.series.items()):
            if len(values) < 2: continue
            pen = QPen(QColor(colors[idx % len(colors)]), 2); p.setPen(pen)
            pts = [QPointF(area.left()+i*area.width()/(len(values)-1), area.bottom()-v*area.height()) for i,v in enumerate(values)]
            for a,b in zip(pts, pts[1:]): p.drawLine(a,b)
        x, y = area.left(), self.height()-8
        for idx, name in enumerate(self.series):
            p.setPen(QPen(QColor(colors[idx % len(colors)]), 3)); p.drawLine(x, y-4, x+15, y-4)
            p.setPen(QColor("#34495e")); p.drawText(x+20, y, name); x += 90


class PngPreview(QLabel):
    def __init__(self) -> None:
        super().__init__("No visualization"); self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(420, 300); self.setStyleSheet("background:#202a33;color:#dbe7ef;border-radius:8px;")
        self._pixmap = None

    def set_png(self, data: bytes) -> None:
        pix = QPixmap(); pix.loadFromData(data, "PNG"); self._pixmap = pix; self._refresh()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event); self._refresh()

    def _refresh(self) -> None:
        if self._pixmap:
            self.setPixmap(self._pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
