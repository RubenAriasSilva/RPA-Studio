from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QFrame, QAbstractItemView, QMenu, QInputDialog,
    QMessageBox,
)
from PyQt6.QtCore import pyqtSignal, Qt, QPoint, QTimer, QItemSelectionModel
from PyQt6.QtGui import QColor, QFont, QKeySequence, QShortcut, QPalette
from typing import Optional, List

from core.workflow import Workflow, WorkflowStep, StepGroup, DEFAULT_GROUP_TITLE
from actions import ACTION_REGISTRY, ACTION_LABELS
from actions.base import ActionStatus
from .theme import ACCENT, SUCCESS, ERROR, DIVIDER, TXT1_HEX, TXT4_HEX


STATUS_COLORS = {
    "pending": TXT1_HEX,
    "running": ACCENT,
    "success": SUCCESS,
    "failed": ERROR,
    "skipped": TXT4_HEX,
}

STATUS_ICONS = {
    "pending": "○",
    "running": "▶",
    "success": "✓",
    "failed": "✗",
    "skipped": "⊘",
}

GROUP_BG = "#e8effc"
SELECTION_HEX = "#e3edfd"
DISABLED_COLOR = TXT4_HEX


class GroupTreeItem(QTreeWidgetItem):
    def __init__(self, group: StepGroup):
        super().__init__()
        self.group = group
        self.setFlags(
            Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled
        )
        font = QFont()
        font.setBold(True)
        self.setFont(0, font)
        self.setBackground(0, QColor(GROUP_BG))
        self.update_display()

    def update_display(self):
        count = len(self.group.steps)
        enabled_prefix = "" if self.group.enabled else "⊘ "
        self.setText(0, f"{enabled_prefix}{self.group.title}   ({count} paso{'s' if count != 1 else ''})")
        self.setForeground(0, QColor(TXT1_HEX if self.group.enabled else DISABLED_COLOR))


class StepTreeItem(QTreeWidgetItem):
    def __init__(self, step: WorkflowStep, index: int, group_enabled: bool = True):
        super().__init__()
        self.step = step
        self.status = "pending"
        self.group_enabled = group_enabled
        self.index = index
        self.setFlags(
            Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsDragEnabled
        )
        self.update_display(index)

    def update_display(self, index: int = None, status: str = None):
        if index is not None:
            self.index = index
        if status:
            self.status = status
        action_cls = ACTION_REGISTRY.get(self.step.action_type)
        icon = action_cls.icon if action_cls else "⚙️"

        if action_cls:
            action_instance = action_cls(params=self.step.params)
            summary = action_instance.get_summary()
        else:
            summary = self.step.action_type

        status_icon = STATUS_ICONS.get(self.status, "○")
        enabled_prefix = "" if self.step.enabled else "⊘ "
        text = f"{status_icon}  {enabled_prefix}{self.index+1}. {icon} {summary}"
        self.setText(0, text)

        active = self.step.enabled and self.group_enabled
        color = STATUS_COLORS.get(self.status, TXT1_HEX)
        self.setForeground(0, QColor(color if active else DISABLED_COLOR))


class StepTree(QTreeWidget):
    """Tree with groups (top level) and steps (children). Drops are resolved
    against the workflow model instead of letting Qt move the items itself."""

    # (dragged group ids, dragged step ids, target group id or "", target index)
    drop_requested = pyqtSignal(list, list, str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setColumnCount(1)
        self.setIndentation(14)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setExpandsOnDoubleClick(False)
        # The branch area uses the palette highlight; match the item selection tint
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Highlight, QColor(SELECTION_HEX))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor(ACCENT))
        self.setPalette(pal)

    def dropEvent(self, event):
        selected = self.selectedItems()
        group_ids = [i.group.group_id for i in selected if isinstance(i, GroupTreeItem)]
        step_ids = [i.step.step_id for i in selected if isinstance(i, StepTreeItem)]
        target = self.itemAt(event.position().toPoint())
        pos = self.dropIndicatorPosition()
        Pos = QAbstractItemView.DropIndicatorPosition

        # Never let Qt move the items: the model is updated and the tree rebuilt
        event.setDropAction(Qt.DropAction.IgnoreAction)
        event.accept()

        if group_ids and step_ids:
            return

        if group_ids:
            if target is None or pos == Pos.OnViewport:
                index = self.topLevelItemCount()
            else:
                top = target if isinstance(target, GroupTreeItem) else target.parent()
                index = self.indexOfTopLevelItem(top)
                if not (isinstance(target, GroupTreeItem) and pos == Pos.AboveItem):
                    index += 1
            target_group = ""
        else:
            if target is None or pos == Pos.OnViewport:
                last = self.topLevelItem(self.topLevelItemCount() - 1)
                if last is None:
                    return
                target_group, index = last.group.group_id, last.childCount()
            elif isinstance(target, GroupTreeItem):
                gi = self.indexOfTopLevelItem(target)
                if pos == Pos.AboveItem and gi > 0:
                    prev = self.topLevelItem(gi - 1)
                    target_group, index = prev.group.group_id, prev.childCount()
                elif pos == Pos.OnItem:
                    target_group, index = target.group.group_id, target.childCount()
                else:
                    target_group, index = target.group.group_id, 0
            else:
                parent = target.parent()
                index = parent.indexOfChild(target)
                if pos != Pos.AboveItem:
                    index += 1
                target_group = parent.group.group_id

        # Defer: rebuilding the tree inside the drag loop is unsafe
        QTimer.singleShot(0, lambda: self.drop_requested.emit(group_ids, step_ids, target_group, index))


