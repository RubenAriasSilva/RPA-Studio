"""RPA Orchestrator Bot — Conversational interface."""

import sys
import os
import glob
import subprocess
from datetime import datetime, timedelta
from typing import Optional, List, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "rpa_platform"))

import qtawesome as qta

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QSizePolicy, QFrame,
    QGraphicsDropShadowEffect, QSpacerItem, QInputDialog,
)
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QTimer, QSize, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QFont, QPalette, QIcon, QTextCursor

from core.workflow import Workflow
from core.runner import WorkflowRunner, RunnerState
from core import scheduler
from core.history import load_history, append_history
from ui import theme as T

WORKFLOWS_DIR = os.path.join(_HERE, "rpa_platform", "workflows")
STUDIO_PATH   = os.path.join(_HERE, "rpa_platform", "main.py")

# ── Palette (DESIGN_SYSTEM.md tokens, see rpa_platform/ui/theme.py) ───────────
BG      = T.BODY_BG_SOLID
SURFACE = T.NAV_BG
SURF2   = T.GLASS
BORDER  = T.BORDER
TXT     = T.TXT1
TXT2    = T.TXT2
TXT3    = T.TXT3
BLUE    = T.ACCENT
BLUE_D  = T.ACCENT_HOVER
BLUE_L  = T.ACCENT_SUBTLE
GREEN   = T.SUCCESS
GREEN_L = T.SUCCESS_BG
RED     = T.ERROR
RED_L   = T.ERROR_BG
ORANGE  = T.WARNING
BOT_BG  = T.GLASS_STRONG
USR_BG  = T.ACCENT_SUBTLE
USR_TXT = T.NAV_ACTIVE_TXT

ICON_SZ = QSize(15, 15)

STYLE = f"""
QWidget     {{ background: transparent; color: {TXT}; font-family: {T.FONT_FAMILY}; }}
QMainWindow {{ background: {T.BODY_BG}; }}
QWidget#root {{ background: {T.BODY_BG}; }}

/* Header (topbar) */
QWidget#header  {{ background: {SURFACE}; border-bottom: 1px solid {BORDER}; }}

/* Chat scroll */
QScrollArea#chatScroll  {{ background: transparent; border: none; }}
QWidget#chatCanvas      {{ background: transparent; }}

/* Bot bubble */
QLabel#botBubble {{
    background: {BOT_BG};
    color: {TXT};
    border: 1px solid {BORDER};
    border-radius: 4px 16px 16px 16px;
    padding: 10px 14px;
    font-size: 10pt;
    line-height: 1.5;
}}

/* User bubble */
QLabel#userBubble {{
    background: {USR_BG};
    color: #ffffff;
    border-radius: 16px 4px 16px 16px;
    padding: 10px 14px;
    font-size: 10pt;
}}

/* System message */
QLabel#sysMsg {{
    color: {TXT3}; font-size: 8pt;
    background: transparent;
}}

/* Progress line */
QLabel#progressLine {{
    color: {TXT2}; font-size: 9pt;
    background: {SURF2};
    border-left: 3px solid {BLUE};
    padding: 3px 10px;
    border-radius: 0 6px 6px 0;
}}

/* Inline button — .btn-secondary (glass) with accent icon */
QPushButton#inlineBtn {{
    background: {T.GLASS};
    color: {TXT2};
    border: 1px solid {T.GLASS_BORDER};
    border-radius: 10px;
    padding: 8px 18px;
    font-size: 10pt;
    font-weight: 600;
    text-align: left;
}}
QPushButton#inlineBtn:hover   {{ background: {T.GLASS_HOVER}; color: {TXT}; border-color: rgba(37,99,235,0.30); }}
QPushButton#inlineBtn:pressed {{ background: {BLUE_L}; color: {USR_TXT}; }}
QPushButton#inlineBtn:disabled {{ background: rgba(255,255,255,0.35); color: {T.TXT4}; border-color: {BORDER}; }}

/* Dialogs */
QDialog, QInputDialog {{ background: {T.GLASS_STRONG}; }}
QLineEdit {{
    background: {T.INPUT_BG}; border: 1px solid {T.INPUT_BORDER}; border-radius: 10px; padding: 6px 10px;
}}
QLineEdit:focus {{ border-color: {T.INPUT_FOCUS}; background: rgba(255,255,255,0.85); }}
QDialog QPushButton {{
    background: {T.GLASS}; color: {TXT2}; border: 1px solid {T.INPUT_BORDER};
    border-radius: 10px; padding: 6px 16px; font-weight: 600;
}}
QDialog QPushButton:hover {{ background: {T.GLASS_HOVER}; color: {TXT}; }}

/* Scrollbar */
QScrollBar:vertical   {{ background: transparent; width: 5px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: {T.SCROLLBAR}; border-radius: 2px; min-height: 24px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QStatusBar {{ background: {SURFACE}; color: {TXT2}; border-top: 1px solid {BORDER}; font-size: 9pt; }}
"""


