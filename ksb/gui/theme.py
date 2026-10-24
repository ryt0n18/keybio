"""Temas claro y oscuro, hoja de estilos y paleta de Qt.

Los colores son atributos del módulo (``theme.TEXT``, ``theme.SERIES_1``...)
que ``apply()`` reemplaza al cambiar de tema; los widgets los leen en el
momento de pintar, así que basta con repintar para cambiar de tema.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtGui import QColor, QFont, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

LIGHT = {
    "SURFACE": "#fcfcfb", "SURFACE_2": "#f6f5f2", "BACKGROUND": "#f1f0ec",
    "SIDEBAR": "#e8e7e2", "SIDEBAR_HOVER": "#f0efea",
    "BORDER": "#dddcd6", "BORDER_STRONG": "#c9c8c1",
    "TEXT": "#0b0b0b", "TEXT_2": "#52514e", "MUTED": "#7c7b76",
    "ACCENT": "#2a78d6", "ACCENT_HOVER": "#1c5cab", "ACCENT_SOFT": "#cde2fb", "ON_ACCENT": "#ffffff",
    "GOOD": "#1a7f37", "GOOD_SOFT": "#dcf2e2",
    "WARN": "#9a6700", "WARN_SOFT": "#fdf0cf",
    "BAD": "#c62828", "BAD_SOFT": "#fde2e1",
    "SERIES_1": "#2a78d6", "SERIES_2": "#eb6834", "GRID": "#e6e5e0",
    "HEAT_LOW": "#cde2fb", "HEAT_HIGH": "#184f95",
    "KEY": "#efeee9", "KEY_EDGE": "#d6d5ce",
    "CATEGORICAL": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"],
}

DARK = {
    "SURFACE": "#1a1a19", "SURFACE_2": "#222220", "BACKGROUND": "#121211",
    "SIDEBAR": "#161615", "SIDEBAR_HOVER": "#20201e",
    "BORDER": "#2f2f2c", "BORDER_STRONG": "#46463f",
    "TEXT": "#f0efec", "TEXT_2": "#c3c2b7", "MUTED": "#8f8e86",
    "ACCENT": "#3987e5", "ACCENT_HOVER": "#5598e7", "ACCENT_SOFT": "#1d3a5f", "ON_ACCENT": "#ffffff",
    "GOOD": "#4ac26b", "GOOD_SOFT": "#17301f",
    "WARN": "#d9a73a", "WARN_SOFT": "#392d11",
    "BAD": "#f47067", "BAD_SOFT": "#3f1b1a",
    "SERIES_1": "#3987e5", "SERIES_2": "#d95926", "GRID": "#2b2b29",
    "HEAT_LOW": "#183a63", "HEAT_HIGH": "#9ec5f4",
    "KEY": "#262624", "KEY_EDGE": "#363633",
    "CATEGORICAL": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
}

MODE = "light"
SCALE = 1.0
BASE_PT = 10.5
ARROWS: dict[str, str] = {"down": "", "up": ""}

# Valores iniciales (se sobrescriben en apply)
globals().update(LIGHT)


def system_is_dark() -> bool:
    try:
        from PySide6.QtCore import Qt
        return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except Exception:  # Qt < 6.5 o sin información del sistema
        return False


def resolve(mode: str) -> str:
    if mode == "system":
        return "dark" if system_is_dark() else "light"
    return "dark" if mode == "dark" else "light"


def status_color(level: str) -> str:
    g = globals()
    return {"good": g["GOOD"], "warn": g["WARN"], "bad": g["BAD"]}.get(level, g["MUTED"])


def status_soft(level: str) -> str:
    g = globals()
    return {"good": g["GOOD_SOFT"], "warn": g["WARN_SOFT"], "bad": g["BAD_SOFT"]}.get(level, g["SURFACE_2"])


def category(index: int) -> str:
    """Color categórico fijo por entidad; más allá de 8 se usa gris neutro."""
    cats = globals()["CATEGORICAL"]
    return cats[index] if 0 <= index < len(cats) else globals()["MUTED"]


def _write_arrows() -> None:
    """Flechas de los desplegables como SVG (la hoja de estilos necesita ficheros)."""
    folder = Path(tempfile.gettempdir()) / "keybio-ui"
    folder.mkdir(parents=True, exist_ok=True)
    color = globals()["TEXT_2"]
    shapes = {"down": "M6 9l6 6 6-6", "up": "M6 15l6-6 6 6"}
    for name, d in shapes.items():
        path = folder / f"{MODE}-{name}.svg"
        path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
                        f'stroke="{color}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">'
                        f'<path d="{d}"/></svg>', encoding="utf-8")
        ARROWS[name] = path.as_posix()


def pt(size: float) -> str:
    return f"{size * SCALE:.1f}pt"


def stylesheet() -> str:
    g = globals()
    return f"""
