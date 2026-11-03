from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class TemporalChart(QWidget):
    """Dependency-free timeline chart for 0..100 quality signals."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(240)
        self.series: dict[str, list[tuple[float, float]]] = {}

    def set_series(self, series: dict[str, list[tuple[float, float]]]) -> None:
        self.series = series
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(52, 20, -18, -38)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        painter.setPen(QPen(QColor("#d9e2e9"), 1))
        for i in range(6):
            y = rect.bottom() - rect.height() * i / 5
            painter.drawLine(rect.left(), int(y), rect.right(), int(y))
            painter.setPen(QColor("#667681")); painter.drawText(8, int(y + 4), f"{i*20}")
            painter.setPen(QPen(QColor("#d9e2e9"), 1))
        if not self.series:
            painter.setPen(QColor("#687681")); painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No temporal samples")
            return
        max_x = max((pts[-1][0] for pts in self.series.values() if pts), default=1.0) or 1.0
        palette = [QColor("#286f9f"), QColor("#c26b16"), QColor("#4a8a55"), QColor("#7a5aa6")]
        legend_x = rect.left()
        for idx, (name, points) in enumerate(self.series.items()):
            if not points: continue
            color = palette[idx % len(palette)]
            painter.setPen(QPen(color, 2.2))
            mapped = [QPointF(rect.left() + (x/max_x)*rect.width(), rect.bottom() - (max(0,min(100,y))/100)*rect.height()) for x,y in points]
            for a,b in zip(mapped, mapped[1:]): painter.drawLine(a,b)
            painter.setPen(color); painter.drawText(int(legend_x), self.height()-14, name); legend_x += 155
        painter.setPen(QColor("#667681")); painter.drawText(rect.right()-95, self.height()-14, f"{max_x:.1f} seconds")