# ── Runner signals ─────────────────────────────────────────────────────────────

class RunnerSignals(QObject):
    log      = pyqtSignal(str, str)
    finished = pyqtSignal(str)


# ── History entry ──────────────────────────────────────────────────────────────

class HistoryEntry:
    def __init__(self, name: str, state: str, elapsed: str, ts: str):
        self.name    = name
        self.state   = state
        self.elapsed = elapsed
        self.ts      = ts


# ── Chat widgets ──────────────────────────────────────────────────────────────

def _shadow(r=12, dy=3, a=20):
    fx = QGraphicsDropShadowEffect()
    fx.setBlurRadius(r); fx.setXOffset(0); fx.setYOffset(dy)
    fx.setColor(QColor(80, 110, 180, a))  # glass-shadow tint
    return fx


def _ico(name: str, color: str = TXT2) -> QIcon:
    return qta.icon(name, color=color, options=[{"scale_factor": 1.0}])


def _make_user_msg(text: str) -> QWidget:
    """Right-aligned bubble (user message)."""
    row = QWidget()
    row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
    lay = QHBoxLayout(row)
    lay.setContentsMargins(80, 4, 16, 4)
    lay.addStretch()

    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
    # Inline stylesheet — overrides global QWidget rule reliably
    lbl.setStyleSheet(
        f"background-color:{USR_BG}; color:{USR_TXT}; font-weight:600;"
        f"border:1px solid rgba(37,99,235,0.25); border-radius:16px;"
        f"padding:10px 16px; font-size:10pt;"
    )
    lbl.setGraphicsEffect(_shadow(8, 2, 20))
    lay.addWidget(lbl)
    return row


def _make_sys_msg(text: str) -> QWidget:
    """Centered gray system / timestamp message."""
    row = QWidget()
    lay = QHBoxLayout(row)
    lay.setContentsMargins(0, 6, 0, 6)
    lay.addStretch()
    lbl = QLabel(text)
    lbl.setObjectName("sysMsg")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(lbl)
    lay.addStretch()
    return row


class BotMessage(QWidget):
    """Left-aligned white bubble with optional inline keyboard buttons."""
    action = pyqtSignal(str, str)  # action_id, label

    def __init__(self, text: str,
                 buttons: Optional[List[Tuple[str, str, str]]] = None,
                 parent=None):
        """
        text: plain or HTML text
        buttons: list of (icon_name, label, action_id)
        """
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 4, 80, 4)
        outer.setSpacing(6)

        # Avatar + bubble row
        row = QHBoxLayout()
        row.setSpacing(10)
        row.setAlignment(Qt.AlignmentFlag.AlignTop)

        av = QLabel()
        av.setPixmap(qta.icon("mdi.robot", color=BLUE).pixmap(20, 20))
        av.setFixedSize(34, 34)
        av.setAlignment(Qt.AlignmentFlag.AlignCenter)
        av.setStyleSheet(
            f"background:{BLUE_L}; border-radius:17px; border:1px solid {T.GLASS_BORDER};"
        )
        row.addWidget(av)
        row.setAlignment(av, Qt.AlignmentFlag.AlignTop)

        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setTextFormat(Qt.TextFormat.RichText)
        bubble.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        bubble.setStyleSheet(
            f"background-color:{BOT_BG}; color:{TXT};"
            f"border:1px solid {T.BORDER_STRONG}; border-radius:16px;"
            f"padding:10px 16px; font-size:10pt;"
        )
        bubble.setGraphicsEffect(_shadow(24, 6, 22))
        row.addWidget(bubble)
        outer.addLayout(row)

        # Inline keyboard
        if buttons:
            kb = QWidget()
            kb_lay = QVBoxLayout(kb)
            kb_lay.setContentsMargins(44, 0, 0, 0)
            kb_lay.setSpacing(5)
            self._btns: List[QPushButton] = []
            for icon_name, label, action_id in buttons:
                b = QPushButton(f"  {label}")
                b.setObjectName("inlineBtn")
                b.setIcon(_ico(icon_name, BLUE))
                b.setIconSize(ICON_SZ)
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
                b.setMinimumWidth(220)
                b.clicked.connect(lambda _, aid=action_id, lbl=label: self._on_click(aid, lbl))
                kb_lay.addWidget(b)
                self._btns.append(b)
            outer.addWidget(kb)

    def _on_click(self, action_id: str, label: str):
        self.disable_buttons()
        self.action.emit(action_id, label)

    def disable_buttons(self):
        if hasattr(self, "_btns"):
            for b in self._btns:
                b.setEnabled(False)