QMainWindow, QWidget#root, QWidget#page, QStackedWidget {{ background: {g['BACKGROUND']}; }}
QWidget {{ color: {g['TEXT']}; }}
QToolTip {{ background: {g['TEXT']}; color: {g['BACKGROUND']}; border: none; padding: 6px; }}

QWidget#sidebar {{ background: {g['SIDEBAR']}; }}
QLabel#brand {{ font-size: {pt(15)}; font-weight: 700; }}
QLabel#brandSub {{ color: {g['TEXT_2']}; font-size: {pt(9)}; }}
QListWidget#nav {{ background: transparent; border: none; outline: 0; }}
QListWidget#nav::item {{ padding: 9px 10px; margin: 2px 8px; border-radius: 7px; color: {g['TEXT_2']}; }}
QListWidget#nav::item:selected {{ background: {g['SURFACE']}; color: {g['TEXT']}; font-weight: 600; }}
QListWidget#nav::item:hover:!selected {{ background: {g['SIDEBAR_HOVER']}; }}

QLabel#title {{ font-size: {pt(18)}; font-weight: 700; }}
QLabel#hero {{ font-size: {pt(22)}; font-weight: 700; }}
QLabel#subtitle {{ color: {g['TEXT_2']}; }}
QLabel#muted {{ color: {g['MUTED']}; }}
QLabel#section {{ font-size: {pt(11.5)}; font-weight: 600; }}
QLabel#small {{ color: {g['TEXT_2']}; font-size: {pt(9)}; }}
QLabel#tileValue {{ font-size: {pt(19)}; font-weight: 700; }}
QLabel#tileLabel {{ color: {g['TEXT_2']}; font-size: {pt(9.5)}; }}
QLabel#tileSub {{ color: {g['MUTED']}; font-size: {pt(8.5)}; }}
QLabel#badge {{ border-radius: 9px; padding: 2px 9px; font-size: {pt(8.5)}; font-weight: 600; }}
QLabel#banner {{ border-radius: 6px; padding: 7px 12px; font-weight: 600; }}

QFrame#card {{ background: {g['SURFACE']}; border: 1px solid {g['BORDER']}; border-radius: 12px; }}
QFrame#card[status="good"] {{ border-left: 6px solid {g['GOOD']}; }}
QFrame#card[status="warn"] {{ border-left: 6px solid {g['WARN']}; }}
QFrame#card[status="bad"] {{ border-left: 6px solid {g['BAD']}; }}
QFrame#tile {{ background: {g['SURFACE']}; border: 1px solid {g['BORDER']}; border-radius: 10px; }}
QFrame#separator {{ background: {g['BORDER']}; max-height: 1px; border: none; }}

QPushButton {{
    background: {g['SURFACE']}; border: 1px solid {g['BORDER']}; border-radius: 7px; padding: 7px 14px;
}}
QPushButton:hover {{ background: {g['SURFACE_2']}; border-color: {g['BORDER_STRONG']}; }}
QPushButton:disabled {{ color: {g['MUTED']}; }}
QPushButton#primary {{ background: {g['ACCENT']}; border-color: {g['ACCENT']}; color: {g['ON_ACCENT']}; font-weight: 600; }}
QPushButton#primary:hover {{ background: {g['ACCENT_HOVER']}; border-color: {g['ACCENT_HOVER']}; }}
QPushButton#primary:disabled {{ background: {g['ACCENT_SOFT']}; border-color: {g['ACCENT_SOFT']}; color: {g['MUTED']}; }}
QPushButton#big {{ padding: 12px 20px; font-size: {pt(11.5)}; }}
QPushButton#danger {{ color: {g['BAD']}; }}
QPushButton#flat {{ background: transparent; border: none; color: {g['TEXT_2']}; text-align: left; padding: 6px 10px; }}
QPushButton#flat:hover {{ background: {g['SIDEBAR_HOVER']}; color: {g['TEXT']}; }}
QPushButton#seg {{ border-radius: 0; padding: 6px 12px; }}
QPushButton#seg:checked {{ background: {g['ACCENT_SOFT']}; border-color: {g['ACCENT']}; color: {g['TEXT']}; font-weight: 600; }}

