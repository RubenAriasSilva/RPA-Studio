from .theme import (
    FONT_FAMILY, BODY_BG, GLASS, GLASS_HOVER, GLASS_BORDER, GLASS_STRONG, NAV_BG, SB_BG,
    BORDER, BORDER_STRONG, DIVIDER, SCROLLBAR, TXT1, TXT2, TXT3, TXT4,
    ACCENT, ACCENT_HOVER, ACCENT_SUBTLE, ACCENT_FAINT, NAV_ACTIVE_TXT, NAV_HOVER_BG,
    INPUT_BG, INPUT_BORDER, INPUT_FOCUS, WARNING, WARNING_BG, ERROR, ERROR_BG, ERROR_BORDER,
)

LIGHT_THEME = f"""
/* ── Base ── */
QWidget {{
    background: transparent;
    color: {TXT1};
    font-family: {FONT_FAMILY};
}}
/* must come after the QWidget rule: same specificity, last one wins */
QMainWindow {{ background: {BODY_BG}; }}

/* ── Menu bar / topbar ── */
QMenuBar {{
    background-color: {NAV_BG};
    color: {TXT2};
    border-bottom: 1px solid {BORDER};
    padding: 2px 4px;
}}
QMenuBar::item {{ padding: 4px 10px; border-radius: 8px; background: transparent; }}
QMenuBar::item:selected {{ background-color: {NAV_HOVER_BG}; color: {TXT1}; }}
QMenu {{
    background-color: {GLASS_STRONG};
    border: 1px solid {BORDER_STRONG};
    border-radius: 12px;
    padding: 5px;
}}
QMenu::item {{ padding: 6px 24px 6px 14px; border-radius: 8px; color: {TXT1}; background: transparent; }}
QMenu::item:selected {{ background-color: {ACCENT_SUBTLE}; color: {NAV_ACTIVE_TXT}; }}
QMenu::item:disabled {{ color: {TXT4}; }}
QMenu::separator {{ height: 1px; background: {DIVIDER}; margin: 4px 8px; }}

/* ── Toolbar ── */
QToolBar {{
    background-color: {NAV_BG};
    border: none;
    border-bottom: 1px solid {BORDER};
    spacing: 6px;
    padding: 6px 10px;
}}
QToolBar::separator {{ background: {DIVIDER}; width: 1px; margin: 6px 6px; }}

/* ── Splitter ── */
QSplitter::handle {{ background-color: transparent; }}
QSplitter::handle:horizontal {{ width: 6px; }}
QSplitter::handle:vertical   {{ height: 6px; }}

/* ── Glass panels ── */
#actionPalette, #propertiesPanel, #editorPanel {{
    background-color: {GLASS};
    border: 1px solid {GLASS_BORDER};
    border-radius: 16px;
}}
#logPanel {{
    background-color: {GLASS};
    border: 1px solid {GLASS_BORDER};
    border-radius: 16px;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 12px;
}}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}

/* ── Section titles (.section-title) ── */
QLabel#sectionTitle {{
    color: {TXT3};
    font-weight: 700;
    font-size: 8pt;
    padding: 0px 14px;
    letter-spacing: 1px;
    background: transparent;
    border: none;
    border-bottom: 1px solid {DIVIDER};
}}

/* ── Step tree ── */
#stepList {{
    background: transparent;
    border: none;
    outline: none;
}}
#stepList::item {{
    padding: 8px 10px;
    border-bottom: 1px solid {DIVIDER};
    color: {TXT1};
}}
#stepList::item:selected {{
    background-color: {ACCENT_SUBTLE};
    color: {NAV_ACTIVE_TXT};
}}
#stepList::item:hover:!selected {{ background-color: {ACCENT_FAINT}; }}

/* ── Buttons — secondary (glass) by default ── */
QPushButton {{
    background-color: {GLASS};
    color: {TXT2};
    border: 1px solid {INPUT_BORDER};
    border-radius: 10px;
    padding: 6px 16px;
    font-weight: 600;
}}
QPushButton:hover    {{ background-color: {GLASS_HOVER}; color: {TXT1}; border-color: rgba(37,99,235,0.30); }}
QPushButton:pressed  {{ background-color: {ACCENT_SUBTLE}; color: {NAV_ACTIVE_TXT}; }}
QPushButton:disabled {{ color: {TXT4}; background-color: rgba(255,255,255,0.40); border-color: {BORDER}; }}

/* Ghost — icon buttons in panel bars */
QPushButton#btnGhost {{
    background: transparent; border: none; color: {TXT3};
    border-radius: 8px; padding: 5px 8px;
}}
QPushButton#btnGhost:hover {{ background: {NAV_HOVER_BG}; color: {TXT1}; }}

/* Primary — run */
QPushButton#btnRun {{
    background-color: {ACCENT};
    color: #FFFFFF;
    border: none;
}}
QPushButton#btnRun:hover    {{ background-color: {ACCENT_HOVER}; color: #FFFFFF; }}
QPushButton#btnRun:pressed  {{ background-color: {ACCENT_HOVER}; color: #FFFFFF; }}
QPushButton#btnRun:disabled {{ background-color: {ACCENT_SUBTLE}; color: {TXT4}; }}

/* Danger — stop */
QPushButton#btnStop {{
    background-color: {ERROR_BG};
    color: {ERROR};
    border: 1px solid {ERROR_BORDER};
}}
QPushButton#btnStop:hover    {{ background-color: rgba(220,38,38,0.18); color: {ERROR}; }}
QPushButton#btnStop:disabled {{ background-color: rgba(255,255,255,0.40); color: {TXT4}; border-color: {BORDER}; }}

/* Warning — pause */
QPushButton#btnPause {{
    background-color: {WARNING_BG};
    color: {WARNING};
    border: 1px solid rgba(180,83,9,0.20);
}}
QPushButton#btnPause:hover    {{ background-color: rgba(180,83,9,0.18); color: {WARNING}; }}
QPushButton#btnPause:disabled {{ background-color: rgba(255,255,255,0.40); color: {TXT4}; border-color: {BORDER}; }}

/* ── Inputs ── */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTimeEdit {{
    background-color: {INPUT_BG};
    color: {TXT1};
    border: 1px solid {INPUT_BORDER};
    border-radius: 10px;
    padding: 6px 10px;
    selection-background-color: {ACCENT};
    selection-color: #FFFFFF;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QTimeEdit:focus {{
    border: 1px solid {INPUT_FOCUS};
    background-color: rgba(255,255,255,0.85);
}}
QLineEdit:disabled, QTextEdit:disabled {{ background-color: {INPUT_BG}; color: {TXT4}; }}

QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background: transparent; border: none; width: 16px;
}}

QComboBox {{ padding-right: 24px; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox::down-arrow {{
    image: none; width: 0; height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TXT3};
}}
QComboBox QAbstractItemView {{
    background-color: {GLASS_STRONG};
    border: 1px solid {BORDER_STRONG};
    border-radius: 10px;
    selection-background-color: {ACCENT_SUBTLE};
    selection-color: {NAV_ACTIVE_TXT};
    padding: 4px;
    color: {TXT1};
    outline: none;
}}

/* ── Checkbox ── */
QCheckBox {{ spacing: 8px; color: {TXT1}; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {INPUT_BORDER};
    border-radius: 5px;
    background-color: rgba(255,255,255,0.85);
}}
QCheckBox::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
}}

/* ── Scrollbars (§15) ── */
QScrollBar:vertical {{ background: transparent; width: 5px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: {SCROLLBAR}; border-radius: 2px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: rgba(0,0,0,0.18); }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

QScrollBar:horizontal {{ background: transparent; height: 5px; margin: 2px 4px; }}
QScrollBar::handle:horizontal {{ background: {SCROLLBAR}; border-radius: 2px; min-width: 24px; }}
QScrollBar::handle:horizontal:hover {{ background: rgba(0,0,0,0.18); }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}

/* ── Group boxes (palette categories) ── */
QGroupBox {{
    color: {TXT3};
    border: 1px solid {BORDER};
    border-radius: 12px;
    margin-top: 12px;
    padding-top: 8px;
    font-size: 8pt;
    font-weight: 700;
    background-color: rgba(255,255,255,0.45);
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
    color: {TXT3};
    letter-spacing: 0.5px;
}}

/* ── Status bar ── */
QStatusBar {{
    background-color: {NAV_BG};
    color: {TXT3};
    border-top: 1px solid {BORDER};
}}
QStatusBar::item {{ border: none; }}

/* ── Dialogs (.glass-strong) ── */
QDialog, QMessageBox, QInputDialog {{ background-color: {GLASS_STRONG}; }}
QDialog QLabel, QMessageBox QLabel {{ color: {TXT1}; }}

/* ── Table (§9, Excel preview) ── */
QTableWidget, QTableView {{
    background-color: rgba(255,255,255,0.85);
    color: {TXT1};
    gridline-color: {DIVIDER};
    border: 1px solid {BORDER};
    border-radius: 12px;
    alternate-background-color: {ACCENT_FAINT};
}}
QTableWidget::item {{ padding: 4px 8px; color: {TXT1}; }}
QTableWidget::item:selected {{ background-color: {ACCENT_SUBTLE}; color: {NAV_ACTIVE_TXT}; }}
QHeaderView::section {{
    background-color: rgba(0,0,0,0.025);
    color: {TXT3};
    border: none;
    border-bottom: 1px solid {DIVIDER};
    padding: 6px 10px;
    font-size: 8pt;
    font-weight: 700;
}}

/* ── Tooltip ── */
QToolTip {{
    background-color: {GLASS_STRONG};
    color: {TXT1};
    border: 1px solid {BORDER_STRONG};
    border-radius: 8px;
    padding: 5px 9px;
}}

/* ── Frame separators ── */
QFrame[frameShape="4"],
QFrame[frameShape="5"] {{
    color: {DIVIDER};
    background-color: {DIVIDER};
    border: none;
}}
"""

# Keep old name working
DARK_THEME = LIGHT_THEME