class ProgressBlock(QWidget):
    """Live-updating progress lines during execution."""
    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(56, 2, 60, 2)
        outer.setSpacing(2)
        self._lay = outer
        self._lines: List[QLabel] = []

    def add_line(self, text: str, level: str = "info"):
        colors = {"info": TXT2, "success": GREEN, "warning": ORANGE, "error": RED}
        icons  = {"info": "·", "success": "✓", "warning": "!", "error": "✗"}
        color  = colors.get(level, TXT2)
        icon   = icons.get(level, "·")
        ts     = datetime.now().strftime("%H:%M:%S")
        lbl    = QLabel(f'<span style="color:{TXT3};">[{ts}]</span> '
                        f'<span style="color:{color}; font-weight:600;">{icon}</span> '
                        f'<span style="color:{color};">{text}</span>')
        lbl.setObjectName("progressLine")
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setWordWrap(True)
        self._lay.addWidget(lbl)
        self._lines.append(lbl)


# ── Chat canvas ───────────────────────────────────────────────────────────────

class ChatArea(QScrollArea):
    """Scrollable chat area. Emits action(action_id, label) on button presses."""
    action = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("chatScroll")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._canvas = QWidget()
        self._canvas.setObjectName("chatCanvas")
        self._canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._lay = QVBoxLayout(self._canvas)
        self._lay.setContentsMargins(8, 16, 8, 24)
        self._lay.setSpacing(6)
        self._lay.addStretch()
        self.setWidget(self._canvas)

        self._progress: Optional[ProgressBlock] = None

    # ── public API ────────────────────────────────────────────────────────────

    def bot(self, text: str,
            buttons: Optional[List[Tuple[str, str, str]]] = None) -> BotMessage:
        msg = BotMessage(text, buttons)
        msg.action.connect(self.action)
        self._insert(msg)
        return msg

    def user(self, text: str):
        self._insert(_make_user_msg(text))

    def sys(self, text: str):
        self._insert(_make_sys_msg(text))

    def start_progress(self) -> ProgressBlock:
        self._progress = ProgressBlock()
        self._insert(self._progress)
        return self._progress

    def stop_progress(self):
        self._progress = None

    def log_line(self, text: str, level: str = "info"):
        if self._progress:
            self._progress.add_line(text, level)
            self._scroll_bottom()

    def clear(self):
        while self._lay.count() > 1:
            item = self._lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._progress = None

    # ── internal ──────────────────────────────────────────────────────────────

    def _insert(self, widget: QWidget):
        self._lay.insertWidget(self._lay.count() - 1, widget)
        QTimer.singleShot(50, self._scroll_bottom)

    def _scroll_bottom(self):
        sb = self.verticalScrollBar()
        sb.setValue(sb.maximum())


# ── Bot conversation engine ───────────────────────────────────────────────────

