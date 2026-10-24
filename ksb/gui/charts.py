"""Gráficos dibujados con QPainter (sin dependencias extra).

Todos leen los colores del tema al pintar, tienen leyenda cuando hay dos
series y muestran un tooltip con los valores al pasar el ratón.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from ..i18n import N_, _
from . import theme

KEY_NAMES = {"space": N_("espacio"), "backspace": N_("retroceso"), "shift_l": N_("shift izq."),
             "shift_r": N_("shift der."), "shift": "shift", "dead_acute": N_("tilde ´"), "dead_grave": N_("acento `"),
             "dead_diaeresis": N_("diéresis ¨"), "dead_circumflex": N_("circunflejo ^"),
             "dead_tilde": N_("virgulilla ~"), "capslock": N_("bloq mayús"), "altgr": "AltGr", "ctrl": "ctrl",
             "alt": "alt", "meta": "win"}


def key_name(label: str) -> str:
    return _(KEY_NAMES[label]) if label in KEY_NAMES else label


def nice_max(v: float) -> float:
    if v <= 0:
        return 1.0
    exp = 10 ** math.floor(math.log10(v))
    for m in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if v <= m * exp:
            return m * exp
    return v


def small_font(widget: QWidget, size: float = 9.0) -> QFont:
    f = QFont(widget.font())
    f.setPointSizeF(size * theme.SCALE)
    return f


def color(c: str, alpha: float = 1.0) -> QColor:
    q = QColor(c)
    q.setAlphaF(alpha)
    return q


def draw_legend(p: QPainter, x: float, y: float, items: list[tuple[str, str]]) -> float:
    """Dibuja una leyenda horizontal; devuelve la x final."""
    fm = p.fontMetrics()
    for name, col in items:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(col))
        p.drawRoundedRect(QRectF(x, y + 2, 11, 11), 3, 3)
        p.setPen(QColor(theme.TEXT_2))
        p.drawText(QRectF(x + 17, y - 3, fm.horizontalAdvance(name) + 4, 20),
                   Qt.AlignmentFlag.AlignVCenter, name)
        x += 32 + fm.horizontalAdvance(name)
    return x


def rounded_bar(p: QPainter, rect: QRectF, col: str, radius: float = 4.0, side: str = "right") -> None:
    """Barra con el extremo de datos redondeado y anclada recta a la línea base."""
    r = max(0.0, min(radius, rect.width() / 2, rect.height() / 2))
    path = QPainterPath()
    path.addRoundedRect(rect, r, r)
    p.fillPath(path, QColor(col))
    if side == "right":      # barras horizontales: base a la izquierda
        p.fillRect(QRectF(rect.left(), rect.top(), r, rect.height()), QColor(col))
    else:                    # barras verticales: base abajo
        p.fillRect(QRectF(rect.left(), rect.bottom() - r, rect.width(), r), QColor(col))


class _HoverMixin:
    """Zonas sensibles con tooltip."""

    def _hover_init(self):
        self._hits: list[tuple[QRectF, str]] = []
        self.setMouseTracking(True)

    def mouseMoveEvent(self, e):  # noqa: N802
        for rect, tip in self._hits:
            if rect.contains(e.position()):
                QToolTip.showText(e.globalPosition().toPoint(), tip, self)
                return
        QToolTip.hideText()


# ---------------------------------------------------------------------------
class HBarChart(_HoverMixin, QWidget):
    """Barras horizontales con una o dos series (p. ej. pulsación por tecla)."""

    ROW = 24

    def __init__(self, unit: str = "ms", label_fn=key_name, decimals: int = 0, parent=None):
        super().__init__(parent)
        self._hover_init()
        self.unit, self.label_fn, self.decimals = unit, label_fn, decimals
        self.rows: list[tuple[str, float | None, float | None]] = []
        self.names: tuple[str, str] = ("", "")
        self.colors: list[str] | None = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(60)

    @property
    def two(self) -> bool:
        return any(r[2] is not None for r in self.rows)

    def set_data(self, rows, names=None, colors: list[str] | None = None) -> None:
        self.rows, self.names, self.colors = list(rows), names or (_("Esta muestra"), _("Perfil")), colors
        row_h = (self.ROW + (10 if self.two else 0)) * max(theme.SCALE, 1.0) ** 0.5
        self.setFixedHeight(int((34 if self.two else 8) + max(len(self.rows), 1) * row_h + 28))
        self.update()

    def _fmt(self, v):
        return f"{v:.{self.decimals}f} {self.unit}".strip()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(small_font(self))
        self._hits = []
        if not self.rows:
            p.setPen(QColor(theme.MUTED))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, _("Sin datos suficientes"))
            return
        fm = p.fontMetrics()
        left = 12 + max(fm.horizontalAdvance(self.label_fn(r[0])) for r in self.rows)
        two = self.two
        top = 34 if two else 8
        if two:
            draw_legend(p, left, 6, [(self.names[0], theme.SERIES_1), (self.names[1], theme.SERIES_2)])
        right = self.width() - 44
        width = max(right - left, 10)
        values = [v for r in self.rows for v in r[1:] if v is not None]
        vmax = nice_max(max(values) if values else 1)
        row_h = (self.height() - top - 28) / len(self.rows)
        bottom = top + row_h * len(self.rows)
        for i in range(5):
            gx = left + width * i / 4
            p.setPen(QPen(QColor(theme.GRID), 1))
            p.drawLine(QPointF(gx, top), QPointF(gx, bottom))
            p.setPen(QColor(theme.MUTED))
            p.drawText(QRectF(gx - 40, bottom + 4, 80, 18), Qt.AlignmentFlag.AlignCenter, self._fmt(vmax * i / 4))
        bar_h = min(10 if two else 14, (row_h - 6) / (2 if two else 1))
        for i, (lbl, a, b) in enumerate(self.rows):
            y = top + i * row_h
            p.setPen(QColor(theme.TEXT_2))
            p.drawText(QRectF(0, y, left - 8, row_h), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       self.label_fn(lbl))
            row_color = self.colors[i] if self.colors else theme.SERIES_1
            bars = [(a, row_color, self.names[0])]
            if two:
                bars.append((b, theme.SERIES_2, self.names[1]))
            yy = y + (row_h - bar_h * len(bars) - 2 * (len(bars) - 1)) / 2
            for value, col, _name in bars:
                if value is not None and value > 0:
                    rounded_bar(p, QRectF(left, yy, max(3.0, width * value / vmax), bar_h), col)
                yy += bar_h + 2
            if not two and a is not None:
                p.setPen(QColor(theme.TEXT_2))
                x_end = left + max(3.0, width * a / vmax) + 6
                p.drawText(QRectF(x_end, y, 80, row_h), Qt.AlignmentFlag.AlignVCenter, self._fmt(a))
            tip = f"<b>{self.label_fn(lbl)}</b>"
            for value, _c, name in bars:
                tip += f"<br>{name + ': ' if name else ''}" + (self._fmt(value) if value is not None else "—")
            self._hits.append((QRectF(0, y, self.width(), row_h), tip))


DwellChart = HBarChart


# ---------------------------------------------------------------------------
class RhythmChart(QWidget):
    """Línea con el intervalo entre pulsaciones (DD) a lo largo del texto."""

    LEFT, RIGHT, TOP, BOTTOM = 58, 16, 14, 26
    CLIP = 1500.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.values: list[float] = []
        self.setMinimumHeight(180)
        self.setMouseTracking(True)
        self._hover: int | None = None

    def set_data(self, values: list[float]) -> None:
        self.values = list(values)
        self._hover = None
        self.update()

    def _geom(self):
        w = self.width() - self.LEFT - self.RIGHT
        h = self.height() - self.TOP - self.BOTTOM
        vmax = nice_max(min(max(self.values), self.CLIP)) if self.values else 1
        return w, h, vmax

    def _point(self, i, v, w, h, vmax):
        n = max(len(self.values) - 1, 1)
        return QPointF(self.LEFT + w * i / n, self.TOP + h * (1 - min(v, vmax) / vmax))

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(small_font(self))
        if len(self.values) < 2:
            p.setPen(QColor(theme.MUTED))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, _("Sin datos suficientes"))
            return
        w, h, vmax = self._geom()
        for i in range(5):
            y = self.TOP + h * i / 4
            p.setPen(QPen(QColor(theme.GRID), 1))
            p.drawLine(QPointF(self.LEFT, y), QPointF(self.LEFT + w, y))
            p.setPen(QColor(theme.MUTED))
            p.drawText(QRectF(0, y - 9, self.LEFT - 6, 18),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{vmax * (1 - i / 4):.0f} ms")
        p.drawText(QRectF(self.LEFT, self.TOP + h + 6, w, 18), Qt.AlignmentFlag.AlignCenter,
                   _("pulsaciones a lo largo del texto →"))
        path = QPainterPath(self._point(0, self.values[0], w, h, vmax))
        for i, v in enumerate(self.values[1:], 1):
            path.lineTo(self._point(i, v, w, h, vmax))
        area = QPainterPath(path)
        area.lineTo(QPointF(self.LEFT + w, self.TOP + h))
        area.lineTo(QPointF(self.LEFT, self.TOP + h))
        area.closeSubpath()
        p.fillPath(area, color(theme.SERIES_1, 0.10))
        p.setPen(QPen(QColor(theme.SERIES_1), 1.6))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        if self._hover is not None:
            pt = self._point(self._hover, self.values[self._hover], w, h, vmax)
            p.setPen(QPen(QColor(theme.MUTED), 1, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(pt.x(), self.TOP), QPointF(pt.x(), self.TOP + h))
            p.setPen(QPen(QColor(theme.SURFACE), 2))
            p.setBrush(QColor(theme.SERIES_1))
            p.drawEllipse(pt, 5, 5)

    def mouseMoveEvent(self, e):
        if len(self.values) < 2:
            return
        w, _, _ = self._geom()
        i = round((e.position().x() - self.LEFT) / max(w, 1) * (len(self.values) - 1))
        if 0 <= i < len(self.values):
            self._hover = i
            v = self.values[i]
            QToolTip.showText(e.globalPosition().toPoint(),
                              _("Intervalo {i}: <b>{ms} ms</b>", i=i + 1, ms=f"{v:.0f}")
                              + (" (" + _("pausa") + ")" if v > self.CLIP else ""), self)
        else:
            self._hover = None
        self.update()

    def leaveEvent(self, _event):
        self._hover = None
        self.update()


# ---------------------------------------------------------------------------
class Sparkline(QWidget):
    """Mini línea del ritmo reciente (sin ejes) para el panel de escritura."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.values: list[float] = []
        self.setFixedSize(150, 38)
        self.setToolTip(_("Ritmo de las últimas pulsaciones (más bajo = más rápido)"))

    def set_data(self, values: list[float]) -> None:
        self.values = [min(v, 1000.0) for v in values[-40:]]
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(4, 5, self.width() - 9, self.height() - 10)
        p.setPen(QPen(QColor(theme.GRID), 1))
        p.drawLine(r.bottomLeft(), r.bottomRight())
        if len(self.values) < 2:
            return
        vmax = max(max(self.values), 200.0)
        n = len(self.values) - 1
        path = QPainterPath()
        for i, v in enumerate(self.values):
            pt = QPointF(r.left() + r.width() * i / n, r.bottom() - r.height() * v / vmax)
            if i == 0:
                path.moveTo(pt)
            else:
                path.lineTo(pt)
        p.setPen(QPen(QColor(theme.SERIES_1), 1.6))
        p.drawPath(path)
        last = QPointF(r.right(), r.bottom() - r.height() * self.values[-1] / vmax)
        p.setPen(QPen(QColor(theme.SURFACE), 1.5))
        p.setBrush(QColor(theme.SERIES_1))
        p.drawEllipse(last, 3.5, 3.5)