class WorkflowEditor(QWidget):
    step_selected = pyqtSignal(object)
    workflow_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("editorPanel")
        self._workflow: Optional[Workflow] = None
        self._step_items: List[StepTreeItem] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("Pasos del Workflow")
        header.setObjectName("sectionTitle")
        header.setFixedHeight(32)
        header.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(header)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"background-color: {DIVIDER};")
        separator.setFixedHeight(1)
        layout.addWidget(separator)

        self._tree = StepTree()
        self._tree.setObjectName("stepList")
        self._tree.itemSelectionChanged.connect(self._on_selection_changed)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._tree.itemExpanded.connect(lambda item: self._set_collapsed(item, False))
        self._tree.itemCollapsed.connect(lambda item: self._set_collapsed(item, True))
        self._tree.drop_requested.connect(self._on_drop_requested)
        layout.addWidget(self._tree)

        shortcut_ctx = Qt.ShortcutContext.WidgetShortcut
        QShortcut(QKeySequence(QKeySequence.StandardKey.Delete), self._tree,
                  self._delete_selected, context=shortcut_ctx)
        QShortcut(QKeySequence("Ctrl+D"), self._tree, self._duplicate_selected, context=shortcut_ctx)
        QShortcut(QKeySequence("F2"), self._tree, self._rename_selected_group, context=shortcut_ctx)

        btn_bar = QWidget()
        btn_bar.setStyleSheet(f"background: transparent; border: none; border-top: 1px solid {DIVIDER};")
        btn_layout = QHBoxLayout(btn_bar)
        btn_layout.setContentsMargins(8, 4, 8, 4)
        btn_layout.setSpacing(4)

        self._btn_up = QPushButton("↑")
        self._btn_up.setFixedWidth(36)
        self._btn_up.setToolTip("Mover arriba los seleccionados")
        self._btn_up.clicked.connect(self._move_up)

        self._btn_down = QPushButton("↓")
        self._btn_down.setFixedWidth(36)
        self._btn_down.setToolTip("Mover abajo los seleccionados")
        self._btn_down.clicked.connect(self._move_down)

        self._btn_add_group = QPushButton("＋ Grupo")
        self._btn_add_group.setToolTip("Nuevo grupo")
        self._btn_add_group.clicked.connect(self._add_group)

        self._btn_delete = QPushButton("🗑")
        self._btn_delete.setFixedWidth(36)
        self._btn_delete.setToolTip("Eliminar seleccionados (Supr)")
        self._btn_delete.clicked.connect(self._delete_selected)

        self._btn_duplicate = QPushButton("⧉")
        self._btn_duplicate.setFixedWidth(36)
        self._btn_duplicate.setToolTip("Duplicar seleccionados (Ctrl+D)")
        self._btn_duplicate.clicked.connect(self._duplicate_selected)

        for btn in (self._btn_up, self._btn_down, self._btn_duplicate, self._btn_delete):
            btn.setObjectName("btnGhost")

        btn_layout.addWidget(self._btn_up)
        btn_layout.addWidget(self._btn_down)
        btn_layout.addWidget(self._btn_add_group)
        btn_layout.addStretch()
        btn_layout.addWidget(self._btn_duplicate)
        btn_layout.addWidget(self._btn_delete)
        layout.addWidget(btn_bar)

    # ------------------------------------------------------------ building

    def load_workflow(self, workflow: Workflow):
        self._workflow = workflow
        self._refresh(select=([], []), keep_scroll=False)

    def _refresh(self, select=None, keep_scroll: bool = True):
        """Rebuild the tree. `select` = (group_ids, step_ids); None keeps the current selection."""
        if select is None:
            select = (self._selected_group_ids(), self._selected_step_ids())
        group_sel, step_sel = set(select[0]), set(select[1])
        scroll = self._tree.verticalScrollBar().value() if keep_scroll else 0

        self._tree.blockSignals(True)
        self._tree.clear()
        self._step_items = []
        current = None
        if self._workflow:
            idx = 0
            for group in self._workflow.groups:
                g_item = GroupTreeItem(group)
                self._tree.addTopLevelItem(g_item)
                for step in group.steps:
                    s_item = StepTreeItem(step, idx, group.enabled)
                    g_item.addChild(s_item)
                    self._step_items.append(s_item)
                    if step.step_id in step_sel:
                        s_item.setSelected(True)
                        current = current or s_item
                    idx += 1
                g_item.setExpanded(not group.collapsed)
                if group.group_id in group_sel:
                    g_item.setSelected(True)
                    current = current or g_item
        if current:
            self._tree.setCurrentItem(current, 0, QItemSelectionModel.SelectionFlag.NoUpdate)
        # clear() resets the scroll and setCurrentItem auto-scrolls: restore the previous
        # position and only scroll if the current item ended up out of view
        self._tree.doItemsLayout()
        self._tree.verticalScrollBar().setValue(scroll)
        if current:
            self._tree.scrollToItem(current, QAbstractItemView.ScrollHint.EnsureVisible)
        self._tree.blockSignals(False)
        self._on_selection_changed()

    def _changed(self, select=None):
        self._refresh(select)
        self.workflow_changed.emit()

    # ----------------------------------------------------------- selection

    def _selected_group_ids(self) -> List[str]:
        return [i.group.group_id for i in self._tree.selectedItems() if isinstance(i, GroupTreeItem)]

    def _selected_step_ids(self) -> List[str]:
        return [i.step.step_id for i in self._tree.selectedItems() if isinstance(i, StepTreeItem)]

    def _on_selection_changed(self):
        items = self._tree.selectedItems()
        if len(items) == 1 and isinstance(items[0], StepTreeItem):
            self.step_selected.emit(items[0].step)
        else:
            self.step_selected.emit(None)

    def _set_collapsed(self, item, collapsed: bool):
        if isinstance(item, GroupTreeItem):
            item.group.collapsed = collapsed

    # --------------------------------------------------------------- steps

    def add_step(self, action_type: str):
        if not self._workflow:
            return
        current = self._tree.currentItem()
        group_id, index = None, None
        if isinstance(current, StepTreeItem):
            parent = current.parent()
            group_id, index = parent.group.group_id, parent.indexOfChild(current) + 1
        elif isinstance(current, GroupTreeItem):
            group_id = current.group.group_id
            current.group.collapsed = False
        step = self._workflow.add_step(action_type, index=index, group_id=group_id)
        self._changed(select=([], [step.step_id]))

    def _on_drop_requested(self, group_ids: list, step_ids: list, target_group: str, index: int):
        if not self._workflow:
            return
        if group_ids:
            self._workflow.move_groups_to(group_ids, index)
        elif step_ids and target_group:
            self._workflow.move_steps_to_group(step_ids, target_group, index)
        else:
            return
        self._changed(select=(group_ids, step_ids))

    def _move(self, direction: int):
        if not self._workflow:
            return
        group_ids, step_ids = self._selected_group_ids(), self._selected_step_ids()
        if group_ids and step_ids:
            return
        if group_ids:
            self._workflow.move_groups(group_ids, direction)
        elif step_ids:
            self._workflow.move_steps(step_ids, direction)
        else:
            return
        self._changed()

    def _move_up(self):
        self._move(-1)

    def _move_down(self):
        self._move(1)

    def _delete_selected(self):
        if not self._workflow:
            return
        group_ids, step_ids = self._selected_group_ids(), self._selected_step_ids()
        if not group_ids and not step_ids:
            return
        groups = [self._workflow.get_group(gid) for gid in group_ids]
        n_steps = sum(len(g.steps) for g in groups if g)
        if n_steps:
            reply = QMessageBox.question(
                self, "Eliminar grupos",
                f"Se eliminarán {len(groups)} grupo(s) con {n_steps} paso(s) en total. ¿Continuar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self._workflow.remove_groups(group_ids)
        self._workflow.remove_steps(step_ids)
        self._changed(select=([], []))

    def _duplicate_selected(self):
        if not self._workflow:
            return
        group_ids, step_ids = self._selected_group_ids(), self._selected_step_ids()
        if group_ids and step_ids:
            return
        if group_ids:
            copies = self._workflow.duplicate_groups(group_ids)
            self._changed(select=([g.group_id for g in copies], []))
        elif step_ids:
            copies = self._workflow.duplicate_steps(step_ids)
            self._changed(select=([], [s.step_id for s in copies]))

    def _toggle_enabled(self):
        if not self._workflow:
            return
        group_ids, step_ids = self._selected_group_ids(), self._selected_step_ids()
        if group_ids and step_ids:
            return
        if group_ids:
            groups = [self._workflow.get_group(gid) for gid in group_ids]
            self._workflow.set_groups_enabled(group_ids, not any(g.enabled for g in groups))
        elif step_ids:
            ids = set(step_ids)
            any_enabled = any(s.enabled for s in self._workflow.steps if s.step_id in ids)
            self._workflow.set_steps_enabled(step_ids, not any_enabled)
        else:
            return
        self._changed()

    def _group_selected_steps(self):
        step_ids = self._selected_step_ids()
        if not self._workflow or not step_ids:
            return
        title, ok = QInputDialog.getText(self, "Agrupar pasos", "Título del grupo:", text=DEFAULT_GROUP_TITLE)
        if not ok:
            return
        self._workflow.group_steps(step_ids, title.strip())
        self._changed(select=([], step_ids))

    def _move_selected_to_group(self, group_id: str):
        step_ids = self._selected_step_ids()
        if not self._workflow or not step_ids:
            return
        self._workflow.move_steps_to_group(step_ids, group_id)
        self._changed(select=([], step_ids))

    # -------------------------------------------------------------- groups

    def _add_group(self):
        if not self._workflow:
            return
        title, ok = QInputDialog.getText(self, "Nuevo grupo", "Título del grupo:", text=DEFAULT_GROUP_TITLE)
        if not ok:
            return
        current = self._tree.currentItem()
        top = current.parent() if isinstance(current, StepTreeItem) else current
        index = self._tree.indexOfTopLevelItem(top) + 1 if top is not None else None
        group = self._workflow.add_group(title.strip(), index=index)
        self._changed(select=([group.group_id], []))

    def _rename_group(self, group: StepGroup):
        title, ok = QInputDialog.getText(self, "Renombrar grupo", "Título del grupo:", text=group.title)
        if ok:
            self._workflow.rename_group(group.group_id, title.strip())
            self._changed()

    def _rename_selected_group(self):
        current = self._tree.currentItem()
        if isinstance(current, GroupTreeItem):
            self._rename_group(current.group)

    def _on_item_double_clicked(self, item, column):
        if isinstance(item, GroupTreeItem):
            self._rename_group(item.group)

    # ---------------------------------------------------------------- menu

    def _show_context_menu(self, pos: QPoint):
        item = self._tree.itemAt(pos)
        if not item:
            return
        if not item.isSelected():
            self._tree.clearSelection()
            item.setSelected(True)
            self._tree.setCurrentItem(item)

        group_ids, step_ids = self._selected_group_ids(), self._selected_step_ids()
        menu = QMenu(self)

        if group_ids and step_ids:
            menu.addAction("🗑 Eliminar seleccionados", self._delete_selected)
            menu.exec(self._tree.viewport().mapToGlobal(pos))
            return

        if group_ids:
            groups = [self._workflow.get_group(gid) for gid in group_ids]
            any_enabled = any(g.enabled for g in groups)
            if len(group_ids) == 1:
                menu.addAction("✎ Renombrar…", lambda: self._rename_group(groups[0]))
                menu.addSeparator()
        else:
            ids = set(step_ids)
            any_enabled = any(s.enabled for s in self._workflow.steps if s.step_id in ids)

        menu.addAction("▲ Mover arriba", self._move_up)
        menu.addAction("▼ Mover abajo", self._move_down)
        menu.addSeparator()
        menu.addAction("⧉ Duplicar", self._duplicate_selected)
        menu.addAction("⊘ Deshabilitar" if any_enabled else "✓ Habilitar", self._toggle_enabled)

        if step_ids:
            menu.addSeparator()
            menu.addAction("▣ Agrupar selección…", self._group_selected_steps)
            move_menu = menu.addMenu("➜ Mover a grupo")
            for group in self._workflow.groups:
                move_menu.addAction(group.title, lambda gid=group.group_id: self._move_selected_to_group(gid))

        menu.addSeparator()
        menu.addAction("🗑 Eliminar", self._delete_selected)
        menu.exec(self._tree.viewport().mapToGlobal(pos))

    # -------------------------------------------------------------- status

    def refresh_step(self, step_id: str):
        for item in self._step_items:
            if item.step.step_id == step_id:
                item.update_display()
                break

    def set_step_status(self, step_idx: int, status: str):
        if 0 <= step_idx < len(self._step_items):
            self._step_items[step_idx].update_display(status=status)

    def reset_statuses(self):
        for item in self._step_items:
            item.update_display(status="pending")

    def get_current_step(self) -> Optional[WorkflowStep]:
        item = self._tree.currentItem()
        if isinstance(item, StepTreeItem):
            return item.step
        return None
