"""Iconos vectoriales propios (SVG en línea) coloreados según el tema."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QSizePolicy, QWidget

from .. import flags
from . import theme

_PATHS = {
    "dashboard": '<rect x="3" y="3" width="7.5" height="9" rx="1.8"/><rect x="13.5" y="3" width="7.5" height="5" rx="1.8"/>'
                 '<rect x="13.5" y="11" width="7.5" height="10" rx="1.8"/><rect x="3" y="15" width="7.5" height="6" rx="1.8"/>',
    "user_plus": '<circle cx="9" cy="8" r="4"/><path d="M2 21c0-3.9 3.1-7 7-7s7 3.1 7 7"/><path d="M19 8v6M16 11h6"/>',
    "scan": '<path d="M3 7.5V5a2 2 0 0 1 2-2h2.5M16.5 3H19a2 2 0 0 1 2 2v2.5M21 16.5V19a2 2 0 0 1-2 2h-2.5M7.5 21H5a2 2 0 0 1-2-2v-2.5"/>'
            '<circle cx="12" cy="10" r="3"/><path d="M7 17.5c1-2.4 2.9-3.6 5-3.6s4 1.2 5 3.6"/>',
    "users": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c0-3.6 2.9-6.5 6.5-6.5s6.5 2.9 6.5 6.5"/>'
             '<circle cx="17" cy="9" r="2.5"/><path d="M16.5 13.6c2.9.3 5 2.8 5 6.4"/>',
    "history": '<path d="M3.5 12a8.5 8.5 0 1 0 2.6-6.1"/><path d="M3 4v4.5h4.5"/><path d="M12 7.5V12l3 2"/>',
    "settings": '<path d="M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1"/>'
                '<circle cx="15" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="17" cy="18" r="2"/>',
    "keyboard": '<rect x="2" y="5" width="20" height="14" rx="2.5"/>'
                '<path d="M6 9.5h.01M9.5 9.5h.01M13 9.5h.01M16.5 9.5h.01M6 13h.01M18 9.5h.01M18 13h.01M8 16h8"/>'
                '<path d="M9.5 13h.01M13 13h.01M16.5 13h.01"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2'
           'M4.6 19.4L6 18M18 6l1.4-1.4"/>',
    "moon": '<path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a6.8 6.8 0 0 0 10.5 10.5z"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "check_circle": '<circle cx="12" cy="12" r="9"/><path d="M8 12.3l2.8 2.8L16.2 9.5"/>',
    "x_circle": '<circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M15 9l-6 6"/>',
    "alert": '<path d="M12 3.5L2.5 20h19z"/><path d="M12 10v4.2M12 17h.01"/>',
    "help": '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6v.4M12 16.8h.01"/>',
    "activity": '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    "shield": '<path d="M12 3l8 3v6c0 4.5-3.4 8.3-8 9-4.6-.7-8-4.5-8-9V6z"/><path d="M8.7 12l2.4 2.4 4.3-4.6"/>',
    "lock": '<rect x="4.5" y="10.5" width="15" height="10" rx="2"/><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3M12 14.5v2"/>',
    "download": '<path d="M12 4v11M7 10.5l5 5 5-5M4 20h16"/>',
    "upload": '<path d="M12 16V5M7 9.5l5-5 5 5M4 20h16"/>',
    "trash": '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
    "edit": '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13.5 6.5l4 4"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "refresh": '<path d="M20 11.5a8 8 0 1 0-2.3 5.6"/><path d="M20 4v7.5h-7.5"/>',
    "gauge": '<path d="M3.5 17a8.5 8.5 0 1 1 17 0"/><path d="M12 17l4-5.5"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/>',
    "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    "bolt": '<path d="M13 2.5L4.5 13.5H12L11 21.5l8.5-11H12z"/>',
    "file": '<path d="M14 3H6.5A1.5 1.5 0 0 0 5 4.5v15A1.5 1.5 0 0 0 6.5 21h11a1.5 1.5 0 0 0 1.5-1.5V8z"/><path d="M14 3v5h5"/>',
    "arrow_right": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "fingerprint": '<path d="M7.5 19.5c1-2 1.5-4.2 1.5-7.5a3 3 0 0 1 6 0c0 1.2-.1 2.4-.3 3.5"/>'
                   '<path d="M12 12c0 3.4-.7 6.3-2 8.5M4.5 16c.6-1.3 1-2.6 1-4a6.5 6.5 0 0 1 11.3-4.4"/>'
                   '<path d="M18.3 10.5c.1.5.2 1 .2 1.5 0 2.7-.4 5.3-1.4 7.5M14.4 20.5c.4-1 .7-2 .9-3"/>',
}


def svg(name: str, color: str, stroke: float = 2.0) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">{_PATHS[name]}</svg>')


def _dpr() -> float:
    screen = QGuiApplication.primaryScreen()
    return screen.devicePixelRatio() if screen else 1.0


def pixmap(name: str, color: str, size: int = 20, stroke: float = 2.0) -> QPixmap:
    dpr = max(_dpr(), 1.0)
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(QByteArray(svg(name, color, stroke).encode()))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(p, QRectF(0, 0, size * dpr, size * dpr))
    p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def icon(name: str, color: str | None = None, active: str | None = None, size: int = 20) -> QIcon:
    ic = QIcon()
    ic.addPixmap(pixmap(name, color or theme.TEXT_2, size), QIcon.Mode.Normal)
    ic.addPixmap(pixmap(name, active or color or theme.TEXT, size), QIcon.Mode.Selected)
    ic.addPixmap(pixmap(name, theme.MUTED, size), QIcon.Mode.Disabled)
    return ic


FLAG_SIZE = QSize(21, 14)


def flag_icon(code: str) -> QIcon:
    """Bandera de un idioma (ksb/flags.py) con las esquinas redondeadas y un borde suave."""
    dpr = max(_dpr(), 1.0)
    w, h = FLAG_SIZE.width() * dpr, FLAG_SIZE.height() * dpr
    pm = QPixmap(int(w), int(h))
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    shape = QPainterPath()
    shape.addRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 2 * dpr, 2 * dpr)
    p.setClipPath(shape)
    QSvgRenderer(QByteArray(flags.svg(code).encode())).render(p, QRectF(0, 0, w, h))
    p.setClipping(False)
    p.setPen(QPen(QColor(0, 0, 0, 45), dpr))
    p.drawPath(shape)
    p.end()
    pm.setDevicePixelRatio(dpr)
    return QIcon(pm)


def blank_flag() -> QIcon:
    """Hueco del tamaño de una bandera, para alinear las opciones sin bandera («Automático»…)."""
    pm = QPixmap(FLAG_SIZE)
    pm.fill(Qt.GlobalColor.transparent)
    return QIcon(pm)


def app_icon() -> QIcon:
    """Icono de la aplicación: teclado blanco sobre cuadrado azul redondeado."""
    ic = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        ic.addPixmap(app_pixmap(size))
    return ic


def app_pixmap(size: int) -> QPixmap:
    body = _PATHS["keyboard"]
    data = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            f'<rect x="0.5" y="0.5" width="23" height="23" rx="5.5" fill="#2a78d6"/>'
            f'<g transform="translate(3.6 3.6) scale(0.7)" fill="none" stroke="#ffffff" stroke-width="2.2" '
            f'stroke-linecap="round" stroke-linejoin="round">{body}</g></svg>')
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(data.encode())).render(p, QRectF(0, 0, size, size))
    p.end()
    return pm


class IconLabel(QWidget):
    """Icono que se repinta con el color actual del tema (role = nombre de color del tema)."""

    def __init__(self, name: str, role: str = "TEXT_2", size: int = 20, parent=None):
        super().__init__(parent)
        self.name, self.role, self._size = name, role, size
        self.setFixedSize(QSize(size, size))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def set_icon(self, name: str, role: str | None = None) -> None:
        self.name = name
        if role:
            self.role = role
        self.update()

    def paintEvent(self, _event):
        color = getattr(theme, self.role, self.role)
        p = QPainter(self)
        p.drawPixmap(0, 0, pixmap(self.name, color, self._size))
