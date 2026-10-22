from datetime import datetime
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QPushButton, QLabel
from PyQt6.QtGui import QTextCharFormat, QColor, QFont, QTextCursor
from PyQt6.QtCore import Qt, pyqtSlot
from .theme import TXT1, TXT3, TXT1_HEX, TXT3_HEX, TXT4_HEX, SUCCESS, WARNING, ERROR, INFO, DIVIDER

LOG_COLORS = {
    "info":    TXT1_HEX,
    "success": SUCCESS,
    "warning": WARNING,
    "error":   ERROR,
    "debug":   TXT3_HEX,
    "progress": INFO,
}


class LogPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("logPanel")
        self._progress_shown = False  # last line is a live "progress" line
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setStyleSheet(f"background: transparent; border: none; border-bottom: 1px solid {DIVIDER};")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 4, 8, 4)

        title = QLabel("LOG DE EJECUCIÓN")
        title.setStyleSheet(
            f"color: {TXT3}; font-weight: 700; font-size: 8pt; letter-spacing: 1px;"
            "background: transparent; border: none;"
        )

        btn_clear = QPushButton("Limpiar")
        btn_clear.setFixedHeight(24)
        btn_clear.setObjectName("btnGhost")
        btn_clear.setStyleSheet("font-size: 11px; padding: 0 10px;")
        btn_clear.clicked.connect(self.clear)

        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(btn_clear)
        layout.addWidget(header)

        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setMaximumBlockCount(2000)
        self._text.setFont(QFont("Consolas", 11))
        self._text.setStyleSheet(
            f"background: transparent; color: {TXT1}; border: none; padding: 6px 12px;"
        )
        layout.addWidget(self._text)

    @pyqtSlot(str, str)
    def append_log(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        color = LOG_COLORS.get(level, LOG_COLORS["info"])

        cursor = self._text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        # A progress line is rewritten in place and dropped once the step reports its result
        if self._progress_shown:
            self._remove_last_line(cursor)
        self._progress_shown = level == "progress"

        fmt_time = QTextCharFormat()
        fmt_time.setForeground(QColor(TXT4_HEX))

        fmt_msg = QTextCharFormat()
        fmt_msg.setForeground(QColor(color))
        if level == "error":
            fmt_msg.setFontWeight(600)

        cursor.insertText(f"[{timestamp}] ", fmt_time)
        cursor.insertText(message + "\n", fmt_msg)

        self._text.setTextCursor(cursor)
        self._text.ensureCursorVisible()

    @staticmethod
    def _remove_last_line(cursor: QTextCursor):
        # Every line ends with a newline, so the document's last block is empty
        cursor.movePosition(QTextCursor.MoveOperation.PreviousBlock)
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()

    def clear(self):
        self._text.clear()
        self._progress_shown = False
