"""Componentes reutilizables: tarjetas, tiles, avatar, pasos, comparativas y vista de análisis."""

from __future__ import annotations

import statistics

from PySide6.QtCore import QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLabel, QLayout, QPushButton,
                               QScrollArea, QSizePolicy, QToolTip, QVBoxLayout, QWidget)

from ..features import SampleFeatures
from ..i18n import N_, _
from ..matcher import GLOBAL_SPEC, Profile
from ..traits import trait_values
from . import theme
from .charts import HBarChart, RadarChart, RhythmChart, key_name, rounded_bar, small_font
from .icons import IconLabel, icon
from .keyboard import KeyboardWidget


# --- utilidades de maquetación ----------------------------------------------

def label(text: str = "", name: str | None = None, wrap: bool = False, rich: bool = False) -> QLabel:
    lbl = QLabel(text)
    if name:
        lbl.setObjectName(name)
    lbl.setWordWrap(wrap)
    if rich:
        lbl.setTextFormat(Qt.TextFormat.RichText)
    return lbl


def card(status: str | None = None, margins: int = 18) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    if status:
        frame.setProperty("status", status)
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(margins, margins - 2, margins, margins - 2)
    lay.setSpacing(8)
    return frame, lay


def set_status(frame: QWidget, status: str | None) -> None:
    """Cambia la propiedad 'status' y fuerza que la hoja de estilos se reaplique."""
    frame.setProperty("status", status or "")
    frame.style().unpolish(frame)
    frame.style().polish(frame)


def card_header(title: str, icon: str | None = None, subtitle: str | None = None) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(8)
    if icon:
        lay.addWidget(IconLabel(icon, "TEXT_2", 18))
    lay.addWidget(label(title, "section"))
    lay.addStretch(1)
    if subtitle:
        lay.addWidget(label(subtitle, "small"))
    return w