QLineEdit, QSpinBox, QComboBox {{
    background: {g['SURFACE']}; border: 1px solid {g['BORDER']}; border-radius: 7px; padding: 6px 8px;
    selection-background-color: {g['ACCENT']};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {g['ACCENT']}; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{ image: url("{ARROWS['down']}"); width: 14px; height: 14px; }}
QSpinBox {{ padding-right: 26px; }}
QSpinBox::up-button, QSpinBox::down-button {{ border: none; width: 24px; background: transparent; }}
QSpinBox::up-button {{ subcontrol-origin: border; subcontrol-position: top right; }}
QSpinBox::down-button {{ subcontrol-origin: border; subcontrol-position: bottom right; }}
QSpinBox::up-arrow {{ image: url("{ARROWS['up']}"); width: 12px; height: 12px; }}
QSpinBox::down-arrow {{ image: url("{ARROWS['down']}"); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{ background: {g['SURFACE']}; border: 1px solid {g['BORDER']};
    selection-background-color: {g['ACCENT_SOFT']}; selection-color: {g['TEXT']}; }}
QCheckBox {{ spacing: 8px; }}

QPlainTextEdit#typingInput {{
    background: {g['SURFACE']}; border: 2px solid {g['BORDER']}; border-radius: 10px; padding: 8px;
    font-size: {pt(15)}; selection-background-color: {g['ACCENT_SOFT']};
}}
QPlainTextEdit#typingInput:focus {{ border-color: {g['ACCENT']}; }}
QTextEdit#targetText {{
    background: {g['SURFACE']}; border: 1px solid {g['BORDER']}; border-radius: 10px; padding: 12px;
    font-size: {pt(16)};
}}
QProgressBar {{ background: {g['GRID']}; border: none; border-radius: 3px; max-height: 6px; }}
QProgressBar::chunk {{ background: {g['ACCENT']}; border-radius: 3px; }}

QTableWidget {{
    background: {g['SURFACE']}; border: 1px solid {g['BORDER']}; border-radius: 10px;
    gridline-color: {g['GRID']}; selection-background-color: {g['ACCENT_SOFT']}; selection-color: {g['TEXT']};
    alternate-background-color: {g['SURFACE_2']};
}}
QHeaderView::section {{
    background: {g['SURFACE']}; border: none; border-bottom: 1px solid {g['BORDER']};
    padding: 7px 6px; color: {g['TEXT_2']}; font-weight: 600;
}}
QTableCornerButton::section {{ background: {g['SURFACE']}; border: none; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 11px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {g['BORDER_STRONG']}; border-radius: 4px; min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: 11px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {g['BORDER_STRONG']}; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QLabel#toast {{
    background: {g['TEXT']}; color: {g['BACKGROUND']}; border-radius: 8px; padding: 10px 18px; font-weight: 600;
}}
"""


def qpalette() -> QPalette:
    g = globals()
    p = QPalette()
    roles = {
        QPalette.ColorRole.Window: g["BACKGROUND"], QPalette.ColorRole.WindowText: g["TEXT"],
        QPalette.ColorRole.Base: g["SURFACE"], QPalette.ColorRole.AlternateBase: g["SURFACE_2"],
        QPalette.ColorRole.Text: g["TEXT"], QPalette.ColorRole.Button: g["SURFACE"],
        QPalette.ColorRole.ButtonText: g["TEXT"], QPalette.ColorRole.Highlight: g["ACCENT"],
        QPalette.ColorRole.HighlightedText: g["ON_ACCENT"], QPalette.ColorRole.ToolTipBase: g["TEXT"],
        QPalette.ColorRole.ToolTipText: g["BACKGROUND"], QPalette.ColorRole.PlaceholderText: g["MUTED"],
        QPalette.ColorRole.Link: g["ACCENT"], QPalette.ColorRole.Mid: g["BORDER"],
    }
    for role, color in roles.items():
        p.setColor(role, QColor(color))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(g["MUTED"]))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(g["MUTED"]))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(g["MUTED"]))
    return p


def apply(app: QApplication, mode: str = "system", scale: float = 1.0) -> str:
    """Aplica el tema a toda la aplicación. Devuelve el modo efectivo."""
    global MODE, SCALE
    MODE = resolve(mode)
    SCALE = scale
    globals().update(DARK if MODE == "dark" else LIGHT)
    try:
        _write_arrows()
    except OSError:
        pass
    font = QFont(app.font())
    font.setPointSizeF(BASE_PT * scale)
    app.setFont(font)
    app.setPalette(qpalette())
    app.setStyleSheet(stylesheet())
    return MODE