# ---------------------------------------------------------------------------
class RadarChart(QWidget):
    """Gráfico radar de rasgos normalizados (0-1), una o dos series."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.axes: list[str] = []
        self.series: list[tuple[str, list[float], list[str], str]] = []
        self.setMinimumHeight(300)
        self.setMouseTracking(True)
        self._points: list[tuple[QPointF, int]] = []

    def set_data(self, axes: list[str], series) -> None:
        """series: [(nombre, valores 0-1, textos con el valor real, color)]"""
        self.axes, self.series = axes, series
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(small_font(self))
        n = len(self.axes)
        if n < 3 or not self.series:
            p.setPen(QColor(theme.MUTED))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, _("Sin datos suficientes"))
            return
        legend_h = 26 if len(self.series) > 1 else 0
        if legend_h:
            items = [(name, col) for name, _, _, col in self.series]
            fm = p.fontMetrics()
            total = sum(32 + fm.horizontalAdvance(nm) for nm, _ in items)
            draw_legend(p, (self.width() - total) / 2, 4, items)
        cx = self.width() / 2
        cy = legend_h + (self.height() - legend_h) / 2 + 2
        radius = max(30.0, min(self.width() / 2 - 74, (self.height() - legend_h) / 2 - 28))

        def at(i, r):
            ang = -math.pi / 2 + 2 * math.pi * i / n
            return QPointF(cx + r * math.cos(ang), cy + r * math.sin(ang))

        p.setBrush(Qt.BrushStyle.NoBrush)
        for level in (0.25, 0.5, 0.75, 1.0):
            p.setPen(QPen(QColor(theme.GRID), 1))
            p.drawPolygon(QPolygonF([at(i, radius * level) for i in range(n)]))
        for i, name in enumerate(self.axes):
            p.setPen(QPen(QColor(theme.GRID), 1))
            p.drawLine(QPointF(cx, cy), at(i, radius))
            lp = at(i, radius + 18)
            p.setPen(QColor(theme.TEXT_2))
            p.drawText(QRectF(lp.x() - 64, lp.y() - 10, 128, 20), Qt.AlignmentFlag.AlignCenter, name)

        self._points = []
        for _name, values, _texts, col in self.series:
            poly = QPolygonF([at(i, radius * max(0.03, v)) for i, v in enumerate(values)])
            p.setBrush(color(col, 0.16))
            p.setPen(QPen(QColor(col), 2))
            p.drawPolygon(poly)
            p.setPen(QPen(QColor(theme.SURFACE), 1.5))
            p.setBrush(QColor(col))
            for i in range(poly.size()):
                p.drawEllipse(poly.at(i), 4.5, 4.5)
                self._points.append((poly.at(i), i))

    def mouseMoveEvent(self, e):
        pos = e.position()
        for pt, i in self._points:
            if (pt - pos).manhattanLength() < 16:
                tip = f"<b>{self.axes[i]}</b>"
                for name, _v, texts, _c in self.series:
                    tip += f"<br>{name}: {texts[i]}"
                QToolTip.showText(e.globalPosition().toPoint(), tip, self)
                return
        QToolTip.hideText()


# ---------------------------------------------------------------------------
class Gauge(QWidget):
    """Medidor semicircular animado (0-100 %) con la marca del umbral en el 50 %."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0.0
        self.target = 0.0
        self.level = "good"
        self.caption = ""
        self.setFixedSize(210, 160)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(900)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._step)

    def _step(self, v):
        self._value = float(v)
        self.update()

    def set_value(self, value: float, level: str, caption: str = "", animate: bool = True) -> None:
        self.target, self.level, self.caption = max(0.0, min(100.0, value)), level, caption
        self.setToolTip(_("Confianza {n} %. La marca indica el umbral (50 %): por debajo, la muestra queda fuera "
                          "del perfil.", n=f"{self.target:.0f}"))
        self._anim.stop()
        if animate:
            self._anim.setStartValue(0.0)
            self._anim.setEndValue(self.target)
            self._anim.start()
        else:
            self._value = self.target
            self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        thick = 15
        rect = QRectF(thick, thick, w - 2 * thick, w - 2 * thick)
        start, span = 210, -240
        pen = QPen(QColor(theme.GRID), thick)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawArc(rect, start * 16, span * 16)
        if self._value > 0.5:
            pen.setColor(QColor(theme.status_color(self.level)))
            p.setPen(pen)
            p.drawArc(rect, start * 16, int(span * 16 * self._value / 100))
        ang = math.radians(start + span * 0.5)
        c = rect.center()
        r1, r2 = rect.width() / 2 - thick / 2 - 3, rect.width() / 2 + thick / 2 + 3
        p.setPen(QPen(QColor(theme.TEXT_2), 2))
        p.drawLine(QPointF(c.x() + r1 * math.cos(ang), c.y() - r1 * math.sin(ang)),
                   QPointF(c.x() + r2 * math.cos(ang), c.y() - r2 * math.sin(ang)))
        f = QFont(self.font())
        f.setPointSizeF(23 * theme.SCALE)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(theme.TEXT))
        p.drawText(QRectF(0, c.y() - 30, w, 40), Qt.AlignmentFlag.AlignCenter, f"{self._value:.0f} %")
        p.setFont(small_font(self, 9))
        p.setPen(QColor(theme.TEXT_2))
        p.drawText(QRectF(0, c.y() + 12, w, 20), Qt.AlignmentFlag.AlignCenter, self.caption)


