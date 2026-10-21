import os
import sys
import qtawesome as qta
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QToolBar, QStatusBar, QFileDialog,
    QInputDialog, QMessageBox, QFrame,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QTimer, QSize
from PyQt6.QtGui import QAction, QKeySequence, QFont, QIcon

from core.workflow import Workflow
from core.runner import WorkflowRunner, RunnerState
from .workflow_editor import WorkflowEditor
from .properties_panel import PropertiesPanel
from .log_panel import LogPanel
from .action_palette import ActionPalette
from .style import LIGHT_THEME
from .theme import ACCENT, TXT1, badge_qss, INFO, INFO_BG, SUCCESS, SUCCESS_BG


class RunnerSignals(QObject):
    log = pyqtSignal(str, str)
    step_start = pyqtSignal(int, object)
    step_complete = pyqtSignal(int, object, object)
    finished = pyqtSignal(dict)
    error = pyqtSignal(int, object, str)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._workflow = Workflow(name="Nuevo Workflow")
        self._current_file: str = ""
        self._modified = False
        self._runner = WorkflowRunner()
        self._signals = RunnerSignals()
        self._setup_runner_callbacks()
        self._setup_ui()
        self._setup_menu()
        self._setup_toolbar()
        self._connect_signals()
        self._update_title()
        self.setStyleSheet(LIGHT_THEME)
        self.setWindowIcon(qta.icon("mdi.robot", color=ACCENT))
        self.resize(1280, 800)
        self._position_on_secondary_screen()

    def _setup_ui(self):
        self.setWindowTitle("RPA Studio")

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(0)

        # Main splitter: left(palette) | center(editor) | right(properties)
        self._h_splitter = QSplitter(Qt.Orientation.Horizontal)

        self._palette = ActionPalette()
        self._h_splitter.addWidget(self._palette)

        self._editor = WorkflowEditor()
        self._h_splitter.addWidget(self._editor)

        self._properties = PropertiesPanel()
        self._h_splitter.addWidget(self._properties)

        self._h_splitter.setSizes([220, 600, 300])
        self._h_splitter.setHandleWidth(10)
        for panel in (self._palette, self._editor, self._properties):
            panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._h_splitter.setChildrenCollapsible(False)

        # Vertical splitter: top(main) | bottom(log)
        self._v_splitter = QSplitter(Qt.Orientation.Vertical)
        self._v_splitter.addWidget(self._h_splitter)

        self._log = LogPanel()
        self._log.setFixedHeight(200)
        self._log.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._v_splitter.addWidget(self._log)
        self._v_splitter.setSizes([580, 200])
        self._v_splitter.setHandleWidth(10)
        self._v_splitter.setChildrenCollapsible(False)

        main_layout.addWidget(self._v_splitter)

        self._editor.load_workflow(self._workflow)

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_label = QLabel("Listo")
        self._status_bar.addWidget(self._status_label)

        self._step_count_label = QLabel("0 pasos")
        self._status_bar.addPermanentWidget(self._step_count_label)

    def _position_on_secondary_screen(self):
        """Move Studio to the secondary screen (Pantalla 2) if available."""
        from core.screen_utils import secondary_rect
        sec = secondary_rect()
        if sec is None:
            return
        sx, sy, sw, sh = sec
        # Center the window on the secondary screen
        ww = min(self.width(),  sw)
        wh = min(self.height(), sh)
        self.resize(ww, wh)
        self.move(sx + (sw - ww) // 2, sy + (sh - wh) // 2)

    def _setup_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("Archivo")
        self._act_new = QAction("Nuevo", self)
        self._act_new.setShortcut(QKeySequence("Ctrl+N"))
        self._act_new.triggered.connect(self._new_workflow)

        self._act_open = QAction("Abrir...", self)
        self._act_open.setShortcut(QKeySequence("Ctrl+O"))
        self._act_open.triggered.connect(self._open_workflow)

        self._act_save = QAction("Guardar", self)
        self._act_save.setShortcut(QKeySequence("Ctrl+S"))
        self._act_save.triggered.connect(self._save_workflow)

        self._act_save_as = QAction("Guardar como...", self)
        self._act_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self._act_save_as.triggered.connect(self._save_workflow_as)

        file_menu.addAction(self._act_new)
        file_menu.addAction(self._act_open)
        file_menu.addSeparator()
        file_menu.addAction(self._act_save)
        file_menu.addAction(self._act_save_as)
        file_menu.addSeparator()
        file_menu.addAction("Salir", self.close)

        workflow_menu = menubar.addMenu("Workflow")
        self._act_run = QAction("▶  Ejecutar", self)
        self._act_run.setShortcut(QKeySequence("F5"))
        self._act_run.triggered.connect(self._run_workflow)

        self._act_stop = QAction("■  Detener", self)
        self._act_stop.setShortcut(QKeySequence("F6"))
        self._act_stop.triggered.connect(self._stop_workflow)
        self._act_stop.setEnabled(False)

        self._act_rename = QAction("Renombrar workflow...", self)
        self._act_rename.triggered.connect(self._rename_workflow)

        workflow_menu.addAction(self._act_run)
        workflow_menu.addAction(self._act_stop)
        workflow_menu.addSeparator()
        workflow_menu.addAction(self._act_rename)

    def _setup_toolbar(self):
        tb = QToolBar("Principal")
        tb.setMovable(False)
        tb.setStyleSheet("QToolBar { padding: 6px 8px; spacing: 6px; }")
        self.addToolBar(tb)

        # Robot logo
        robot_lbl = QLabel()
        robot_lbl.setPixmap(qta.icon("mdi.robot", color=ACCENT).pixmap(26, 26))
        robot_lbl.setFixedSize(30, 30)
        robot_lbl.setToolTip("RPA Studio")
        tb.addWidget(robot_lbl)
        tb.addSeparator()

        self._btn_new = QPushButton("Nuevo")
        self._btn_new.clicked.connect(self._new_workflow)
        tb.addWidget(self._btn_new)

        self._btn_open = QPushButton("Abrir")
        self._btn_open.clicked.connect(self._open_workflow)
        tb.addWidget(self._btn_open)

        self._btn_save = QPushButton("Guardar")
        self._btn_save.clicked.connect(self._save_workflow)
        tb.addWidget(self._btn_save)

        tb.addSeparator()

        self._btn_run = QPushButton("▶  Ejecutar")
        self._btn_run.setObjectName("btnRun")
        self._btn_run.setMinimumWidth(110)
        self._btn_run.setToolTip("F5")
        self._btn_run.clicked.connect(self._run_workflow)
        tb.addWidget(self._btn_run)

        self._btn_pause = QPushButton("⏸  Pausar")
        self._btn_pause.setObjectName("btnPause")
        self._btn_pause.setMinimumWidth(100)
        self._btn_pause.setEnabled(False)
        self._btn_pause.clicked.connect(self._pause_resume_workflow)
        tb.addWidget(self._btn_pause)

        self._btn_stop = QPushButton("■  Detener")
        self._btn_stop.setObjectName("btnStop")
        self._btn_stop.setMinimumWidth(100)
        self._btn_stop.setEnabled(False)
        self._btn_stop.setToolTip("F6")
        self._btn_stop.clicked.connect(self._stop_workflow)
        tb.addWidget(self._btn_stop)

        tb.addSeparator()

        self._wf_name_label = QLabel("Nuevo Workflow")
        self._wf_name_label.setStyleSheet(f"font-weight: 700; font-size: 13px; color: {TXT1}; padding: 0 8px;")
        tb.addWidget(self._wf_name_label)

        self._state_badge = QLabel()
        tb.addWidget(self._state_badge)
        self._set_state_badge(False)

    def _connect_signals(self):
        self._palette.action_requested.connect(self._editor.add_step)
        self._editor.step_selected.connect(self._on_step_selected)
        self._editor.workflow_changed.connect(self._on_workflow_changed)
        self._properties.step_changed.connect(self._on_step_params_changed)

        self._signals.log.connect(self._log.append_log)
        self._signals.step_start.connect(self._on_runner_step_start)
        self._signals.step_complete.connect(self._on_runner_step_complete)
        self._signals.finished.connect(self._on_runner_finished)
        self._signals.error.connect(self._on_runner_error)

    def _setup_runner_callbacks(self):
        def on_log(msg, level):
            self._signals.log.emit(msg, level)

        def on_step_start(idx, step):
            self._signals.step_start.emit(idx, step)

        def on_step_complete(idx, step, result):
            self._signals.step_complete.emit(idx, step, result)

        def on_finished(variables):
            self._signals.finished.emit(variables)

        def on_error(idx, step, error):
            self._signals.error.emit(idx, step, error)

        self._runner.on_log = on_log
        self._runner.on_step_start = on_step_start
        self._runner.on_step_complete = on_step_complete
        self._runner.on_finished = on_finished
        self._runner.on_error = on_error

    def _on_step_selected(self, step):
        if step:
            self._properties.load_step(step)
        else:
            self._properties.clear()

    def _on_workflow_changed(self):
        self._modified = True
        count = len(self._workflow.steps)
        self._step_count_label.setText(f"{count} paso{'s' if count != 1 else ''}")
        self._update_title()

    def _on_step_params_changed(self, step_id: str, params: dict):
        self._editor.refresh_step(step_id)
        self._modified = True
        self._update_title()

    def _on_runner_step_start(self, idx: int, step):
        self._editor.set_step_status(idx, "running")
        self._status_label.setText(f"Ejecutando paso {idx + 1}...")

    def _on_runner_step_complete(self, idx: int, step, result):
        from actions.base import ActionStatus
        status = "success" if result.status == ActionStatus.SUCCESS else "failed"
        self._editor.set_step_status(idx, status)

    def _on_runner_finished(self, variables: dict):
        self._set_running_state(False)
        state = self._runner.state
        if state == RunnerState.STOPPED:
            self._status_label.setText("Detenido")
        else:
            self._status_label.setText("Completado ✓")

    def _on_runner_error(self, idx: int, step, error: str):
        self._editor.set_step_status(idx, "failed")

    def _run_workflow(self):
        if self._runner.is_running:
            return
        if not self._workflow.steps:
            QMessageBox.information(self, "Sin pasos", "El workflow no tiene pasos.")
            return
        self._editor.reset_statuses()
        self._log.append_log(f"▶  {self._workflow.name}", "info")
        self._set_running_state(True)
        self._runner.run(self._workflow)

    def _stop_workflow(self):
        self._runner.stop()
        # buttons will be restored when on_finished fires from the runner thread
        self._btn_stop.setEnabled(False)
        self._btn_pause.setEnabled(False)
        self._status_label.setText("Deteniendo…")

    def _pause_resume_workflow(self):
        if self._runner.state == RunnerState.PAUSED:
            self._runner.resume()
            self._btn_pause.setText("⏸  Pausar")
            self._btn_pause.setObjectName("btnPause")
            self._btn_pause.setStyle(self._btn_pause.style())
            self._status_label.setText("Ejecutando…")
        elif self._runner.state == RunnerState.RUNNING:
            self._runner.pause()
            self._btn_pause.setText("▶  Reanudar")
            self._btn_pause.setObjectName("btnRun")
            self._btn_pause.setStyle(self._btn_pause.style())
            self._status_label.setText("En pausa ⏸")

    def _set_state_badge(self, running: bool):
        if running:
            self._state_badge.setText("Ejecutando")
            self._state_badge.setStyleSheet(badge_qss(INFO, INFO_BG))
        else:
            self._state_badge.setText("Listo")
            self._state_badge.setStyleSheet(badge_qss(SUCCESS, SUCCESS_BG))

    def _set_running_state(self, running: bool):
        self._set_state_badge(running)
        self._btn_run.setEnabled(not running)
        self._btn_pause.setEnabled(running)
        self._btn_stop.setEnabled(running)
        self._act_run.setEnabled(not running)
        self._act_stop.setEnabled(running)
        if not running:
            self._btn_pause.setText("⏸  Pausar")
            self._btn_pause.setObjectName("btnPause")
            self._btn_pause.setStyle(self._btn_pause.style())

    def _new_workflow(self):
        if self._modified and not self._confirm_discard():
            return
        self._workflow = Workflow(name="Nuevo Workflow")
        self._current_file = ""
        self._modified = False
        self._editor.load_workflow(self._workflow)
        self._properties.clear()
        self._wf_name_label.setText(self._workflow.name)
        self._update_title()
        self._step_count_label.setText("0 pasos")

    def _open_workflow(self):
        if self._modified and not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir Workflow", "workflows", "Workflow RPA (*.rpa.json);;JSON (*.json)"
        )
        if path:
            self.open_file(path)

    def open_file(self, path: str):
        """Load a workflow file into the editor (also used by `main.py --open`)."""
        try:
            self._workflow = Workflow.load(path)
            self._current_file = path
            self._modified = False
            self._editor.load_workflow(self._workflow)
            self._properties.clear()
            self._wf_name_label.setText(self._workflow.name)
            self._update_title()
            count = len(self._workflow.steps)
            self._step_count_label.setText(f"{count} paso{'s' if count != 1 else ''}")
            self._log.append_log(f"Workflow cargado: {self._workflow.name} ({count} pasos)", "info")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir el archivo:\n{str(e)}")

    def _save_workflow(self):
        if not self._current_file:
            self._save_workflow_as()
            return
        self._do_save(self._current_file)

    def _save_workflow_as(self):
        os.makedirs("workflows", exist_ok=True)
        default_name = os.path.join("workflows", f"{self._workflow.name}.rpa.json")
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar Workflow", default_name, "Workflow RPA (*.rpa.json);;JSON (*.json)"
        )
        if path:
            self._do_save(path)

    def _do_save(self, path: str):
        try:
            self._workflow.save(path)
            self._current_file = path
            self._modified = False
            self._update_title()
            self._status_label.setText(f"Guardado: {os.path.basename(path)}")
            self._log.append_log(f"Guardado: {path}", "success")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar:\n{str(e)}")

    def _rename_workflow(self):
        name, ok = QInputDialog.getText(self, "Renombrar", "Nombre del workflow:", text=self._workflow.name)
        if ok and name.strip():
            self._workflow.name = name.strip()
            self._wf_name_label.setText(self._workflow.name)
            self._modified = True
            self._update_title()

    def _update_title(self):
        modified_marker = " •" if self._modified else ""
        file_part = f" — {os.path.basename(self._current_file)}" if self._current_file else ""
        self.setWindowTitle(f"RPA Studio{file_part}{modified_marker}")

    def _confirm_discard(self) -> bool:
        reply = QMessageBox.question(
            self, "Cambios sin guardar",
            "Hay cambios sin guardar. ¿Descartar y continuar?",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
        )
        return reply == QMessageBox.StandardButton.Discard

    def closeEvent(self, event):
        if self._modified:
            reply = QMessageBox.question(
                self, "Salir", "Hay cambios sin guardar. ¿Salir de todos modos?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
        event.accept()
