"""Teclado en pantalla: resalta las teclas pulsadas y dibuja mapas de calor."""

from __future__ import annotations

import unicodedata

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from . import theme
from ..i18n import N_, _
from .charts import key_name

# Cada fila: lista de (id de tecla, etiqueta visible, anchura en unidades). El id de una tecla de
# carácter es lo que escribe sin mayúsculas; las teclas especiales usan nombres fijos.
def _bottom(ctrl: str = "Ctrl", altgr: str = "AltGr", menu: str = "Menú") -> list[tuple[str, str, float]]:
    return [("ctrl", ctrl, 1.5), ("meta", "Win", 1.25), ("alt", "Alt", 1.25), ("space", "", 6.25),
            ("altgr", altgr, 1.25), ("menu", menu, 1.25), ("ctrl_r", ctrl, 2.25)]


def _row(keys: str, upper: bool = True) -> list[tuple[str, str, float]]:
    return [(k, k.upper() if upper and k.isalpha() else k, 1.0) for k in keys]


def _iso(top: list, second: str, home: str, bottom: str, *, tab="Tab", enter="Intro", caps="Bloq",
         shift="Shift", ctrl="Ctrl", altgr="AltGr", menu="Menú") -> list:
    """Teclado ISO de 105 teclas: la fila de inicio lleva 12 teclas y la de abajo empieza con «<»."""
    return [
        top + [("backspace", "⌫", 2.0)],
        [("tab", tab, 1.5)] + _row(second) + [("enter", enter, 1.5)],
        [("capslock", caps, 1.75)] + _row(home) + [("enter2", "", 1.25)],
        [("shift_l", shift, 1.25)] + _row(bottom) + [("shift_r", shift, 2.75)],
        _bottom(ctrl, altgr, menu),
    ]


LAYOUTS = {
    "es": {
        "name": N_("Español (España)"),
        "rows": _iso(_row("º1234567890'¡"), "qwertyuiop`+", "asdfghjklñ´ç", "<zxcvbnm,.-"),
        # carácter producido -> tecla base
        "shift": dict(zip("ª!\"·$%&/()=?¿^*¨ÇÑ>;:_", "º1234567890'¡`+´çñ<,.-")),
        "altgr": dict(zip("\\|@#~€¬[]{}", "º1234e6`+´ç")),
        "dead": {"dead_acute": "´", "dead_diaeresis": "´", "dead_grave": "`", "dead_circumflex": "`",
                 "dead_tilde": "4"},
    },
    "us": {
        "name": N_("Inglés (EE. UU.)"),
        "rows": [
            _row("`1234567890-=") + [("backspace", "⌫", 2.0)],
            [("tab", "Tab", 1.5)] + _row("qwertyuiop[]") + [("\\", "\\", 1.5)],
            [("capslock", "Caps", 1.75)] + _row("asdfghjkl;'") + [("enter", "Enter", 2.25)],
            [("shift_l", "Shift", 2.25)] + _row("zxcvbnm,./") + [("shift_r", "Shift", 2.75)],
            _bottom(altgr="Alt", menu="Menu"),
        ],
        "shift": dict(zip("~!@#$%^&*()_+{}|:\"<>?", "`1234567890-=[]\\;',./")),
        "altgr": {},
        "dead": {"dead_acute": "'", "dead_grave": "`", "dead_diaeresis": "'", "dead_circumflex": "6",
                 "dead_tilde": "`"},
    },
    "fr": {
        "name": N_("Francés (AZERTY)"),
        "rows": _iso(_row("²&é\"'(-è_çà)=", upper=False), "azertyuiop^$", "qsdfghjklmù*", "<wxcvbn,;:!",
                     enter="Entrée", caps="Verr.", shift="Maj", altgr="Alt Gr", menu="Menu"),
        "shift": dict(zip("1234567890°+¨£%µ>?./§", "&é\"'(-è_çà)=^$ù*<,;:!")),
        "altgr": dict(zip("~#{[|`\\^@]}€¤", "é\"'(-è_çà)=e$")),
        "dead": {"dead_circumflex": "^", "dead_diaeresis": "^", "dead_grave": "è", "dead_tilde": "é"},
    },
    "de": {
        "name": N_("Alemán (QWERTZ)"),
        "rows": _iso(_row("^1234567890ß´"), "qwertzuiopü+", "asdfghjklöä#", "<yxcvbnm,.-",
                     enter="Enter", caps="Feststell", shift="Umschalt", ctrl="Strg", altgr="Alt Gr", menu="Menü"),
        "shift": dict(zip("°!\"§$%&/()=?`*'>;:_ÜÖÄ", "^1234567890ß´+#<,.-üöä")),
        "altgr": dict(zip("²³{[]}\\@€~|µ", "237890ßqe+<m")),
        "dead": {"dead_circumflex": "^", "dead_acute": "´", "dead_grave": "´", "dead_tilde": "+"},
    },
    "it": {
        "name": N_("Italiano"),
        "rows": _iso(_row("\\1234567890'ì"), "qwertyuiopè+", "asdfghjklòàù", "<zxcvbnm,.-",
                     enter="Invio", caps="Bloc", shift="Maiusc", altgr="Alt Gr", menu="Menu"),
        "shift": dict(zip("|!\"£$%&/()=?^é*ç°§>;:_", "\\1234567890'ìè+òàù<,.-")),
        "altgr": dict(zip("[]@#€", "è+òàe")),
        "dead": {},
    },
    "pt": {
        "name": N_("Portugués (Portugal)"),
        "rows": _iso(_row("\\1234567890'«"), "qwertyuiop+´", "asdfghjklçº~", "<zxcvbnm,.-",
                     enter="Enter", caps="Caps", altgr="Alt Gr", menu="Menu"),
        "shift": dict(zip("|!\"#$%&/()=?»*`Çª^>;:_", "\\1234567890'«+´çº~<,.-")),
        "altgr": dict(zip("@£§{[]}€¨", "2347890e+")),
        "dead": {"dead_acute": "´", "dead_grave": "´", "dead_tilde": "~", "dead_circumflex": "~",
                 "dead_diaeresis": "+"},
    },
}
for _lay in LAYOUTS.values():   # teclas de cada distribución (para no confundir «ä» con «a», por ejemplo)
    _lay["keys"] = {key for row in _lay["rows"] for key, _label, _width in row}

