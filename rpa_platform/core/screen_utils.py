"""Screen geometry utilities — always call after QApplication exists."""

from __future__ import annotations
from typing import Tuple, List, Optional

ScreenRect = Tuple[int, int, int, int]   # (x, y, w, h)


def _qt_logical_rects() -> List[ScreenRect]:
    """Qt logical coordinates — for window positioning only."""
    from PyQt6.QtWidgets import QApplication
    return [
        (s.geometry().x(), s.geometry().y(),
         s.geometry().width(), s.geometry().height())
        for s in QApplication.screens()
    ]


def screen_rects() -> List[ScreenRect]:
    """Physical pixel coordinates — for pyautogui screenshot/click."""
    from PyQt6.QtWidgets import QApplication
    result = []
    for s in QApplication.screens():
        g   = s.geometry()
        dpr = s.devicePixelRatio()
        result.append((
            int(g.x()      * dpr),
            int(g.y()      * dpr),
            int(g.width()  * dpr),
            int(g.height() * dpr),
        ))
    return result


def screen_count() -> int:
    from PyQt6.QtWidgets import QApplication
    return len(QApplication.screens())


def primary_rect() -> ScreenRect:
    """Primary screen in physical pixels (pyautogui coordinate space)."""
    rects = screen_rects()
    return rects[0] if rects else (0, 0, 1920, 1080)


def secondary_rect() -> Optional[ScreenRect]:
    """Secondary screen in Qt logical coords (for Studio window positioning)."""
    rects = _qt_logical_rects()
    return rects[1] if len(rects) > 1 else None


def combined_rect() -> ScreenRect:
    """Bounding box of all screens in physical pixels (for full-desktop capture)."""
    rects = screen_rects()
    if not rects:
        return (0, 0, 1920, 1080)
    min_x = min(r[0] for r in rects)
    min_y = min(r[1] for r in rects)
    max_x = max(r[0] + r[2] for r in rects)
    max_y = max(r[1] + r[3] for r in rects)
    return (min_x, min_y, max_x - min_x, max_y - min_y)
