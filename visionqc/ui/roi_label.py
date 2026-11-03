from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel


class RoiImageLabel(QLabel):
    roi_changed = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(540, 380)
        self.setText("Load an image to begin")
        self.setStyleSheet("background:#202a33; color:#dbe7ef; border-radius:8px;")
        self._source_pixmap: QPixmap | None = None
        self._display_rect = QRect()
        self._start: QPoint | None = None
        self._current: QPoint | None = None
        self._roi_widget: QRect | None = None
        self._roi_image: tuple[int, int, int, int] | None = None

    def set_source_pixmap(self, pixmap: QPixmap) -> None:
        self._source_pixmap = pixmap
        self.clear_roi()
        self.update()

    def clear_roi(self) -> None:
        self._start = None
        self._current = None
        self._roi_widget = None
        self._roi_image = None
        self.roi_changed.emit(None)
        self.update()

    def image_roi(self) -> tuple[int, int, int, int] | None:
        return self._roi_image

    def _scaled_geometry(self) -> tuple[QPixmap | None, QRect]:
        if not self._source_pixmap:
            return None, QRect()
        scaled = self._source_pixmap.scaled(
            self.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        return scaled, QRect(x, y, scaled.width(), scaled.height())

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        scaled, rect = self._scaled_geometry()
        self._display_rect = rect
        if scaled:
            painter.drawPixmap(rect.topLeft(), scaled)
        if self._roi_widget:
            painter.setPen(QPen(QColor(255, 193, 7), 3))
            painter.setBrush(QColor(255, 193, 7, 35))
            painter.drawRect(self._roi_widget.normalized())
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(self._roi_widget.normalized().adjusted(6, 6, -6, -6), "ROI")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._source_pixmap and self._display_rect.contains(event.position().toPoint()):
            self._start = event.position().toPoint()
            self._current = self._start
            self._roi_widget = QRect(self._start, self._current)
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._start is not None:
            point = event.position().toPoint()
            point.setX(max(self._display_rect.left(), min(point.x(), self._display_rect.right())))
            point.setY(max(self._display_rect.top(), min(point.y(), self._display_rect.bottom())))
            self._current = point
            self._roi_widget = QRect(self._start, self._current).normalized()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._start is None or not self._source_pixmap:
            return
        self.mouseMoveEvent(event)
        rect = self._roi_widget.normalized() if self._roi_widget else QRect()
        self._start = None
        self._current = None
        if rect.width() < 10 or rect.height() < 10:
            self.clear_roi()
            return
        sx = self._source_pixmap.width() / self._display_rect.width()
        sy = self._source_pixmap.height() / self._display_rect.height()
        x = int((rect.left() - self._display_rect.left()) * sx)
        y = int((rect.top() - self._display_rect.top()) * sy)
        w = int(rect.width() * sx)
        h = int(rect.height() * sy)
        self._roi_image = (x, y, w, h)
        self.roi_changed.emit(self._roi_image)
        self.update()
