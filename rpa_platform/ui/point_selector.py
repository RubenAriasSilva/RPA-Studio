from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QImage, QPixmap, QCursor
import pyautogui
import numpy as np


class PointSelectorOverlay(QWidget):
    """
    Full-screen overlay — single left-click captures (x, y).
    ESC cancels.
    """
    point_selected = pyqtSignal(int, int)
    cancelled = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._bg: QPixmap | None = None
        self._cursor_pos = None
        self._setup_window()

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)

        screens = QApplication.screens()
        combined = screens[0].geometry()
        for s in screens[1:]:
            combined = combined.united(s.geometry())
        self.setGeometry(combined)

    def start(self):
        img = pyautogui.screenshot()
        arr = np.array(img)
        h, w, ch = arr.shape
        qimg = QImage(arr.data, w, h, w * ch, QImage.Format.Format_RGB888)
        self._bg = QPixmap.fromImage(qimg)
        self._cursor_pos = None
        self.showFullScreen()
        self.activateWindow()
        self.raise_()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            self.cancelled.emit()

    def mouseMoveEvent(self, event):
        self._cursor_pos = event.pos()
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.hide()
            origin = self.geometry().topLeft()
            abs_x = origin.x() + event.pos().x()
            abs_y = origin.y() + event.pos().y()
            self.point_selected.emit(abs_x, abs_y)

    def paintEvent(self, event):
        painter = QPainter(self)
        w, h = self.width(), self.height()

        if self._bg:
            painter.drawPixmap(0, 0, w, h, self._bg)

        painter.fillRect(0, 0, w, h, QColor(0, 0, 0, 110))

        if self._cursor_pos:
            cx, cy = self._cursor_pos.x(), self._cursor_pos.y()

            # Crosshair lines across full screen
            pen = QPen(QColor("#007AFF"), 1)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(0, cy, w, cy)
            painter.drawLine(cx, 0, cx, h)

            # Solid crosshair around cursor
            painter.setPen(QPen(QColor("#cba6f7"), 2))
            gap, arm = 8, 20
            painter.drawLine(cx - arm - gap, cy, cx - gap, cy)
            painter.drawLine(cx + gap, cy, cx + arm + gap, cy)
            painter.drawLine(cx, cy - arm - gap, cx, cy - gap)
            painter.drawLine(cx, cy + gap, cx, cy + arm + gap)

            # Magnifier circle border
            painter.setPen(QPen(QColor("#34C759"), 1))
            painter.drawEllipse(cx - 6, cy - 6, 12, 12)

            # Coordinates tooltip
            origin = self.geometry().topLeft()
            abs_x = origin.x() + cx
            abs_y = origin.y() + cy
            label = f"  x: {abs_x}   y: {abs_y}  "
            font = QFont("Consolas", 11, QFont.Weight.Bold)
            painter.setFont(font)
            fm = painter.fontMetrics()
            lw = fm.horizontalAdvance(label) + 4
            lh = fm.height() + 4
            tx = min(cx + 18, w - lw - 4)
            ty = cy + 18
            if ty + lh > h:
                ty = cy - lh - 8
            painter.fillRect(tx, ty, lw, lh, QColor(30, 30, 46, 220))
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(tx + 2, ty + lh - 4, label)

        else:
            font = QFont("Segoe UI", 14)
            painter.setFont(font)
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Haz click en el punto que deseas capturar\n\nESC para cancelar",
            )