# ---------------------------------------------------------------------------
class StackedBars(_HoverMixin, QWidget):
    """Barras verticales apiladas por día (dos categorías)."""

    LEFT, RIGHT, TOP, BOTTOM = 34, 10, 32, 24

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hover_init()
        self.days: list[tuple[str, int, int]] = []
        self.names = ("A", "B")
        self.setMinimumHeight(210)

    def set_data(self, days, names) -> None:
        self.days, self.names = list(days), names
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(small_font(self))
        self._hits = []
        draw_legend(p, self.LEFT, 4, [(self.names[0], theme.SERIES_1), (self.names[1], theme.SERIES_2)])
        if not self.days:
            return
        w = self.width() - self.LEFT - self.RIGHT
        h = self.height() - self.TOP - self.BOTTOM
        top_val = max((a + b for _, a, b in self.days), default=0)
        vmax = max(4, int(math.ceil(top_val / 4.0)) * 4)
        for i in range(5):
            y = self.TOP + h * i / 4
            p.setPen(QPen(QColor(theme.GRID), 1))
            p.drawLine(QPointF(self.LEFT, y), QPointF(self.LEFT + w, y))
            p.setPen(QColor(theme.MUTED))
            p.drawText(QRectF(0, y - 9, self.LEFT - 6, 18),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{vmax * (1 - i / 4):.0f}")
        slot = w / len(self.days)
        bw = min(26.0, slot * 0.6)
        base = self.TOP + h
        for i, (lbl, a, b) in enumerate(self.days):
            x = self.LEFT + slot * i + (slot - bw) / 2
            ha, hb = h * a / vmax, h * b / vmax
            if a:
                rect = QRectF(x, base - ha, bw, ha)
                if b:
                    p.fillRect(rect, QColor(theme.SERIES_1))
                else:
                    rounded_bar(p, rect, theme.SERIES_1, side="top")
            if b:
                gap = 2 if a else 0
                rounded_bar(p, QRectF(x, base - ha - hb - gap, bw, hb), theme.SERIES_2, side="top")
            if len(self.days) <= 8 or (len(self.days) - 1 - i) % 2 == 0:
                p.setPen(QColor(theme.MUTED))
                p.drawText(QRectF(x - 24, base + 4, bw + 48, 18), Qt.AlignmentFlag.AlignCenter, lbl)
            self._hits.append((QRectF(self.LEFT + slot * i, self.TOP, slot, h),
                               f"<b>{lbl}</b><br>{self.names[0]}: {a}<br>{self.names[1]}: {b}"))


# ---------------------------------------------------------------------------
class RatioHistogram(_HoverMixin, QWidget):
    """Distribución de distancia ÷ umbral: mismo usuario frente a otros usuarios."""

    LEFT, RIGHT, TOP, BOTTOM = 42, 12, 32, 38
    N_BINS = 25          # 0.0 … 2.5 en pasos de 0.1; el último acumula ≥ 2.4

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hover_init()
        self.genuine: list[float] = []
        self.impostor: list[float] = []
        self.setMinimumHeight(220)

    def set_data(self, genuine: list[float], impostor: list[float]) -> None:
        self.genuine, self.impostor = genuine, impostor
        self.update()

    def _hist(self, values):
        counts = [0] * self.N_BINS
        for v in values:
            counts[max(0, min(int(v * 10), self.N_BINS - 1))] += 1
        total = max(len(values), 1)
        return [100.0 * c / total for c in counts]

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(small_font(self))
        self._hits = []
        draw_legend(p, self.LEFT, 4, [(_("Mismo usuario"), theme.SERIES_1), (_("Otros usuarios"), theme.SERIES_2)])
        g, im = self._hist(self.genuine), self._hist(self.impostor)
        w = self.width() - self.LEFT - self.RIGHT
        h = self.height() - self.TOP - self.BOTTOM
        vmax = nice_max(max(g + im + [1]))
        for i in range(5):
            y = self.TOP + h * i / 4
            p.setPen(QPen(QColor(theme.GRID), 1))
            p.drawLine(QPointF(self.LEFT, y), QPointF(self.LEFT + w, y))
            p.setPen(QColor(theme.MUTED))
            p.drawText(QRectF(0, y - 9, self.LEFT - 6, 18),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{vmax * (1 - i / 4):.0f}%")
        slot = w / self.N_BINS
        bw = max(1.5, (slot - 4) / 2)
        base = self.TOP + h
        for i in range(self.N_BINS):
            x = self.LEFT + slot * i + 1
            for j, (vals, col) in enumerate(((g, theme.SERIES_1), (im, theme.SERIES_2))):
                if vals[i] > 0:
                    bh = max(2.0, h * vals[i] / vmax)
                    rounded_bar(p, QRectF(x + j * (bw + 2), base - bh, bw, bh), col, radius=2, side="top")
            lo = i / 10
            rng = f"{lo:.1f}–{lo + 0.1:.1f}" if i < self.N_BINS - 1 else f"≥ {lo:.1f}"
            self._hits.append((QRectF(x - 1, self.TOP, slot, h),
                               f"<b>{_('distancia ÷ umbral')} {rng}</b><br>"
                               + _("Mismo usuario: {pct} %", pct=f"{g[i]:.0f}") + "<br>"
                               + _("Otros usuarios: {pct} %", pct=f"{im[i]:.0f}")))
        tx = self.LEFT + slot * 10
        p.setPen(QPen(QColor(theme.TEXT_2), 1.5, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(tx, self.TOP - 4), QPointF(tx, base))
        p.setPen(QColor(theme.TEXT_2))
        p.drawText(QRectF(tx + 5, self.TOP - 4, 120, 16), Qt.AlignmentFlag.AlignLeft, _("umbral"))
        p.setPen(QColor(theme.MUTED))
        for v in (0, 0.5, 1.0, 1.5, 2.0, 2.5):
            x = self.LEFT + slot * v * 10
            p.drawText(QRectF(x - 20, base + 4, 40, 16), Qt.AlignmentFlag.AlignCenter, f"{v:g}")
        p.drawText(QRectF(self.LEFT, base + 20, w, 16), Qt.AlignmentFlag.AlignCenter, _("distancia ÷ umbral"))


# ---------------------------------------------------------------------------
class LineChart(_HoverMixin, QWidget):
    """Evolución de una medida a lo largo de las muestras (una serie, con puntos)."""

    LEFT, RIGHT, TOP, BOTTOM = 48, 14, 12, 24

    def __init__(self, unit: str = "", decimals: int = 0, parent=None):
        super().__init__(parent)
        self._hover_init()
        self.unit, self.decimals = unit, decimals
        self.points: list[tuple[str, float]] = []
        self.marks: list[int] = []          # índices donde empieza una sesión nueva
        self.setMinimumHeight(170)

    def set_data(self, points: list[tuple[str, float]], marks: list[int] | None = None) -> None:
        self.points, self.marks = list(points), list(marks or [])
        self.update()

    def _fmt(self, v: float) -> str:
        return f"{v:.{self.decimals}f}{(' ' + self.unit) if self.unit else ''}"

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(small_font(self))
        self._hits = []
        if len(self.points) < 2:
            p.setPen(QColor(theme.MUTED))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, _("Hacen falta al menos 2 muestras"))
            return
        vals = [v for _, v in self.points]
        lo, hi = min(vals), max(vals)
        pad = max((hi - lo) * 0.2, abs(hi) * 0.05, 1.0)
        lo, hi = max(0.0, lo - pad), hi + pad
        w = self.width() - self.LEFT - self.RIGHT
        h = self.height() - self.TOP - self.BOTTOM
        for i in range(4):
            y = self.TOP + h * i / 3
            p.setPen(QPen(QColor(theme.GRID), 1))
            p.drawLine(QPointF(self.LEFT, y), QPointF(self.LEFT + w, y))
            p.setPen(QColor(theme.MUTED))
            p.drawText(QRectF(0, y - 9, self.LEFT - 6, 18), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{hi - (hi - lo) * i / 3:.0f}")
        n = len(self.points)

        def pt(i, v):
            return QPointF(self.LEFT + w * i / (n - 1), self.TOP + h * (1 - (v - lo) / (hi - lo)))

        for i in self.marks:
            if 0 < i < n:
                x = self.LEFT + w * (i - 0.5) / (n - 1)
                p.setPen(QPen(QColor(theme.BORDER_STRONG), 1, Qt.PenStyle.DashLine))
                p.drawLine(QPointF(x, self.TOP), QPointF(x, self.TOP + h))
        path = QPainterPath(pt(0, vals[0]))
        for i, v in enumerate(vals[1:], 1):
            path.lineTo(pt(i, v))
        p.setPen(QPen(QColor(theme.SERIES_1), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        for i, (lbl, v) in enumerate(self.points):
            c = pt(i, v)
            p.setPen(QPen(QColor(theme.SURFACE), 1.5))
            p.setBrush(QColor(theme.SERIES_1))
            p.drawEllipse(c, 4.5, 4.5)
            self._hits.append((QRectF(c.x() - 10, self.TOP, 20, h), f"<b>{lbl}</b><br>{self._fmt(v)}"))
        p.setPen(QColor(theme.MUTED))
        p.drawText(QRectF(self.LEFT, self.TOP + h + 4, w, 18), Qt.AlignmentFlag.AlignCenter, _("por fecha →"))
