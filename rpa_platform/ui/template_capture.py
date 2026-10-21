import os
from datetime import datetime
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QImage, QPixmap
import pyautogui
import numpy as np


class TemplateCaptureOverlay(QWidget):
    """
    Drag to select a region → saves it as PNG → emits captured(file_path).
    Used to build template images for FindImage / WaitForImage actions.
    """
    captured = pyqtSignal(str)   # emits saved file path
    cancelled = pyqtSignal()

    def __init__(self, save_dir: str = "assets"):
        super().__init__()
        self._save_dir = save_dir
        self._bg: QPixmap | None = None
        self._bg_raw = None          # PIL image for cropping
        self._start = None
        self._end = None
        self._selecting = False
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
        self._bg_raw = pyautogui.screenshot()
        arr = np.array(self._bg_raw)
        h, w, ch = arr.shape
        qimg = QImage(arr.data, w, h, w * ch, QImage.Format.Format_RGB888)
        self._bg = QPixmap.fromImage(qimg)
        self._start = None
        self._end = None
        self._selecting = False
        self.showFullScreen()
        self.activateWindow()
        self.raise_()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            self.cancelled.emit()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start = event.pos()
            self._end = event.pos()
            self._selecting = True
            self.update()

    def mouseMoveEvent(self, event):
        if self._selecting:
            self._end = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._selecting:
            self._end = event.pos()
            self._selecting = False
            self.hide()
            self._save_template()

    def _normalized_rect(self):
        from PyQt6.QtCore import QRect
        if self._start is None or self._end is None:
            return QRect()
        return QRect(self._start, self._end).normalized()

    def _save_template(self):
        from PyQt6.QtCore import QRect
        rect = self._normalized_rect()
        if rect.width() < 4 or rect.height() < 4:
            self.cancelled.emit()
            return

        # Convert to screen coords
        origin = self.geometry().topLeft()
        abs_x = origin.x() + rect.x()
        abs_y = origin.y() + rect.y()

        try:
            # Crop from the PIL screenshot
            region = self._bg_raw.crop((abs_x, abs_y, abs_x + rect.width(), abs_y + rect.height()))

            os.makedirs(self._save_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"template_{ts}.png"
            filepath = os.path.join(self._save_dir, filename)
            region.save(filepath)
            self.captured.emit(os.path.abspath(filepath))
        except Exception as e:
            self.cancelled.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        w, h = self.width(), self.height()

        if self._bg:
            painter.drawPixmap(0, 0, w, h, self._bg)

        painter.fillRect(0, 0, w, h, QColor(0, 0, 0, 130))

        if self._start and self._end:
            from PyQt6.QtCore import QRect
            rect = QRect(self._start, self._end).normalized()

            # Show original pixels in selection
            if self._bg:
                painter.drawPixmap(rect, self._bg, rect)

            # Border
            painter.setPen(QPen(QColor("#FFFFFF"), 2))
            painter.drawRect(rect)

            # Corner marks
            painter.setPen(QPen(QColor("#FF9500"), 3))
            cl = 12
            for cx, cy, dx, dy in [
                (rect.left(), rect.top(), 1, 1),
                (rect.right(), rect.top(), -1, 1),
                (rect.left(), rect.bottom(), 1, -1),
                (rect.right(), rect.bottom(), -1, -1),
            ]:
                painter.drawLine(cx, cy, cx + dx * cl, cy)
                painter.drawLine(cx, cy, cx, cy + dy * cl)

            # Size label
            lbl = f"  {rect.width()} × {rect.height()}  "
            font = QFont("Consolas", 11, QFont.Weight.Bold)
            painter.setFont(font)
            fm = painter.fontMetrics()
            lw, lh = fm.horizontalAdvance(lbl) + 4, fm.height() + 4
            lx = rect.left()
            ly = rect.top() - lh - 4 if rect.top() > lh + 8 else rect.bottom() + 4
            painter.fillRect(lx, ly, lw, lh, QColor(30, 30, 46, 220))
            painter.setPen(QColor("#34C759"))
            painter.drawText(lx + 2, ly + lh - 4, lbl)

            # "Se guardará" hint
            hint = "  Suelta para guardar template  "
            hw = fm.horizontalAdvance(hint) + 4
            hx = max(0, rect.center().x() - hw // 2)
            hy = rect.center().y() - lh // 2
            painter.fillRect(hx, hy, hw, lh, QColor(30, 30, 46, 200))
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(hx + 2, hy + lh - 4, hint)

        else:
            font = QFont("Segoe UI", 14)
            painter.setFont(font)
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Arrastra para capturar el elemento\n\nESC para cancelar",
            )
