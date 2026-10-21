"""
Region selector dialog — lives inside the Studio window.
Uses QLabel + QRubberBand (Qt built-ins) so aspect ratio is always correct.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSizePolicy, QSpinBox, QRubberBand,
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QPoint, QSize
from PyQt6.QtGui import QPainter, QColor, QPen, QPixmap, QFont, QImage

import pyautogui
import numpy as np


# ── Screenshot helper ─────────────────────────────────────────────────────────

def _grab_pixmap(region) -> QPixmap:
    img  = pyautogui.screenshot(region=region).convert("RGB")
    arr  = np.array(img)
    h, w, _ = arr.shape
    data = arr.tobytes()
    return QPixmap.fromImage(
        QImage(data, w, h, w * 3, QImage.Format.Format_RGB888)
    )


# ── Canvas ────────────────────────────────────────────────────────────────────

class _Canvas(QLabel):
    """
    QLabel that shows a screenshot with optional grid overlay.
    Mouse drag creates a QRubberBand selection and emits screen coordinates.
    """
    selection_changed = pyqtSignal(int, int, int, int)   # x, y, w, h screen coords

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background:#1C1C1E;")
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(640, 360)

        self._full_px: QPixmap | None = None
        self._screen_origin = (0, 0)
        self._img_offset    = (0, 0)      # top-left of scaled image inside label
        self._img_size      = (1, 1)      # size of scaled image
        self._scale         = (1.0, 1.0)  # (scale_x, scale_y) img→screen

        self._drag_start: QPoint | None = None
        self._drag_end:   QPoint | None = None
        self._rubberband  = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self._last_rect: tuple | None = None

        self._show_grid  = False
        self._grid_cells = 20

    # ── Public ────────────────────────────────────────────────────────────────

    def load(self, pixmap: QPixmap, screen_origin: tuple):
        self._full_px       = pixmap
        self._screen_origin = screen_origin
        self._drag_start    = None
        self._last_rect     = None
        self._rubberband.hide()
        self._refresh_scaled()

    def set_grid(self, enabled: bool):
        self._show_grid = enabled
        self.update()

    def set_snap(self, enabled: bool):
        self._snap = enabled

    def set_grid_cells(self, n: int):
        self._grid_cells = max(5, n)
        self.update()

    def current_screen_rect(self):
        return self._last_rect

    # ── Internal ──────────────────────────────────────────────────────────────

    def _refresh_scaled(self):
        if not self._full_px:
            return
        scaled = self._full_px.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)
        # Offset of the image inside the label (centered)
        ox = (self.width()  - scaled.width())  // 2
        oy = (self.height() - scaled.height()) // 2
        self._img_offset = (ox, oy)
        self._img_size   = (scaled.width(), scaled.height())
        self._scale      = (
            self._full_px.width()  / max(scaled.width(),  1),
            self._full_px.height() / max(scaled.height(), 1),
        )

    def _widget_to_img(self, pos: QPoint) -> QPoint:
        """Convert widget coordinate to image-relative coordinate (clamped)."""
        ox, oy   = self._img_offset
        iw, ih   = self._img_size
        x = max(0, min(pos.x() - ox, iw - 1))
        y = max(0, min(pos.y() - oy, ih - 1))
        return QPoint(x, y)

    def _img_rect_to_screen(self, img_rect: QRect):
        sx_o, sy_o = self._screen_origin
        sx, sy   = self._scale
        return (
            int(img_rect.x()      * sx) + sx_o,
            int(img_rect.y()      * sy) + sy_o,
            int(img_rect.width()  * sx),
            int(img_rect.height() * sy),
        )

    # ── Events ────────────────────────────────────────────────────────────────

    def resizeEvent(self, event):
        self._refresh_scaled()
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._full_px:
            self._drag_start = event.pos()
            self._drag_end   = event.pos()
            self._rubberband.setGeometry(QRect(self._drag_start, QSize()))
            self._rubberband.show()

    def mouseMoveEvent(self, event):
        if self._drag_start:
            self._drag_end = event.pos()
            self._rubberband.setGeometry(
                QRect(self._drag_start, self._drag_end).normalized()
            )
            self._update_selection()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drag_start:
            self._drag_end = event.pos()
            self._rubberband.setGeometry(
                QRect(self._drag_start, self._drag_end).normalized()
            )
            self._update_selection()

    def _update_selection(self):
        if not self._drag_start or not self._drag_end:
            return
        drag_rect = QRect(self._drag_start, self._drag_end).normalized()
        p1 = self._widget_to_img(drag_rect.topLeft())
        p2 = self._widget_to_img(drag_rect.bottomRight())
        img_rect = QRect(p1, p2).normalized()
        if img_rect.width() < 2 or img_rect.height() < 2:
            return
        result = self._img_rect_to_screen(img_rect)
        self._last_rect = result
        self.selection_changed.emit(*result)

    # ── Paint (grid overlay only — image handled by QLabel) ──────────────────

    def paintEvent(self, event):
        super().paintEvent(event)   # draws the QLabel pixmap first
        if not self._show_grid or not self._full_px:
            return
        painter = QPainter(self)
        ox, oy = self._img_offset
        iw, ih = self._img_size
        cell_w = iw / self._grid_cells
        cell_h = ih / self._grid_cells
        pen = QPen(QColor(0, 122, 255, 90), 1)
        painter.setPen(pen)
        x = ox
        while x <= ox + iw:
            painter.drawLine(int(x), oy, int(x), oy + ih)
            x += cell_w
        y = oy
        while y <= oy + ih:
            painter.drawLine(ox, int(y), ox + iw, int(y))
            y += cell_h
        painter.end()


# ── Dialog ────────────────────────────────────────────────────────────────────

class RegionSelectorOverlay(QDialog):
    """
    Modal dialog — stays on screen 2, shows screenshot of screen 1.
    Emits region_selected(x, y, w, h) in absolute screen coordinates.
    """
    region_selected = pyqtSignal(int, int, int, int)
    cancelled       = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Seleccionar Región  ·  Pantalla 1")
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ── Top bar ──────────────────────────────────────────────────────────
        bar = QHBoxLayout()
        bar.setSpacing(6)

        hint = QLabel("Arrastra para seleccionar  ·  Enter = confirmar  ·  Esc = cancelar")
        hint.setStyleSheet("color:#6E6E73; font-size:11px;")
        bar.addWidget(hint)
        bar.addStretch()

        self._btn_grid = QPushButton("🔲 Malla")
        self._btn_grid.setCheckable(True)
        self._btn_grid.setFixedHeight(26)
        self._btn_grid.toggled.connect(self._on_grid_toggled)
        bar.addWidget(self._btn_grid)

        self._btn_snap = QPushButton("🧲 Snap")
        self._btn_snap.setCheckable(True)
        self._btn_snap.setFixedHeight(26)
        self._btn_snap.setEnabled(False)
        self._btn_snap.toggled.connect(lambda v: self._canvas.set_snap(v))
        bar.addWidget(self._btn_snap)

        self._spin = QSpinBox()
        self._spin.setRange(5, 50)
        self._spin.setValue(20)
        self._spin.setSuffix(" celdas")
        self._spin.setFixedWidth(95)
        self._spin.setEnabled(False)
        self._spin.valueChanged.connect(lambda v: self._canvas.set_grid_cells(v))
        bar.addWidget(self._spin)

        root.addLayout(bar)

        # ── Canvas ───────────────────────────────────────────────────────────
        self._canvas = _Canvas(self)
        self._canvas.selection_changed.connect(self._on_sel)
        root.addWidget(self._canvas)

        # ── Footer ───────────────────────────────────────────────────────────
        foot = QHBoxLayout()
        foot.setSpacing(6)

        self._coord = QLabel("Sin selección")
        self._coord.setStyleSheet(
            "color:#007AFF; font-size:12px; font-weight:600; font-family:Consolas;"
        )
        foot.addWidget(self._coord)
        foot.addStretch()

        btn_ok = QPushButton("✓  Confirmar")
        btn_ok.setFixedHeight(30)
        btn_ok.setStyleSheet(
            "background:#34C759;color:#fff;border:none;"
            "border-radius:7px;font-weight:600;padding:0 14px;"
        )
        btn_ok.clicked.connect(self._confirm)

        btn_cancel = QPushButton("✗  Cancelar")
        btn_cancel.setFixedHeight(30)
        btn_cancel.setStyleSheet(
            "background:#FF3B30;color:#fff;border:none;"
            "border-radius:7px;font-weight:600;padding:0 14px;"
        )
        btn_cancel.clicked.connect(self._cancel)

        foot.addWidget(btn_ok)
        foot.addWidget(btn_cancel)
        root.addLayout(foot)

    # ── Public ────────────────────────────────────────────────────────────────

    def start(self):
        from core.screen_utils import primary_rect, secondary_rect

        # Capture primary screen
        rx, ry, rw, rh = primary_rect()
        self._canvas.load(_grab_pixmap((rx, ry, rw, rh)), (rx, ry))
        self._coord.setText("Sin selección")

        # Position on secondary screen
        sec = secondary_rect()
        if sec:
            sx, sy, sw, sh = sec
            m = 20
            self.setGeometry(sx + m, sy + m, sw - m * 2, sh - m * 2)
        else:
            self.resize(1100, 620)

        self.exec()

    # ── Events ────────────────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        k = event.key()
        if k == Qt.Key.Key_Escape:
            self._cancel()
        elif k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._confirm()
        else:
            super().keyPressEvent(event)

    def _on_grid_toggled(self, on: bool):
        self._canvas.set_grid(on)
        self._btn_snap.setEnabled(on)
        self._spin.setEnabled(on)

    def _on_sel(self, x, y, w, h):
        self._coord.setText(f"x:{x}  y:{y}  w:{w}  h:{h}")

    def _confirm(self):
        r = self._canvas.current_screen_rect()
        if r and r[2] > 4 and r[3] > 4:
            self.accept()
            self.region_selected.emit(*r)
        else:
            self._cancel()

    def _cancel(self):
        self.reject()
        self.cancelled.emit()


# ── Compat alias ──────────────────────────────────────────────────────────────

def _grab_full_desktop() -> QPixmap:
    from core.screen_utils import combined_rect
    return _grab_pixmap(combined_rect())