class OrchestratorBot(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("RPA Orchestrator")
        self.setWindowIcon(qta.icon("mdi.robot", color=BLUE))
        self.resize(920, 720)

        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor(BG))
        self.setPalette(pal)

        self._runner   = WorkflowRunner()
        self._signals  = RunnerSignals()
        self._history: List[HistoryEntry] = []
        self._pending_robot: Optional[str] = None  # path of robot pending action
        self._pending_sched: Optional[str] = None  # path being scheduled
        self._sched_timer:   Optional[QTimer] = None
        self._sched_info:    Optional[str] = None
        self._start_time:    Optional[datetime] = None
        self._elapsed_timer  = QTimer(self)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)

        self._setup_runner()
        self._build_ui()
        self.setStyleSheet(STYLE)
        QTimer.singleShot(300, self._greet)

    # ── Runner ────────────────────────────────────────────────────────────────

    def _setup_runner(self):
        sig = self._signals
        def _on_log(msg, level): sig.log.emit(msg, level)
        def _on_done(_):         sig.finished.emit(self._runner.state.value)
        self._runner.on_log      = _on_log
        self._runner.on_finished = _on_done
        sig.log.connect(self._on_log)
        sig.finished.connect(self._on_finished)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        root.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCentralWidget(root)
        vlay = QVBoxLayout(root)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(0)

        vlay.addWidget(self._build_header())

        self._chat = ChatArea()
        self._chat.action.connect(self._on_action)
        vlay.addWidget(self._chat)

        self.statusBar().showMessage("Listo")

    def _build_header(self) -> QWidget:
        h = QWidget()
        h.setObjectName("header")
        h.setFixedHeight(58)
        row = QHBoxLayout(h)
        row.setContentsMargins(16, 0, 16, 0)
        row.setSpacing(10)

        av = QLabel()
        av.setPixmap(qta.icon("mdi.robot", color=BLUE).pixmap(24, 24))
        av.setFixedSize(38, 38)
        av.setAlignment(Qt.AlignmentFlag.AlignCenter)
        av.setStyleSheet(f"background:{BLUE_L}; border-radius:19px;")
        row.addWidget(av)

        col = QWidget()
        cl  = QVBoxLayout(col)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(1)
        t = QLabel("RPA Assistant")
        t.setStyleSheet(f"color:{TXT}; font-weight:700; font-size:12pt; letter-spacing:-0.2px;")
        s = QLabel("Bot de automatizacion de procesos")
        s.setStyleSheet(f"color:{TXT3}; font-size:8pt;")
        cl.addWidget(t); cl.addWidget(s)
        row.addWidget(col)
        row.addStretch()

        self._hdr_status = QLabel()
        self._set_status_badge(False)
        row.addWidget(self._hdr_status, alignment=Qt.AlignmentFlag.AlignVCenter)

        return h

    def _set_status_badge(self, running: bool):
        if running:
            self._hdr_status.setText("● Ejecutando")
            self._hdr_status.setStyleSheet(T.badge_qss(T.INFO, T.INFO_BG))
        else:
            self._hdr_status.setText("● En línea")
            self._hdr_status.setStyleSheet(T.badge_qss(GREEN, GREEN_L))

    # ── Greeting / main menu ──────────────────────────────────────────────────

    def _greet(self):
        self._chat.sys(datetime.now().strftime("%A, %d de %B · %H:%M"))
        self._chat.bot(
            "Hola! Soy tu asistente de automatizacion RPA 🤖<br>"
            f"<span style='color:{TXT2}; font-size:9pt;'>¿Que deseas hacer hoy?</span>",
            buttons=[
                ("fa5s.play-circle",    "Ejecutar un proceso",          "menu_run"),
                ("fa5s.edit",           "Editar un proceso",            "menu_edit"),
                ("fa5s.plus-circle",    "Crear nuevo proceso",          "menu_create"),
                ("fa5s.clock",          "Programar ejecucion",         "menu_schedule"),
                ("fa5s.calendar-check", "Ver programaciones",          "sched_list"),
                ("fa5s.history",        "Ver historial",                "menu_history"),
                ("fa5s.cog",            "Configuracion",               "menu_config"),
            ],
        )

    def _main_menu(self):
        self._chat.bot(
            "¿Que mas deseas hacer?",
            buttons=[
                ("fa5s.play-circle",    "Ejecutar un proceso",          "menu_run"),
                ("fa5s.edit",           "Editar un proceso",            "menu_edit"),
                ("fa5s.plus-circle",    "Crear nuevo proceso",          "menu_create"),
                ("fa5s.clock",          "Programar ejecucion",         "menu_schedule"),
                ("fa5s.calendar-check", "Ver programaciones",          "sched_list"),
                ("fa5s.history",        "Ver historial",                "menu_history"),
                ("fa5s.cog",            "Configuracion",               "menu_config"),
            ],
        )

    # ── Action router ─────────────────────────────────────────────────────────

    def _on_action(self, action_id: str, label: str):
        self._chat.user(label)

        # Main menu
        if action_id == "menu_run":       self._ask_select_run()
        elif action_id == "menu_edit":    self._ask_select_edit()
        elif action_id == "menu_create":  self._do_create()
        elif action_id == "menu_schedule":self._ask_select_schedule()
        elif action_id == "menu_history": self._show_history()
        elif action_id == "menu_config":  self._show_config()
        elif action_id == "menu_main":    self._main_menu()

        # Run flow
        elif action_id.startswith("run_select:"):
            path = action_id.split(":", 1)[1]
            self._confirm_run(path)
        elif action_id.startswith("run_confirm:"):
            path = action_id.split(":", 1)[1]
            self._do_run(path)

        # Edit flow
        elif action_id.startswith("edit_select:"):
            path = action_id.split(":", 1)[1]
            self._do_edit(path)

        # Schedule flow
        elif action_id.startswith("sched_select:"):
            path = action_id.split(":", 1)[1]
            self._ask_schedule_time(path)
        elif action_id.startswith("sched_time:"):
            # paths contain "C:\", so split from the right
            path, mins = action_id[len("sched_time:"):].rsplit(":", 1)
            self._do_schedule(path, int(mins))
        elif action_id == "sched_cancel":
            self._cancel_schedule()

        # Fixed-time schedule (Windows Task Scheduler) — "|" separated, paths never contain it
        elif action_id.startswith("sched_clock|"):
            self._ask_clock_time(action_id.split("|")[1])
        elif action_id.startswith("sched_other|"):
            self._ask_custom_time(action_id.split("|")[1])
        elif action_id.startswith("sched_at|"):
            _, path, hhmm = action_id.split("|")
            self._ask_repeat(path, hhmm)
        elif action_id.startswith("sched_repeat|"):
            _, path, hhmm, mode = action_id.split("|")
            self._do_schedule_clock(path, hhmm, mode)
        elif action_id == "sched_list":
            self._show_schedules()
        elif action_id.startswith("sched_del|"):
            self._delete_schedule(action_id.split("|", 1)[1])

        elif action_id == "config_open_folder":
            os.makedirs(WORKFLOWS_DIR, exist_ok=True)
            os.startfile(WORKFLOWS_DIR)
            QTimer.singleShot(600, self._main_menu)

        # Stop
        elif action_id == "stop_run":
            self._runner.stop()
            self._chat.bot("Enviando senal de parada...")

        # Run again
        elif action_id.startswith("run_again:"):
            path = action_id.split(":", 1)[1]
            self._do_run(path)

        else:
            self._main_menu()

    # ── FLOW: Execute ─────────────────────────────────────────────────────────

    def _ask_select_run(self):
        robots = self._load_robots()
        if not robots:
            self._chat.bot(
                "No encontre ningun proceso en la carpeta de workflows.<br>"
                f"<span style='color:{TXT3}; font-size:9pt;'>Crea uno primero.</span>",
                buttons=[
                    ("fa5s.plus-circle", "Crear nuevo proceso", "menu_create"),
                    ("fa5s.home",        "Menu principal",      "menu_main"),
                ],
            )
            return
        btns = []
        for path, name, steps in robots:
            btns.append(("fa5s.robot", f"{name}  ·  {steps} pasos", f"run_select:{path}"))
        btns.append(("fa5s.arrow-left", "Volver", "menu_main"))
        self._chat.bot("¿Que proceso deseas ejecutar?", buttons=btns)

    def _confirm_run(self, path: str):
        try:
            wf    = Workflow.load(path)
            name  = wf.name
            n     = len(wf.steps)
            act   = sum(1 for s in wf.steps if wf.is_step_active(s))
        except Exception as e:
            self._chat.bot(f"Error al cargar el proceso: {e}")
            return
        self._chat.bot(
            f"¿Confirmas ejecutar <b>{name}</b>?<br>"
            f"<span style='color:{TXT2}; font-size:9pt;'>"
            f"📋 {n} pasos &nbsp;·&nbsp; {act} activos</span>",
            buttons=[
                ("fa5s.play",       "Si, ejecutar", f"run_confirm:{path}"),
                ("fa5s.times",      "Cancelar",     "menu_run"),
            ],
        )

    def _do_run(self, path: str):
        if self._runner.is_running:
            self._chat.bot("Ya hay un proceso en ejecucion. Detienelo primero.")
            return
        try:
            wf = Workflow.load(path)
        except Exception as e:
            self._chat.bot(f"No se pudo cargar el proceso: {e}")
            return

        self._pending_robot = path
        self._start_time    = datetime.now()
        self._elapsed_timer.start(1000)

        self._chat.bot(
            f"▶ Ejecutando <b>{wf.name}</b>...<br>"
            f"<span style='color:{TXT3}; font-size:8pt;'>Iniciado a las "
            f"{datetime.now().strftime('%H:%M:%S')}</span>",
            buttons=[("fa5s.stop-circle", "Detener ejecucion", "stop_run")],
        )
        self._prog = self._chat.start_progress()

        self._set_status_badge(True)
        self.statusBar().showMessage(f"Ejecutando: {wf.name}")

        # Ocultar ventana tras 800 ms para que SAP tome el foco
        QTimer.singleShot(800, self.hide)
        QTimer.singleShot(800, lambda: self._runner.run(wf))

    # ── FLOW: Edit ────────────────────────────────────────────────────────────

    def _ask_select_edit(self):
        robots = self._load_robots()
        if not robots:
            self._chat.bot(
                "No hay procesos para editar.",
                buttons=[
                    ("fa5s.plus-circle", "Crear nuevo proceso", "menu_create"),
                    ("fa5s.home",        "Menu principal",      "menu_main"),
                ],
            )
            return
        btns = []
        for path, name, steps in robots:
            btns.append(("fa5s.edit", f"{name}  ·  {steps} pasos", f"edit_select:{path}"))
        btns.append(("fa5s.arrow-left", "Volver", "menu_main"))
        self._chat.bot("¿Que proceso deseas editar?", buttons=btns)

    def _do_edit(self, path: str):
        self._chat.bot(
            f"Abriendo el editor para <b>{os.path.basename(path)}</b>...<br>"
            f"<span style='color:{TXT3}; font-size:9pt;'>El estudio RPA se abrira en una ventana separada.</span>",
        )
        QTimer.singleShot(400, lambda: self._open_studio(path))
        QTimer.singleShot(1200, self._main_menu)

    def _open_studio(self, path: Optional[str] = None):
        args = [sys.executable, STUDIO_PATH]
        if path:
            args += ["--open", path]
        try:
            subprocess.Popen(args, cwd=os.path.join(_HERE, "rpa_platform"))
        except Exception as e:
            self._chat.bot(f"Error al abrir el estudio: {e}")

    # ── FLOW: Create ──────────────────────────────────────────────────────────

    def _do_create(self):
        self._chat.bot(
            "Abriendo el estudio RPA para crear un nuevo proceso...<br>"
            f"<span style='color:{TXT3}; font-size:9pt;'>Una vez guardado, aparecera aqui automaticamente.</span>",
        )
        QTimer.singleShot(400, lambda: self._open_studio(None))
        QTimer.singleShot(1200, self._main_menu)

    # ── FLOW: Schedule ────────────────────────────────────────────────────────

    def _ask_select_schedule(self):
        robots = self._load_robots()
        if not robots:
            self._chat.bot(
                "No hay procesos disponibles para programar.",
                buttons=[("fa5s.home", "Menu principal", "menu_main")],
            )
            return
        btns = []
        for path, name, steps in robots:
            btns.append(("fa5s.robot", f"{name}  ·  {steps} pasos", f"sched_select:{path}"))
        btns.append(("fa5s.arrow-left", "Volver", "menu_main"))
        self._chat.bot("¿Que proceso deseas programar?", buttons=btns)

    def _ask_schedule_time(self, path: str):
        try:
            wf   = Workflow.load(path)
            name = wf.name
        except Exception:
            name = os.path.basename(path)
        self._chat.bot(
            f"¿Cuándo deseas ejecutar <b>{name}</b>?<br>"
            f"<span style='color:{TXT3}; font-size:9pt;'>"
            f"«A una hora específica» funciona aunque el Orchestrator y RPA Studio estén cerrados. "
            f"Las opciones en minutos requieren dejar el Orchestrator abierto.</span>",
            buttons=[
                ("fa5s.calendar-alt", "A una hora específica", f"sched_clock|{path}"),
                ("fa5s.clock", "En 5 minutos",   f"sched_time:{path}:5"),
                ("fa5s.clock", "En 15 minutos",  f"sched_time:{path}:15"),
                ("fa5s.clock", "En 30 minutos",  f"sched_time:{path}:30"),
                ("fa5s.clock", "En 1 hora",      f"sched_time:{path}:60"),
                ("fa5s.times", "Cancelar",        "menu_main"),
            ],
        )

    def _do_schedule(self, path: str, minutes: int):
        if self._sched_timer and self._sched_timer.isActive():
            self._sched_timer.stop()

        try:
            wf   = Workflow.load(path)
            name = wf.name
        except Exception:
            name = os.path.basename(path)

        run_at = datetime.now() + timedelta(minutes=minutes)
        self._sched_info = name

        self._sched_timer = QTimer(self)
        self._sched_timer.setSingleShot(True)
        self._sched_timer.timeout.connect(lambda: self._fire_scheduled(path, name))
        self._sched_timer.start(minutes * 60 * 1000)

        self._chat.bot(
            f"✓ <b>{name}</b> programado para ejecutarse en "
            f"<b>{minutes} minutos</b><br>"
            f"<span style='color:{TXT3}; font-size:9pt;'>"
            f"Hora de ejecucion: {run_at.strftime('%H:%M:%S')}</span>",
            buttons=[
                ("fa5s.ban",  "Cancelar programacion", "sched_cancel"),
                ("fa5s.home", "Menu principal",          "menu_main"),
            ],
        )

    def _fire_scheduled(self, path: str, name: str):
        self._chat.sys(f"⏰ Ejecucion programada de '{name}' iniciando...")
        self._do_run(path)

    def _cancel_schedule(self):
        if self._sched_timer:
            self._sched_timer.stop()
            self._sched_timer = None
        name = self._sched_info or "proceso"
        self._chat.bot(f"Programacion de <b>{name}</b> cancelada.")
        QTimer.singleShot(600, self._main_menu)

    # ── FLOW: Schedule at a fixed time (Windows Task Scheduler) ──────────────

    _PRESET_TIMES = ("06:00", "07:00", "08:00", "09:00", "12:00", "18:00")

    def _wf_name(self, path: str) -> str:
        try:
            return Workflow.load(path).name
        except Exception:
            return os.path.basename(path).replace(".rpa.json", "")

    def _ask_clock_time(self, path: str):
        btns = [("fa5s.clock", t, f"sched_at|{path}|{t}") for t in self._PRESET_TIMES]
        btns.append(("fa5s.keyboard", "Otra hora…", f"sched_other|{path}"))
        btns.append(("fa5s.times", "Cancelar", "menu_main"))
        self._chat.bot(f"¿A qué hora deseas ejecutar <b>{self._wf_name(path)}</b>?", buttons=btns)

    def _ask_custom_time(self, path: str):
        text, ok = QInputDialog.getText(self, "Hora de ejecución", "Hora (HH:MM, formato 24 h):", text="07:30")
        hhmm = self._parse_hhmm(text) if ok else None
        if not ok:
            self._main_menu()
            return
        if not hhmm:
            self._chat.bot(
                f"«{text}» no es una hora válida. Usa el formato HH:MM, por ejemplo 07:30.",
                buttons=[
                    ("fa5s.keyboard", "Intentar de nuevo", f"sched_other|{path}"),
                    ("fa5s.home",     "Menu principal",     "menu_main"),
                ],
            )
            return
        self._chat.user(hhmm)
        self._ask_repeat(path, hhmm)

    @staticmethod
    def _parse_hhmm(text: str) -> Optional[str]:
        try:
            hh, mm = text.strip().replace(".", ":").split(":")
            hh, mm = int(hh), int(mm)
        except ValueError:
            return None
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            return f"{hh:02d}:{mm:02d}"
        return None

    def _ask_repeat(self, path: str, hhmm: str):
        self._chat.bot(
            f"¿Con qué frecuencia ejecutar <b>{self._wf_name(path)}</b> a las <b>{hhmm}</b>?",
            buttons=[
                ("fa5s.dot-circle",     scheduler.MODES["once"],     f"sched_repeat|{path}|{hhmm}|once"),
                ("fa5s.redo",           scheduler.MODES["daily"],    f"sched_repeat|{path}|{hhmm}|daily"),
                ("fa5s.briefcase",      scheduler.MODES["weekdays"], f"sched_repeat|{path}|{hhmm}|weekdays"),
                ("fa5s.times",          "Cancelar",                  "menu_main"),
            ],
        )

    def _do_schedule_clock(self, path: str, hhmm: str, mode: str):
        name = self._wf_name(path)
        hh, mm = (int(x) for x in hhmm.split(":"))
        try:
            task_name, first_run = scheduler.create_task(path, name, hh, mm, mode)
        except Exception as e:
            self._chat.bot(
                f'<span style="color:{RED}; font-weight:600;">No se pudo crear la programación.</span><br>'
                f"<span style='color:{TXT3}; font-size:9pt;'>{e}</span>",
                buttons=[("fa5s.home", "Menu principal", "menu_main")],
            )
            return
        self._chat.bot(
            f"✓ <b>{name}</b> programado · {T.badge(scheduler.MODES[mode], T.INFO, T.INFO_BG)}<br>"
            f"<span style='color:{TXT2}; font-size:9pt;'>Próxima ejecución: "
            f"<b>{first_run.strftime('%A %d/%m/%Y a las %H:%M')}</b></span><br>"
            f"<span style='color:{TXT3}; font-size:8pt;'>Se ejecutará aunque el Orchestrator y RPA Studio "
            f"estén cerrados. El equipo debe estar encendido y con la sesión iniciada y desbloqueada.</span>",
            buttons=[
                ("fa5s.calendar-check", "Ver programaciones", "sched_list"),
                ("fa5s.home",           "Menu principal",     "menu_main"),
            ],
        )

    def _show_schedules(self):
        tasks = scheduler.list_tasks()
        if not tasks:
            self._chat.bot(
                "No hay ejecuciones programadas a hora fija.",
                buttons=[
                    ("fa5s.clock", "Programar ejecucion", "menu_schedule"),
                    ("fa5s.home",  "Menu principal",      "menu_main"),
                ],
            )
            return
        rows = "".join(
            f'<tr><td style="color:{TXT}; padding:3px 8px 3px 0;"><b>{t["name"]}</b></td>'
            f'<td style="color:{TXT3}; font-size:8pt; padding:3px 8px;">{t["next_run"]}</td>'
            f'<td style="padding:3px 0;">{T.badge(t["status"], T.MUTED, T.MUTED_BG)}</td></tr>'
            for t in tasks
        )
        btns = [("fa5s.trash-alt", f"Eliminar «{t['name']}»", f"sched_del|{t['name']}") for t in tasks]
        btns.append(("fa5s.home", "Menu principal", "menu_main"))
        self._chat.bot(
            f"<b>Ejecuciones programadas</b><br><br><table cellspacing='0' cellpadding='0'>{rows}</table>",
            buttons=btns,
        )

    def _delete_schedule(self, task_name: str):
        try:
            scheduler.delete_task(task_name)
            self._chat.bot(f"Programación <b>{task_name}</b> eliminada.")
        except Exception as e:
            self._chat.bot(f"No se pudo eliminar <b>{task_name}</b>: {e}")
        QTimer.singleShot(400, self._show_schedules)

    # ── FLOW: History ─────────────────────────────────────────────────────────

    def _show_history(self):
        history = load_history()
        if not history:
            self._chat.bot(
                "Aun no hay ejecuciones registradas.",
                buttons=[("fa5s.home", "Menu principal", "menu_main")],
            )
            return

        rows = ""
        badges = {"success": ("Completado", T.SUCCESS, T.SUCCESS_BG),
                  "failed":  ("Error",      T.ERROR,   T.ERROR_BG),
                  "stopped": ("Detenido",   T.WARNING, T.WARNING_BG)}
        for h in reversed(history[-10:]):
            label, fg, bg = badges.get(h.get("state"), ("—", T.MUTED, T.MUTED_BG))
            origin = h.get("origin", "manual")
            origin_badge = T.badge("Programado", T.INFO, T.INFO_BG) if origin == "programado" else ""
            rows += (
                f'<tr>'
                f'<td style="padding:3px 8px 3px 0;">{T.badge(label, fg, bg)}</td>'
                f'<td style="color:{TXT}; padding:3px 4px;">{h.get("name", "")} {origin_badge}</td>'
                f'<td style="color:{TXT3}; font-size:8pt; padding:3px 8px;">{h.get("elapsed", "")}</td>'
                f'<td style="color:{TXT3}; font-size:8pt; padding:3px 4px;">{h.get("ts", "")}</td>'
                f'</tr>'
            )
        html = (
            f"<b>Ultimas {min(len(history), 10)} ejecuciones:</b><br><br>"
            f'<table cellspacing="0" cellpadding="0">{rows}</table>'
        )
        self._chat.bot(
            html,
            buttons=[("fa5s.home", "Menu principal", "menu_main")],
        )

    # ── FLOW: Config ──────────────────────────────────────────────────────────

    def _show_config(self):
        api_set = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
        api_status = (
            f'<span style="color:{GREEN};">● Configurada</span>'
            if api_set else
            f'<span style="color:{RED};">● No configurada</span>'
        )
        wf_count = len(glob.glob(os.path.join(WORKFLOWS_DIR, "*.rpa.json")))
        self._chat.bot(
            f"<b>Configuracion del sistema</b><br><br>"
            f"🔑 API Key de Claude: {api_status}<br>"
            f"📁 Carpeta de workflows: <code style='font-size:8pt;'>{WORKFLOWS_DIR}</code><br>"
            f"🤖 Procesos disponibles: <b>{wf_count}</b>",
            buttons=[
                ("fa5s.folder-open", "Abrir carpeta de workflows", "config_open_folder"),
                ("fa5s.home",        "Menu principal",             "menu_main"),
            ],
        )

    # ── Runner callbacks ──────────────────────────────────────────────────────

    def _on_log(self, msg: str, level: str):
        self._chat.log_line(msg, level)
        self.statusBar().showMessage(msg[:100])

    def _on_finished(self, state: str):
        self._elapsed_timer.stop()
        self._chat.stop_progress()

        path  = self._pending_robot or ""
        name  = ""
        try:
            wf   = Workflow.load(path)
            name = wf.name
        except Exception:
            name = os.path.basename(path)

        elapsed = ""
        if self._start_time:
            sec     = int((datetime.now() - self._start_time).total_seconds())
            h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
            elapsed = f"{h:02d}:{m:02d}:{s:02d}"

        ts = datetime.now().strftime("%H:%M:%S")

        if state == "finished":
            result_state = "success"
            result_icon  = "✓"
            result_color = GREEN
            result_txt   = "Proceso completado exitosamente"
        elif state == "stopped":
            result_state = "stopped"
            result_icon  = "■"
            result_color = ORANGE
            result_txt   = "Proceso detenido por el usuario"
        else:
            result_state = "failed"
            result_icon  = "✗"
            result_color = RED
            result_txt   = "El proceso termino con errores"

        self._history.append(HistoryEntry(name, result_state, elapsed, ts))
        try:
            append_history({
                "name": name, "state": result_state, "elapsed": elapsed,
                "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "origin": "manual",
            })
        except OSError:
            pass

        # Volver a mostrar la ventana y traerla al frente
        self.show()
        self.raise_()
        self.activateWindow()

        self._chat.bot(
            f'<span style="color:{result_color}; font-weight:700; font-size:12pt;">'
            f'{result_icon} {result_txt}</span><br>'
            f'<span style="color:{TXT3}; font-size:9pt;">'
            f'Proceso: <b>{name}</b> &nbsp;·&nbsp; '
            f'Duracion: <b>{elapsed}</b> &nbsp;·&nbsp; {ts}</span>',
            buttons=[
                ("fa5s.redo",   "Ejecutar de nuevo",  f"run_again:{path}"),
                ("fa5s.home",   "Menu principal",      "menu_main"),
            ],
        )

        self._set_status_badge(False)
        self.statusBar().showMessage(
            f"Listo  ·  Ultima ejecucion: {name}  ·  {result_txt}"
        )
        self._pending_robot = None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _load_robots(self) -> List[Tuple[str, str, int]]:
        """Returns list of (path, name, step_count)."""
        os.makedirs(WORKFLOWS_DIR, exist_ok=True)
        result = []
        for path in sorted(glob.glob(os.path.join(WORKFLOWS_DIR, "*.rpa.json"))):
            try:
                wf   = Workflow.load(path)
                name = wf.name if wf.name not in ("Nuevo Workflow", "") else os.path.basename(path).replace(".rpa.json", "")
                result.append((path, name, len(wf.steps)))
            except Exception:
                pass
        return result

    def _tick_elapsed(self):
        if not self._start_time:
            return
        sec = int((datetime.now() - self._start_time).total_seconds())
        h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
        self.statusBar().showMessage(
            f"Ejecutando... {h:02d}:{m:02d}:{s:02d}"
        )


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("RPA Orchestrator")
    f = QFont("Segoe UI Variable Display", 10)
    f.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(f)
    win = OrchestratorBot()
    win.show()
    sys.exit(app.exec())
