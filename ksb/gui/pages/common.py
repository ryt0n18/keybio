"""Utilidades compartidas por las pantallas."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QDate, QLocale, QObject, QRunnable, Qt, QTime, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem

from ...evaluation import UserData, evaluate
from ...i18n import _, _n


def table(headers: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setShowGrid(False)
    t.setAlternatingRowColors(True)
    t.setWordWrap(False)
    t.verticalHeader().setDefaultSectionSize(34)
    header = t.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    header.setStretchLastSection(True)
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    header.setHighlightSections(False)
    return t


def fit_height(t: QTableWidget, max_rows: int = 10) -> None:
    """Ajusta la altura de la tabla a sus filas (sin hueco vacío debajo)."""
    rows = min(max(t.rowCount(), 1), max_rows)
    header = t.horizontalHeader()
    head_h = max(header.height(), header.sizeHint().height())
    row_h = sum(t.rowHeight(i) for i in range(min(rows, t.rowCount()))) or t.verticalHeader().defaultSectionSize()
    h = head_h + row_h + 2 * t.frameWidth() + 4
    t.setFixedHeight(h)


def cell(text, color: str | None = None, data=None, bold: bool = False) -> QTableWidgetItem:
    item = QTableWidgetItem(str(text))
    if color:
        item.setForeground(QColor(color))
    if data is not None:
        item.setData(Qt.ItemDataRole.UserRole, data)
    if bold:
        f = item.font()
        f.setBold(True)
        item.setFont(f)
    return item


def time_ago(iso: str) -> str:
    try:
        then = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return iso or ""
    secs = (datetime.now() - then).total_seconds()
    if secs < 60:
        return _("ahora mismo")
    if secs < 3600:
        return _("hace {n} min", n=int(secs // 60))
    if secs < 86400:
        return _("hace {n} h", n=int(secs // 3600))
    if secs < 2 * 86400:
        return _("ayer")
    if secs < 7 * 86400:
        return _n("hace {n} día", "hace {n} días", int(secs // 86400))
    return short_date(then)


def short_date(day) -> str:
    """Fecha corta en el orden del idioma de la interfaz, con el año completo (24/10/2026, 10/24/2026...)."""
    loc = QLocale()
    fmt = loc.dateFormat(QLocale.FormatType.ShortFormat)
    if "yyyy" not in fmt:
        fmt = fmt.replace("yy", "yyyy")
    return loc.toString(QDate(day.year, day.month, day.day), fmt)


def short_datetime(moment) -> str:
    """Fecha corta y hora (sin segundos) en el idioma de la interfaz."""
    time = QLocale().toString(QTime(moment.hour, moment.minute), QLocale.FormatType.ShortFormat)
    return f"{short_date(moment)} {time}"


def weekday_short(day) -> str:
    """Día de la semana abreviado en el idioma de la interfaz ("lun", "Mon"...)."""
    return QLocale().dayName(day.isoweekday(), QLocale.FormatType.ShortFormat).rstrip(".")


def long_date(day) -> str:
    """Fecha larga en el idioma de la interfaz, con mayúscula inicial ("Viernes, 24 de octubre de 2026")."""
    text = QLocale().toString(QDate(day.year, day.month, day.day), QLocale.FormatType.LongFormat)
    return text[:1].upper() + text[1:]


class _EvalSignals(QObject):
    done = Signal(object, object)   # (clave, EvalResult)


class EvalTask(QRunnable):
    """Ejecuta la evaluación cruzada en segundo plano para no congelar la interfaz."""

    def __init__(self, key, data: list[UserData], sensitivity: str):
        super().__init__()
        self.key, self.data, self.sensitivity = key, data, sensitivity
        self.signals = _EvalSignals()

    def run(self):
        try:
            result = evaluate(self.data, self.sensitivity)
        except Exception as exc:  # se muestra en la interfaz en lugar de perderse en el hilo
            result = exc
        self.signals.done.emit(self.key, result)
