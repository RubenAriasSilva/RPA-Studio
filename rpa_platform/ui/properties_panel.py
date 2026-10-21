from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLabel, QLineEdit,
    QTextEdit, QCheckBox, QComboBox, QDoubleSpinBox, QSpinBox,
    QScrollArea, QPushButton, QHBoxLayout, QFileDialog, QFrame,
    QApplication,
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFont, QImage, QPixmap
from typing import Dict, Any, Optional
import numpy as np
import pyautogui

from actions import ACTION_REGISTRY, ACTION_LABELS
from core.workflow import WorkflowStep
from .region_selector import RegionSelectorOverlay
from .excel_preview import open_excel_preview
from .point_selector import PointSelectorOverlay
from .template_capture import TemplateCaptureOverlay
from .theme import TXT1, TXT3, TXT4, FORM_LABEL, DIVIDER, INPUT_BG, INPUT_BORDER, ACCENT, ACCENT_SUBTLE

FORM_LABEL_QSS = f"color: {FORM_LABEL}; font-size: 8pt; font-weight: 700; letter-spacing: 0.4px;"


class PropertiesPanel(QWidget):
    step_changed = pyqtSignal(str, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("propertiesPanel")
        self._current_step: Optional[WorkflowStep] = None
        self._widgets: Dict[str, QWidget] = {}
        self._field_rows: Dict[str, list] = {}
        self._schema: Dict[str, Dict] = {}
        self._region_overlay = RegionSelectorOverlay(self)
        self._region_target_key: Optional[str] = None
        self._region_overlay.region_selected.connect(self._on_region_selected)
        self._region_overlay.cancelled.connect(self._on_region_cancelled)
        self._vision_preview_labels: Dict[str, QLabel] = {}

        self._point_overlay = PointSelectorOverlay()
        self._point_target_keys: tuple[str, str] = ("x", "y")
        self._point_overlay.point_selected.connect(self._on_point_selected)
        self._point_overlay.cancelled.connect(self._on_region_cancelled)

        self._template_overlay = TemplateCaptureOverlay(save_dir="assets")
        self._template_target_key: Optional[str] = None
        self._template_overlay.captured.connect(self._on_template_captured)
        self._template_overlay.cancelled.connect(self._on_region_cancelled)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("Propiedades")
        header.setObjectName("sectionTitle")
        header.setFixedHeight(32)
        header.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(header)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"background-color: {DIVIDER};")
        separator.setFixedHeight(1)
        layout.addWidget(separator)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        layout.addWidget(self._scroll)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(12, 12, 12, 12)
        self._content_layout.setSpacing(8)
        self._content_layout.addStretch()
        self._scroll.setWidget(self._content)

        self._show_empty_state()

    def _clear_content(self):
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        self._widgets.clear()
        self._field_rows.clear()
        self._vision_preview_labels.clear()

    def _show_empty_state(self):
        self._clear_content()
        label = QLabel("Selecciona un paso\npara ver sus propiedades")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(f"color: {TXT4}; font-size: 13px;")
        self._content_layout.addStretch()
        self._content_layout.addWidget(label)
        self._content_layout.addStretch()

    def load_step(self, step: WorkflowStep):
        self._current_step = step
        self._clear_content()

        action_cls = ACTION_REGISTRY.get(step.action_type)
        if not action_cls:
            self._show_empty_state()
            return

        action_label = ACTION_LABELS.get(step.action_type, step.action_type)
        title = QLabel(f"{action_cls.icon}  {action_label}")
        title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {TXT1}; padding: 4px 0;")
        self._content_layout.addWidget(title)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"background-color: {DIVIDER}; margin: 4px 0;")
        separator.setFixedHeight(1)
        self._content_layout.addWidget(separator)

        enabled_cb = QCheckBox("Paso habilitado")
        enabled_cb.setChecked(step.enabled)
        enabled_cb.toggled.connect(lambda v: self._on_field_changed("_enabled", v))
        self._content_layout.addWidget(enabled_cb)
        self._widgets["_enabled"] = enabled_cb

        schema = action_cls.PARAM_SCHEMA
        self._schema = schema
        for param_key, param_meta in schema.items():
            self._add_field(param_key, param_meta, step.params.get(param_key, param_meta.get("default", "")))

        self._content_layout.addStretch()
        self._apply_visibility()

    def _field_value(self, key: str):
        """Current value of a field, falling back to the schema default."""
        if self._current_step and key in self._current_step.params:
            return self._current_step.params[key]
        return self._schema.get(key, {}).get("default", "")

    def _apply_visibility(self):
        """Show/hide fields declaring `visible_if: (controller_key, value)`."""
        for key, meta in self._schema.items():
            cond = meta.get("visible_if")
            if not cond or key not in self._field_rows:
                continue
            ctrl_key, expected = cond
            visible = str(self._field_value(ctrl_key)) == str(expected)
            for w in self._field_rows[key]:
                w.setVisible(visible)

    def _add_field(self, key: str, meta: Dict, current_value):
        label_text = meta.get("label", key)
        field_type = meta.get("type", "str")

        first_row = self._content_layout.count()
        label = QLabel(label_text)
        label.setStyleSheet(FORM_LABEL_QSS)

        required = meta.get("required", False)
        if required:
            label.setText(f"{label_text} *")
            label.setStyleSheet(FORM_LABEL_QSS + f"color: {TXT1};")

        self._content_layout.addWidget(label)

        if field_type == "bool":
            widget = QCheckBox()
            widget.setChecked(bool(current_value) if not isinstance(current_value, bool)
                              else current_value)
            widget.toggled.connect(lambda v, k=key: self._on_field_changed(k, v))
            self._content_layout.addWidget(widget)

        elif field_type == "int":
            widget = QSpinBox()
            widget.setRange(0, 99999)
            try:
                widget.setValue(int(current_value))
            except (ValueError, TypeError):
                widget.setValue(int(meta.get("default", 0)))
            widget.valueChanged.connect(lambda v, k=key: self._on_field_changed(k, v))
            self._content_layout.addWidget(widget)

        elif field_type == "float":
            widget = QDoubleSpinBox()
            widget.setRange(0.0, 9999.0)
            widget.setSingleStep(0.1)
            widget.setDecimals(2)
            try:
                widget.setValue(float(current_value))
            except (ValueError, TypeError):
                widget.setValue(float(meta.get("default", 0.0)))
            widget.valueChanged.connect(lambda v, k=key: self._on_field_changed(k, v))
            self._content_layout.addWidget(widget)

        elif field_type == "choice":
            widget = QComboBox()
            choices = meta.get("choices", [])
            widget.addItems(choices)
            try:
                idx = choices.index(str(current_value))
                widget.setCurrentIndex(idx)
            except (ValueError, IndexError):
                pass
            widget.currentTextChanged.connect(lambda v, k=key: self._on_field_changed(k, v))
            self._content_layout.addWidget(widget)

        elif field_type == "multiline" or meta.get("multiline", False):
            widget = QTextEdit()
            widget.setFixedHeight(80)
            widget.setPlainText(str(current_value) if current_value else "")
            widget.textChanged.connect(lambda k=key: self._on_field_changed(k, self._widgets[k].toPlainText()))
            self._content_layout.addWidget(widget)

        elif field_type == "region":
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)
            widget = QLineEdit(str(current_value) if current_value else "")
            widget.setPlaceholderText("x,y,ancho,alto")
            btn_pick = QPushButton("📐")
            btn_pick.setFixedWidth(32)
            btn_pick.setToolTip("Seleccionar región visualmente")
            btn_pick.setStyleSheet("font-size: 14px; padding: 2px;")
            btn_pick.clicked.connect(lambda checked, k=key: self._launch_region_selector(k))
            row_layout.addWidget(widget)
            row_layout.addWidget(btn_pick)
            widget.textChanged.connect(lambda v, k=key: self._on_field_changed(k, v))
            self._content_layout.addWidget(row)

            # Vision preview thumbnail — only for Vision AI actions
            _VISION_TYPES = frozenset({
                "vision_find_element", "vision_read_text",
                "vision_verify", "vision_wait_for_element",
            })
            if self._current_step and self._current_step.action_type in _VISION_TYPES:
                thumb = self._build_vision_preview(key, str(current_value) if current_value else "")

        elif field_type == "file":
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)
            widget = QLineEdit(str(current_value) if current_value else "")
            btn_browse = QPushButton("...")
            btn_browse.setFixedWidth(32)
            btn_browse.clicked.connect(lambda checked, k=key: self._browse_file(k))
            row_layout.addWidget(widget)
            row_layout.addWidget(btn_browse)
            # Excel preview button
            if self._current_step and self._current_step.action_type.startswith("excel_"):
                btn_preview = QPushButton("👁")
                btn_preview.setFixedWidth(32)
                btn_preview.setToolTip("Vista previa del archivo Excel")
                btn_preview.setStyleSheet("font-size: 14px; padding: 2px;")
                btn_preview.clicked.connect(lambda checked, k=key: self._preview_excel(k))
                row_layout.addWidget(btn_preview)

            # Template capture button for image-based actions
            _image_actions = ("find_image", "wait_for_image", "sap_click_button")
            if self._current_step and self._current_step.action_type in _image_actions:
                btn_capture = QPushButton("📸")
                btn_capture.setFixedWidth(32)
                btn_capture.setToolTip("Capturar elemento de pantalla como template")
                btn_capture.setStyleSheet("font-size: 14px; padding: 2px;")
                btn_capture.clicked.connect(lambda checked, k=key: self._launch_template_capture(k))
                row_layout.addWidget(btn_capture)

            widget.textChanged.connect(lambda v, k=key: self._on_field_changed(k, v))
            self._content_layout.addWidget(row)

        else:
            is_mouse = self._current_step and self._current_step.action_type.startswith("mouse_")
            is_coord = key in ("x", "y") and is_mouse

            if is_coord:
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(4)
                widget = QLineEdit(str(current_value) if current_value else "0")
                btn_pick = QPushButton("📍")
                btn_pick.setFixedWidth(32)
                btn_pick.setToolTip("Capturar coordenada haciendo click en pantalla")
                btn_pick.setStyleSheet("font-size: 14px; padding: 2px;")
                btn_pick.clicked.connect(lambda checked: self._launch_point_selector())
                row_layout.addWidget(widget)
                row_layout.addWidget(btn_pick)
                widget.textChanged.connect(lambda v, k=key: self._on_field_changed(k, v))
                self._content_layout.addWidget(row)
            else:
                widget = QLineEdit(str(current_value) if current_value else "")
                placeholder = meta.get("placeholder", "")
                if placeholder:
                    widget.setPlaceholderText(placeholder)
                widget.textChanged.connect(lambda v, k=key: self._on_field_changed(k, v))
                self._content_layout.addWidget(widget)

        self._widgets[key] = widget
        self._field_rows[key] = [
            self._content_layout.itemAt(i).widget()
            for i in range(first_row, self._content_layout.count())
            if self._content_layout.itemAt(i).widget()
        ]

    def _launch_region_selector(self, key: str):
        self._region_target_key = key
        self._region_overlay.start()

    def _on_region_selected(self, x: int, y: int, w: int, h: int):
        key = self._region_target_key
        if key and key in self._widgets:
            value = f"{x},{y},{w},{h}"
            self._widgets[key].setText(value)
            if key in self._vision_preview_labels:
                thumb = self._vision_preview_labels[key]
                QTimer.singleShot(150, lambda: self._update_vision_preview(thumb, value))

    def _on_region_cancelled(self):
        pass  # dialog closed — Studio stays in place

    def _launch_point_selector(self):
        self.window().setWindowOpacity(0.0)
        QTimer.singleShot(300, self._point_overlay.start)

    def _on_point_selected(self, x: int, y: int):
        self.window().setWindowOpacity(1.0)
        self.window().activateWindow()
        if "x" in self._widgets:
            self._widgets["x"].setText(str(x))
        if "y" in self._widgets:
            self._widgets["y"].setText(str(y))

    def _launch_template_capture(self, key: str):
        self._template_target_key = key
        self.window().setWindowOpacity(0.0)
        QTimer.singleShot(300, self._template_overlay.start)

    def _on_template_captured(self, file_path: str):
        self.window().setWindowOpacity(1.0)
        self.window().activateWindow()
        if self._template_target_key and self._template_target_key in self._widgets:
            self._widgets[self._template_target_key].setText(file_path)
            self._on_field_changed(self._template_target_key, file_path)

    def _preview_excel(self, key: str):
        if key in self._widgets:
            path = self._widgets[key].text().strip()
            if path:
                open_excel_preview(path, parent=self)

    def _browse_file(self, key: str):
        is_excel = self._current_step and self._current_step.action_type.startswith("excel_")
        if is_excel:
            path, _ = QFileDialog.getOpenFileName(
                self, "Seleccionar archivo Excel", "",
                "Excel (*.xlsx *.xls);;Todos (*.*)"
            )
        else:
            path, _ = QFileDialog.getOpenFileName(
                self, "Seleccionar archivo", "",
                "Imágenes (*.png *.jpg *.bmp);;Todos (*.*)"
            )
        if path and key in self._widgets:
            self._widgets[key].setText(path)

    def _on_field_changed(self, key: str, value):
        if not self._current_step:
            return
        if key == "_enabled":
            self._current_step.enabled = bool(value)
        else:
            self._current_step.params[key] = value
            if any(m.get("visible_if", (None,))[0] == key for m in self._schema.values()):
                self._apply_visibility()
        self.step_changed.emit(self._current_step.step_id, self._current_step.params)

    # ── Vision preview helpers ────────────────────────────────────────────────

    def _build_vision_preview(self, key: str, region_str: str) -> QLabel:
        """Create thumbnail container for Vision AI region fields."""
        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 4, 0, 0)
        vbox.setSpacing(3)

        # Header row: title + refresh button
        hrow = QWidget()
        hlay = QHBoxLayout(hrow)
        hlay.setContentsMargins(0, 0, 0, 0)
        hlay.setSpacing(4)
        title_lbl = QLabel("👁  Lo que verá la IA")
        title_lbl.setStyleSheet(f"color: {TXT3}; font-size: 11px;")
        btn_refresh = QPushButton("↻")
        btn_refresh.setFixedSize(22, 22)
        btn_refresh.setToolTip("Actualizar captura de la región")
        btn_refresh.setStyleSheet(
            f"QPushButton {{ background:{INPUT_BG}; border:none; border-radius:6px; font-size:13px; padding:0; }}"
            f"QPushButton:hover {{ background:{ACCENT_SUBTLE}; color:{ACCENT}; }}"
        )
        hlay.addWidget(title_lbl)
        hlay.addStretch()
        hlay.addWidget(btn_refresh)
        vbox.addWidget(hrow)

        # Thumbnail label
        thumb = QLabel("Sin región seleccionada")
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setStyleSheet(
            f"border: 1px dashed {INPUT_BORDER}; border-radius: 10px;"
            f"background: {INPUT_BG}; color: {TXT4}; font-size: 11px;"
        )
        thumb.setFixedHeight(120)
        thumb.setScaledContents(False)
        vbox.addWidget(thumb)

        self._content_layout.addWidget(container)
        self._vision_preview_labels[key] = thumb

        btn_refresh.clicked.connect(
            lambda checked, lbl=thumb, k=key: self._refresh_vision_preview(lbl, k)
        )

        # Auto-load if region already set when step is opened
        if region_str:
            QTimer.singleShot(300, lambda lbl=thumb, v=region_str: self._update_vision_preview(lbl, v))

        return thumb

    def _refresh_vision_preview(self, thumb: QLabel, key: str):
        w = self._widgets.get(key)
        region_str = w.text().strip() if w and hasattr(w, "text") else ""
        self._update_vision_preview(thumb, region_str)

    def _update_vision_preview(self, thumb: QLabel, region_str: str):
        if not region_str:
            thumb.clear()
            thumb.setText("Sin región seleccionada")
            return
        try:
            parts = [int(v.strip()) for v in region_str.split(",")]
            if len(parts) != 4 or parts[2] <= 0 or parts[3] <= 0:
                thumb.setText("Región inválida")
                return
            rx, ry, rw, rh = parts
            img = pyautogui.screenshot(region=(rx, ry, rw, rh))
            arr = np.array(img)
            qimg = QImage(arr.data, arr.shape[1], arr.shape[0],
                          arr.shape[1] * 3, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)
            avail_w = max(thumb.width() - 8, 160)
            avail_h = thumb.height() - 8
            scaled = pixmap.scaled(
                avail_w, avail_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            thumb.setPixmap(scaled)
            thumb.setText("")
        except Exception as e:
            thumb.setText(f"Error: {str(e)[:60]}")

    def clear(self):
        self._current_step = None
        self._show_empty_state()