def scroll(widget: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setWidget(widget)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    return area


def page_widget(margins: int = 28) -> tuple[QWidget, QVBoxLayout]:
    w = QWidget()
    w.setObjectName("page")
    lay = QVBoxLayout(w)
    lay.setContentsMargins(margins, 22, margins, 22)
    lay.setSpacing(14)
    return w, lay


def page_title(title: str, subtitle: str = "", icon: str | None = None) -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(2)
    row = QHBoxLayout()
    row.setSpacing(10)
    if icon:
        row.addWidget(IconLabel(icon, "ACCENT", 26))
    row.addWidget(label(title, "title"))
    row.addStretch(1)
    lay.addLayout(row)
    if subtitle:
        lay.addWidget(label(subtitle, "subtitle", wrap=True))
    return w


class HBox(QWidget):
    def __init__(self, *widgets, stretch_end=True, spacing: int = 8, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(spacing)
        for w in widgets:
            lay.addWidget(w)
        if stretch_end:
            lay.addStretch(1)
        self.layout_ = lay



class FlowLayout(QLayout):
    """Como una fila horizontal, pero lo que no cabe pasa a la línea siguiente."""

    def __init__(self, parent=None, spacing: int = 8):
        super().__init__(parent)
        self._items = []
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(spacing)

    def addItem(self, item):
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._place(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect: QRect):
        super().setGeometry(rect)
        self._place(rect, apply=True)

    def sizeHint(self) -> QSize:
        """Todo en una línea."""
        visible = [i.sizeHint() for i in self._items if not i.isEmpty()]
        width = sum(s.width() for s in visible) + self.spacing() * max(0, len(visible) - 1)
        return QSize(width, max((s.height() for s in visible), default=0))

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            if not item.isEmpty():
                size = size.expandedTo(item.minimumSize())
        return size

    def _place(self, rect: QRect, apply: bool) -> int:
        x, y, line = rect.x(), rect.y(), 0
        for item in self._items:
            if item.isEmpty():
                continue
            hint = item.sizeHint()
            if x > rect.x() and x + hint.width() > rect.right() + 1:
                x, y, line = rect.x(), y + line + self.spacing(), 0
            if apply:
                item.setGeometry(QRect(x, y, hint.width(), hint.height()))
            x += hint.width() + self.spacing()
            line = max(line, hint.height())
        return y + line - rect.y()


class FlowBox(QWidget):
    """Fila de botones que se reparte en varias líneas si no cabe (los textos cambian con el idioma)."""

    def __init__(self, *widgets, spacing: int = 8, parent=None):
        super().__init__(parent)
        lay = FlowLayout(self, spacing)
        for w in widgets:
            lay.addWidget(w)

def button(text: str, icon_name: str | None = None, kind: str | None = None) -> QPushButton:
    b = QPushButton(text)
    if kind:
        b.setObjectName(kind)
    if icon_name:
        b.setProperty("icon_name", icon_name)
        refresh_button_icon(b)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


def refresh_button_icon(b: QPushButton) -> None:
    name = b.property("icon_name")
    if not name:
        return
    kind = b.objectName()
    col = theme.ON_ACCENT if kind == "primary" else theme.BAD if kind == "danger" else theme.TEXT_2
    b.setIcon(icon(name, col, col, 18))


def primary(text: str, icon_name: str | None = None) -> QPushButton:
    return button(text, icon_name, "primary")


def notify(widget: QWidget, text: str, kind: str = "good") -> None:
    """Muestra un aviso no bloqueante en la ventana principal."""
    win = widget.window()
    if hasattr(win, "toast"):
        win.toast(text, kind)


# --- tiles y métricas ------------------------------------------------------

class Tile(QFrame):
    """Indicador con icono, valor grande, etiqueta y texto secundario."""

    def __init__(self, icon_name: str | None, title: str, value: str = "—", sub: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("tile")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(12)
        if icon_name:
            self.icon = IconLabel(icon_name, "ACCENT", 26)
            lay.addWidget(self.icon, alignment=Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(1)
        self.value = label(value, "tileValue")
        self.title = label(title, "tileLabel", wrap=True)
        self.sub = label(sub, "tileSub", wrap=True)
        col.addWidget(self.value)
        col.addWidget(self.title)
        col.addWidget(self.sub)
        lay.addLayout(col, 1)
        self.sub.setVisible(bool(sub))

    def set(self, value: str, sub: str | None = None, tip: str | None = None) -> None:
        self.value.setText(value)
        if sub is not None:
            self.sub.setText(sub)
            self.sub.setVisible(bool(sub))
        if tip:
            self.setToolTip(tip)


class MetricsGrid(QWidget):
    """Cuadrícula de tiles sin icono."""

    def __init__(self, columns: int = 4, parent=None):
        super().__init__(parent)
        self.columns = columns
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(10)

    def set_items(self, items: list[tuple[str, str, str]]) -> None:
        """items: (valor, etiqueta, ayuda)."""
        while self.grid.count():
            w = self.grid.takeAt(0).widget()
            if w:
                w.hide()
                w.deleteLater()
        for i, (value, title, tip) in enumerate(items):
            tile = Tile(None, title, value)
            tile.setToolTip(tip)
            self.grid.addWidget(tile, i // self.columns, i % self.columns)


def metric_items(m: dict) -> list[tuple[str, str, str]]:
    return [
        (f"{m['wpm']:.0f}", _("Palabras por minuto"), _("Velocidad bruta (5 caracteres = 1 palabra).")),
        (f"{m['net_wpm']:.0f}", _("PPM netas"), _("Velocidad descontando errores sin corregir.")),
        (f"{m['accuracy']:.1f} %", _("Precisión final"), _("Coincidencia del texto final con el original.")),
        (f"{m['duration_s']:.1f} s", _("Duración"), _("Desde la primera pulsación hasta la última.")),
        (f"{m['errors_committed']}", _("Errores cometidos"), _("Caracteres incorrectos tecleados (corregidos o no).")),
        (f"{m['errors_corrected']}", _("Errores corregidos"), _("Errores que se corrigieron con retroceso.")),
        (f"{m['backspaces']}", _("Retrocesos"), _("Pulsaciones de la tecla de borrar.")),
        (f"{m['pauses']}", _("Pausas > 1,5 s"), _("Interrupciones largas del ritmo.")),
        (f"{m['dwell_mean']:.0f} ms", _("Pulsación media"), _("Tiempo medio que se mantiene pulsada una tecla.")),
        (f"{m['flight_mean']:.0f} ms", _("Vuelo medio"), _("Tiempo entre soltar una tecla y pulsar la siguiente.")),
        (f"{m['rollover_pct']:.0f} %", _("Solapamiento"), _("Veces que se pulsa la siguiente tecla antes de soltar la anterior.")),
        (f"{max(m['consistency'], 0):.0f} %", _("Regularidad"), _("100 % = ritmo perfectamente constante.")),
        (f"{m['shift_left']} / {m['shift_right']}", _("Shift izq. / der."), _("Qué shift se usa para las mayúsculas.")),
        (f"{m['keystrokes']}", _("Pulsaciones"), _("Total de teclas pulsadas (incluye shift y retroceso).")),
        (f"{m['autorepeats']}", _("Autorrepeticiones"), _("Veces que una tecla se mantuvo pulsada hasta repetirse.")),
        (f"{m['blocked']}", _("Acciones bloqueadas"), _("Pegar, flechas, ratón… (no permitidos).")),
    ]


# --- pequeños elementos visuales --------------------------------------------

class Badge(QLabel):
    """Etiqueta de estado con color suave (siempre con texto, nunca solo color)."""

    def __init__(self, text: str = "", level: str = "good", parent=None):
        super().__init__(text, parent)
        self.setObjectName("badge")
        self.set(text, level)

    def set(self, text: str, level: str) -> None:
        self.level = level
        self.setText(text)
        self.restyle()

    def restyle(self) -> None:
        self.setStyleSheet(f"QLabel#badge {{ background: {theme.status_soft(self.level)}; "
                           f"color: {theme.status_color(self.level)}; }}")


class Banner(QLabel):
    """Aviso en línea (bloq mayús, foco perdido...)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("banner")
        self.setVisible(False)
        self.level = "warn"

    def show_text(self, text: str, level: str = "warn") -> None:
        self.level = level
        self.setText(text)
        self.setStyleSheet(f"QLabel#banner {{ background: {theme.status_soft(level)}; "
                           f"color: {theme.status_color(level)}; }}")
        self.setVisible(True)


class Avatar(QWidget):
    """Círculo con iniciales; el color sigue a la persona (orden de alta)."""

    def __init__(self, size: int = 40, parent=None):
        super().__init__(parent)
        self.text = "?"
        self.index = -1
        self.setFixedSize(size, size)

    def set_user(self, name: str, index: int) -> None:
        parts = [p for p in name.split() if p]
        self.text = ("".join(p[0] for p in parts[:2]) or "?").upper()
        self.index = index
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor(theme.category(self.index))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawEllipse(self.rect().adjusted(1, 1, -1, -1))
        lum = 0.2126 * bg.redF() + 0.7152 * bg.greenF() + 0.0722 * bg.blueF()
        p.setPen(QColor("#0b0b0b") if lum > 0.55 else QColor("#ffffff"))
        f = QFont(self.font())
        f.setBold(True)
        f.setPixelSize(int(self.height() * 0.38))
        p.setFont(f)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text)


class Stepper(QWidget):
    """Indicador de pasos: ● completado, ◉ actual, ○ pendiente."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.steps: list[str] = []
        self.current = 0
        self.setFixedHeight(54)

    def set_steps(self, steps: list[str], current: int) -> None:
        self.steps, self.current = steps, current
        self.update()

    def paintEvent(self, _event):
        if not self.steps:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(small_font(self, 9))
        n = len(self.steps)
        w = self.width()
        slot = w / n
        r = 11
        cy = 15
        for i in range(n - 1):
            x1, x2 = slot * i + slot / 2 + r + 4, slot * (i + 1) + slot / 2 - r - 4
            p.setPen(QPen(QColor(theme.ACCENT if i < self.current else theme.BORDER_STRONG), 2))
            p.drawLine(int(x1), cy, int(x2), cy)
        for i, name in enumerate(self.steps):
            cx = slot * i + slot / 2
            rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
            if i < self.current:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(theme.ACCENT))
                p.drawEllipse(rect)
                p.setPen(QPen(QColor(theme.ON_ACCENT), 2))
                p.drawLine(int(cx - 4.5), cy, int(cx - 1), cy + 4)
                p.drawLine(int(cx - 1), cy + 4, int(cx + 5), cy - 4)
            elif i == self.current:
                p.setPen(QPen(QColor(theme.ACCENT), 2))
                p.setBrush(QColor(theme.ACCENT_SOFT))
                p.drawEllipse(rect)
                p.setPen(QColor(theme.TEXT))
                p.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(i + 1))
            else:
                p.setPen(QPen(QColor(theme.BORDER_STRONG), 2))
                p.setBrush(QColor(theme.SURFACE))
                p.drawEllipse(rect)
                p.setPen(QColor(theme.MUTED))
                p.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(i + 1))
            p.setPen(QColor(theme.TEXT if i == self.current else theme.TEXT_2))
            p.drawText(QRectF(cx - slot / 2, cy + r + 4, slot, 18), Qt.AlignmentFlag.AlignCenter, name)


class _SegmentButton(QPushButton):
    """Reserva el ancho del texto en negrita, el del botón marcado (si no, se corta al marcarlo)."""

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        bold = QFont(self.font())
        bold.setWeight(QFont.Weight.DemiBold)
        extra = QFontMetrics(bold).horizontalAdvance(self.text()) - self.fontMetrics().horizontalAdvance(self.text())
        return QSize(hint.width() + max(0, extra), hint.height())

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()


class Segmented(QWidget):
    """Grupo de botones excluyentes."""

    changed = Signal(int)

    def __init__(self, options: list[str], parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for i, text in enumerate(options):
            b = _SegmentButton(text)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            self.group.addButton(b, i)
            lay.addWidget(b)
        self.group.button(0).setChecked(True)
        self.group.idClicked.connect(self.changed)
        lay.addStretch(1)

    def index(self) -> int:
        return self.group.checkedId()


# --- comparación de rasgos (explicación del resultado) ----------------------

FEATURE_FMT = {
    "dwell_med": ("ms", 1, 0), "dwell_iqr": ("ms", 1, 0), "dd_med": ("ms", 1, 0), "dd_iqr": ("ms", 1, 0),
    "ud_med": ("ms", 1, 0), "overlap": ("%", 100, 0), "space_dwell": ("ms", 1, 0),
    "dd_to_space": ("ms", 1, 0), "dd_from_space": ("ms", 1, 0), "speed_cpm": ("p/min", 1, 0),
    "pause_rate": ("/100", 1, 1), "bs_rate": ("/100", 1, 1), "err_rate": ("/100", 1, 1),
    "shift_right": ("%", 100, 0), "shift_lead": ("ms", 1, 0), "shift_hold": ("ms", 1, 0),
    "bs_dwell": ("ms", 1, 0), "bs_latency": ("ms", 1, 0),
}


def fmt_feature(key: str, value: float) -> str:
    unit, mult, dec = FEATURE_FMT.get(key, ("", 1, 2))
    return f"{value * mult:.{dec}f} {unit}".strip()


def similarity_level(z: float) -> tuple[str, str]:
    if z < 1.0:
        return "good", _("similar")
    if z < 2.0:
        return "warn", _("algo distinto")
    return "bad", _("muy distinto")


class SimilarityList(QWidget):
    """Lista de rasgos con barra de similitud y su estado en texto."""

    ROW = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows: list[tuple[str, str, str, float]] = []
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_data(self, f: SampleFeatures, profile: Profile, who: str) -> None:
        zg = profile.z_scores(f)[0]
        rows = []
        for key, z in sorted(zg.items(), key=lambda kv: -kv[1]):
            mu = profile.global_stats[key][0]
            rows.append((_(GLOBAL_SPEC[key][3]), fmt_feature(key, f.globals[key]), fmt_feature(key, mu), z))
        self.rows = rows
        self.who = who
        self.setFixedHeight(int(max(len(rows), 1) * self.ROW * max(theme.SCALE, 1.0) ** 0.5 + 6))
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(small_font(self, 9.5))
        if not self.rows:
            p.setPen(QColor(theme.MUTED))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, _("Sin datos suficientes"))
            return
        fm = p.fontMetrics()
        name_w = max(fm.horizontalAdvance(r[0]) for r in self.rows) + 16
        status_w = max(fm.horizontalAdvance(similarity_level(z)[1]) for z in (0, 1.5, 3)) + 18
        values_w = max(fm.horizontalAdvance(f"{r[1]} · {r[2]}") for r in self.rows) + 16
        bar_x = name_w
        bar_w = max(60, self.width() - name_w - status_w - values_w - 8)
        row_h = (self.height() - 6) / len(self.rows)
        for i, (name, mine, theirs, z) in enumerate(self.rows):
            y = 3 + i * row_h
            level, text = similarity_level(z)
            sim = max(0.04, 1 - z / 3)
            p.setPen(QColor(theme.TEXT_2))
            p.drawText(QRectF(0, y, name_w - 10, row_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                       name)
            track = QRectF(bar_x, y + row_h / 2 - 4, bar_w, 8)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(theme.GRID))
            p.drawRoundedRect(track, 4, 4)
            rounded_bar(p, QRectF(bar_x, track.top(), bar_w * sim, 8), theme.status_color(level))
            p.setPen(QColor(theme.status_color(level)))
            p.drawText(QRectF(bar_x + bar_w + 10, y, status_w, row_h), Qt.AlignmentFlag.AlignVCenter, text)
            p.setPen(QColor(theme.MUTED))
            p.drawText(QRectF(bar_x + bar_w + 10 + status_w, y, values_w, row_h), Qt.AlignmentFlag.AlignVCenter,
                       f"{mine} · {theirs}")

    def mouseMoveEvent(self, e):
        if not self.rows:
            return
        row_h = (self.height() - 6) / len(self.rows)
        i = int((e.position().y() - 3) // row_h)
        if 0 <= i < len(self.rows):
            name, mine, theirs, z = self.rows[i]
            QToolTip.showText(e.globalPosition().toPoint(),
                              f"<b>{name}</b><br>" + _("Esta muestra: {value}", value=mine) + "<br>"
                              + _("Perfil de {name}: {value}", name=self.who, value=theirs) + "<br>"
                              + _("Desviación: {z} veces la variación habitual", z=f"{z:.1f}"), self)


def radar_series(metrics_a: list[dict], name_a: str, metrics_b: list[dict] | None = None,
                 name_b: str = "") -> tuple[list[str], list]:
    a = trait_values(metrics_a)
    axes = [_(t.name) for t, _raw, _norm in a]
    series = [(name_a, [n for _t, _raw, n in a], [f"{raw:.0f} {_(t.unit)}" for t, raw, _norm in a], theme.SERIES_1)]
    if metrics_b:
        b = trait_values(metrics_b)
        series.append((name_b, [n for _t, _raw, n in b], [f"{raw:.0f} {_(t.unit)}" for t, raw, _norm in b], theme.SERIES_2))
    return axes, series


# --- vista de análisis ------------------------------------------------------

def dwell_rows(f: SampleFeatures, profile: Profile | None = None, top: int = 12):
    counts = sorted(((len(v), k) for k, v in f.dwell.items() if len(v) >= 2), reverse=True)
    rows = []
    for _count, k in counts[:top]:
        prof = profile.dwell_stats.get(k, (None,))[0] if profile else None
        rows.append((k, statistics.median(f.dwell[k]), prof))
    return rows


def digraph_text(pairs) -> str:
    if not pairs:
        return "—"
    return "&nbsp;&nbsp; ".join(f"<b>{key_name(a)}{key_name(b)}</b> {v:.0f} ms" for (a, b), v in pairs)


class HeatmapCard(QFrame):
    """Tarjeta con el teclado en modo mapa de calor y selector de medida."""

    MODES = (N_("Tiempo de pulsación"), N_("Frecuencia"), N_("Errores"))

    def __init__(self, title: str | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.addWidget(card_header(title or _("Mapa de calor del teclado"), "keyboard"))
        self.selector = Segmented([_(m) for m in self.MODES])
        self.selector.changed.connect(lambda _: self._show())
        lay.addWidget(self.selector)
        self.keyboard = KeyboardWidget()
        lay.addWidget(self.keyboard)
        self.dwell: dict[str, list[float]] = {}
        self.errors: dict[str, int] = {}

    def set_data(self, dwell: dict[str, list[float]], errors: dict[str, int], layout: str) -> None:
        self.dwell, self.errors = dwell, errors
        self.keyboard.set_layout(layout)
        self._show()

    def _show(self):
        i = self.selector.index()
        kb = self.keyboard
        if i == 0:
            kb.set_heat({k: statistics.median(v) for k, v in self.dwell.items() if v},
                        _("pulsación mediana"), "ms")
        elif i == 1:
            kb.set_heat({k: float(len(v)) for k, v in self.dwell.items() if v}, _("pulsaciones"), "",
                        aggregate="sum")
        else:
            kb.set_heat({k: float(v) for k, v in self.errors.items()}, _("errores"), "", aggregate="sum")


class AnalysisView(QWidget):
    """Análisis completo de una muestra: métricas, ritmo, teclado y dígrafos."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        self.metrics = MetricsGrid(4)
        lay.addWidget(self.metrics)

        c1, l1 = card()
        l1.addWidget(card_header(_("Ritmo de escritura"), "activity"))
        l1.addWidget(label(_("Intervalo entre pulsaciones consecutivas. Los picos son dudas o pausas; "
                             "una línea plana indica un ritmo regular."), "subtitle", wrap=True))
        self.rhythm = RhythmChart()
        l1.addWidget(self.rhythm)
        lay.addWidget(c1)

        self.heat = HeatmapCard()
        lay.addWidget(self.heat)

        c2, l2 = card()
        l2.addWidget(card_header(_("Tiempo de pulsación por tecla"), "clock"))
        self.dwell = HBarChart()
        l2.addWidget(self.dwell)
        lay.addWidget(c2)

        c3, l3 = card()
        l3.addWidget(card_header(_("Combinaciones de teclas (dígrafos)"), "bolt"))
        self.fast = label(wrap=True, rich=True)
        self.slow = label(wrap=True, rich=True)
        self.errors = label(wrap=True, rich=True)
        for w in (self.fast, self.slow, self.errors):
            l3.addWidget(w)
        lay.addWidget(c3)

    def show_features(self, f: SampleFeatures, profile: Profile | None = None,
                      names: tuple[str, str] | None = None, layout: str = "es") -> None:
        names = names or (_("Esta muestra"), _("Perfil"))
        m = f.metrics
        self.metrics.set_items(metric_items(m))
        self.rhythm.set_data(f.rhythm)
        self.heat.set_data(f.dwell, m.get("error_counts", {}), layout)
        self.dwell.set_data(dwell_rows(f, profile), names if profile else (names[0], ""))
        self.fast.setText(_("Más rápidas:") + "&nbsp; " + digraph_text(m["fastest_digraphs"]))
        self.slow.setText(_("Más lentas:") + "&nbsp; " + digraph_text(m["slowest_digraphs"]))
        errs = m["error_chars"]
        self.errors.setText(_("Caracteres donde más te equivocas:") + "&nbsp; " + (
            "&nbsp;&nbsp; ".join(f"<b>{_('espacio') if c == ' ' else c}</b> ×{n}" for c, n in errs)
            if errs else _("ninguno")))


def separator() -> QFrame:
    line = QFrame()
    line.setObjectName("separator")
    line.setFrameShape(QFrame.Shape.HLine)
    return line


__all__ = [
    "AnalysisView", "Avatar", "Badge", "Banner", "HBox", "HeatmapCard", "MetricsGrid", "RadarChart",
    "Segmented", "SimilarityList", "Stepper", "Tile", "button", "card", "card_header", "digraph_text",
    "dwell_rows", "label", "metric_items", "notify", "page_title", "page_widget", "primary",
    "radar_series", "refresh_button_icon", "scroll", "separator", "set_status",
]
