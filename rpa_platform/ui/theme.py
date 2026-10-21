"""Design tokens from DESIGN_SYSTEM.md, shared by RPA Studio and the Orchestrator.

Qt has no backdrop-filter, so "glass" surfaces are approximated with
semi-transparent white over the gradient background plus a light border.
"""

FONT_FAMILY = '"Inter", "Segoe UI Variable Display", "Segoe UI", sans-serif'

# Background — soft blue gradient (body-bg)
BODY_BG = (
    "qlineargradient(x1:0, y1:0, x2:0.25, y2:1, "
    "stop:0 #eef5ff, stop:0.35 #e8f1fe, stop:0.65 #eef2ff, stop:1 #f3f0ff)"
)
BODY_BG_SOLID = "#eef3ff"

# Surfaces
GLASS         = "rgba(255,255,255,0.68)"
GLASS_HOVER   = "rgba(255,255,255,0.84)"
GLASS_BORDER  = "rgba(255,255,255,0.88)"
GLASS_STRONG  = "rgba(240,246,255,0.96)"
NAV_BG        = "rgba(255,255,255,0.78)"
SB_BG         = "rgba(255,255,255,0.62)"
BORDER        = "rgba(0,0,0,0.07)"
BORDER_STRONG = "rgba(0,0,0,0.09)"
DIVIDER       = "rgba(0,0,0,0.07)"
SCROLLBAR     = "rgba(0,0,0,0.10)"

# Text — slate scale (never pure black)
TXT1 = "rgba(15,23,42,0.92)"
TXT2 = "rgba(51,65,85,0.75)"
TXT3 = "rgba(100,116,139,0.68)"
TXT4 = "rgba(148,163,184,0.70)"

# Accent
ACCENT        = "#2563eb"
ACCENT_HOVER  = "#1d4ed8"
ACCENT_SUBTLE = "rgba(59,130,246,0.10)"
ACCENT_FAINT  = "rgba(59,130,246,0.04)"
NAV_ACTIVE_TXT = "rgba(30,64,175,0.95)"
NAV_HOVER_BG  = "rgba(0,0,0,0.04)"

# Forms
INPUT_BG      = "rgba(0,0,0,0.04)"
INPUT_BORDER  = "rgba(0,0,0,0.12)"
INPUT_FOCUS   = "rgba(37,99,235,0.55)"
FORM_LABEL    = "rgba(51,65,85,0.72)"

# Semantic (badges)
SUCCESS    = "#166534"
SUCCESS_BG = "rgba(21,128,61,0.10)"
WARNING    = "#b45309"
WARNING_BG = "rgba(180,83,9,0.10)"
ERROR      = "#b91c1c"
ERROR_BG   = "rgba(220,38,38,0.10)"
ERROR_BORDER = "rgba(220,38,38,0.20)"
INFO       = "#1d4ed8"
INFO_BG    = "rgba(37,99,235,0.10)"
MUTED      = "rgba(100,116,139,0.80)"
MUTED_BG   = "rgba(100,116,139,0.10)"

# Opaque equivalents for APIs that need a QColor (item foregrounds, icons)
TXT1_HEX = "#1e293b"
TXT3_HEX = "#64748b"
TXT4_HEX = "#94a3b8"


def badge(text: str, fg: str, bg: str) -> str:
    """Rich-text pill (DESIGN_SYSTEM §10) for QLabel HTML."""
    return (
        f'<span style="background:{bg}; color:{fg}; font-weight:600; '
        f'font-size:8pt;">&nbsp;{text}&nbsp;</span>'
    )


def badge_qss(fg: str, bg: str) -> str:
    """Stylesheet for a QLabel rendered as a pill."""
    return (
        f"background:{bg}; color:{fg}; border-radius:10px; padding:3px 10px; "
        f"font-size:8pt; font-weight:600;"
    )