_ALIASES = {"shift": "shift_l", "ctrl": "ctrl", "alt": "alt", "meta": "meta", "altgr": "altgr"}


def key_for(label: str, layout: str = "es") -> str | None:
    """Convierte una etiqueta de pulsación (o un carácter) en el id de su tecla física."""
    lay = LAYOUTS.get(layout, LAYOUTS["es"])
    if label in ("space", "backspace", "shift_l", "shift_r", "capslock", "enter"):
        return label
    if label in _ALIASES:
        return _ALIASES[label]
    if label in lay["dead"]:
        return lay["dead"][label]
    if label == " ":
        return "space"
    if len(label) != 1:
        return None
    ch = label
    if ch in lay["shift"]:
        return lay["shift"][ch]
    if ch in lay["altgr"]:
        return lay["altgr"][ch]
    low = ch.lower()
    if low in lay["keys"]:
        return low
    return "".join(c for c in unicodedata.normalize("NFD", low) if not unicodedata.combining(c)) or low


def _lerp(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(int(a.red() + (b.red() - a.red()) * t), int(a.green() + (b.green() - a.green()) * t),
                  int(a.blue() + (b.blue() - a.blue()) * t))


def _readable_on(bg: QColor) -> QColor:
    lum = 0.2126 * bg.redF() + 0.7152 * bg.greenF() + 0.0722 * bg.blueF()
    return QColor("#0b0b0b") if lum > 0.5 else QColor("#ffffff")


class KeyboardWidget(QWidget):
    """Teclado dibujado. Modo en vivo (teclas pulsadas) o mapa de calor (valor por tecla)."""

    ROWS_U = 5
    WIDTH_U = 15

    def __init__(self, layout: str = "es", parent=None):
        super().__init__(parent)
        self.layout_id = layout
        self.active: dict[str, int] = {}
        self.values: dict[str, float] = {}
        self.unit = "ms"
        self.value_name = ""
        self.decimals = 0
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(150)
        self._rects: list[tuple[QRectF, str, str]] = []

    def sizeHint(self) -> QSize:
        return QSize(640, 220)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, w: int) -> int:
        return int(min(w, 820) / self.WIDTH_U * self.ROWS_U + (34 if self.values else 6))

    def set_layout(self, layout: str) -> None:
        self.layout_id = layout if layout in LAYOUTS else "es"
        self.update()

    # -- modo en vivo -------------------------------------------------------
    def press(self, label: str) -> None:
        k = key_for(label, self.layout_id)
        if k:
            self.active[k] = self.active.get(k, 0) + 1
            self.update()

    def release(self, label: str) -> None:
        k = key_for(label, self.layout_id)
        if k and k in self.active:
            self.active[k] -= 1
            if self.active[k] <= 0:
                del self.active[k]
            self.update()

    def clear_active(self) -> None:
        self.active.clear()
        self.update()

    # -- mapa de calor ------------------------------------------------------
    def set_heat(self, values_by_label: dict[str, float], name: str, unit: str, decimals: int = 0,
                 aggregate: str = "mean") -> None:
        """Valores por etiqueta; las etiquetas de una misma tecla se combinan (media o suma)."""
        merged: dict[str, list[float]] = {}
        for label, v in values_by_label.items():
            k = key_for(label, self.layout_id)
            if k:
                merged.setdefault(k, []).append(v)
        self.values = {k: (sum(v) if aggregate == "sum" else sum(v) / len(v)) for k, v in merged.items()}
        self.value_name, self.unit, self.decimals = name, unit, decimals
        self.updateGeometry()
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        legend_h = 34 if self.values else 0
        avail_w = self.width() - 4
        u = min(avail_w / self.WIDTH_U, (self.height() - legend_h - 4) / self.ROWS_U)
        x0 = (self.width() - u * self.WIDTH_U) / 2
        y0 = 2
        gap = max(2.0, u * 0.08)
        font = QFont(self.font())
        font.setPointSizeF(max(7.0, min(11.0, u * 0.27)) * min(theme.SCALE, 1.2))
        p.setFont(font)

        vals = list(self.values.values())
        vmin, vmax = (min(vals), max(vals)) if vals else (0.0, 1.0)
        span = (vmax - vmin) or 1.0
        low, high = QColor(theme.HEAT_LOW), QColor(theme.HEAT_HIGH)
        base, edge = QColor(theme.KEY), QColor(theme.KEY_EDGE)
        self._rects = []
        for r, row in enumerate(LAYOUTS[self.layout_id]["rows"]):
            x = x0
            for key_id, text, width in row:
                rect = QRectF(x + gap / 2, y0 + r * u + gap / 2, width * u - gap, u - gap)
                x += width * u
                if key_id == "enter2":
                    key_id = "enter"
                fill = base
                txt = QColor(theme.TEXT_2)
                if key_id in self.values:
                    fill = _lerp(low, high, (self.values[key_id] - vmin) / span)
                    txt = _readable_on(fill)
                if key_id in self.active:
                    fill = QColor(theme.ACCENT)
                    txt = QColor(theme.ON_ACCENT)
                p.setPen(QPen(edge, 1))
                p.setBrush(fill)
                p.drawRoundedRect(rect, u * 0.12, u * 0.12)
                if text:
                    p.setPen(txt)
                    p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
                self._rects.append((rect, key_id, text))

        if self.values:
            ly = y0 + self.ROWS_U * u + 10
            lw = min(260.0, self.width() * 0.4)
            lx = (self.width() - lw) / 2
            grad = QLinearGradient(lx, 0, lx + lw, 0)
            grad.setColorAt(0, low)
            grad.setColorAt(1, high)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(grad)
            p.drawRoundedRect(QRectF(lx, ly, lw, 9), 4, 4)
            small = QFont(self.font())
            small.setPointSizeF(8.5 * theme.SCALE)
            p.setFont(small)
            p.setPen(QColor(theme.TEXT_2))
            p.drawText(QRectF(lx - 110, ly - 5, 104, 20), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       self._fmt(vmin))
            p.drawText(QRectF(lx + lw + 6, ly - 5, 260, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       f"{self._fmt(vmax)}  ({self.value_name})")

    def _fmt(self, v: float) -> str:
        return f"{v:.{self.decimals}f} {self.unit}".strip()

    def mouseMoveEvent(self, e):
        pos = e.position()
        for rect, key_id, text in self._rects:
            if rect.contains(pos):
                name = key_name(key_id) if not text or len(text) > 1 else text
                tip = f"<b>{name}</b>"
                if key_id in self.values:
                    tip += f"<br>{self.value_name}: {self._fmt(self.values[key_id])}"
                elif self.values:
                    tip += "<br>" + _("sin datos")
                QToolTip.showText(e.globalPosition().toPoint(), tip, self)
                return
        QToolTip.hideText()
