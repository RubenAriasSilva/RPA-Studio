from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QLabel, QPushButton,
    QFrame, QGroupBox, QSizePolicy,
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont

from actions import ACTION_CATEGORIES, ACTION_LABELS, ACTION_REGISTRY
from .theme import GLASS, TXT2, BORDER, DIVIDER, ACCENT_SUBTLE, NAV_ACTIVE_TXT


class ActionButton(QPushButton):
    def __init__(self, action_type: str, parent=None):
        super().__init__(parent)
        action_cls = ACTION_REGISTRY.get(action_type)
        icon = action_cls.icon if action_cls else "⚙️"
        label = ACTION_LABELS.get(action_type, action_type)
        self.setText(f"{icon}  {label}")
        self.action_type = action_type
        self.setFixedHeight(30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                padding: 5px 10px;
                background-color: {GLASS};
                color: {TXT2};
                border: 1px solid {BORDER};
                border-radius: 8px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {ACCENT_SUBTLE};
                border-color: rgba(37,99,235,0.30);
                color: {NAV_ACTIVE_TXT};
            }}
            QPushButton:pressed {{
                background-color: rgba(59,130,246,0.18);
            }}
        """)


class ActionPalette(QWidget):
    action_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("actionPalette")
        self.setFixedWidth(220)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("Acciones")
        header.setObjectName("sectionTitle")
        header.setFixedHeight(32)
        header.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(header)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"background-color: {DIVIDER};")
        separator.setFixedHeight(1)
        layout.addWidget(separator)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(scroll)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(6)

        for category, action_types in ACTION_CATEGORIES.items():
            group = QGroupBox(category)
            group_layout = QVBoxLayout(group)
            group_layout.setContentsMargins(4, 8, 4, 4)
            group_layout.setSpacing(3)

            for action_type in action_types:
                btn = ActionButton(action_type)
                btn.clicked.connect(lambda checked, at=action_type: self.action_requested.emit(at))
                group_layout.addWidget(btn)

            content_layout.addWidget(group)

        content_layout.addStretch()
        scroll.setWidget(content)
