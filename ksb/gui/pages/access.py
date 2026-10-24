"""Verificaciones de acceso: puntuaciones guardadas y avisos para el administrador."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QCheckBox, QFormLayout, QHBoxLayout, QMessageBox, QSpinBox, QVBoxLayout, QWidget

from ...i18n import N_, _
from ...service import BiometricService
from .. import theme
from ..widgets import Tile, button, card, card_header, label, page_title, page_widget, scroll
from .common import cell, fit_height, short_date, short_datetime, table

# cómo terminó la verificación adicional de un aviso: (texto, color del tema)
EXTRA = {"pending": (N_("sin terminar"), "WARN"), "passed": (N_("✔ superada"), "GOOD"),
         "failed": (N_("✘ no superada"), "BAD"), "abandoned": (N_("✘ abandonada"), "BAD")}


def command_name() -> str:
    """Cómo se lanza KeyBio en este equipo (ejecutable empaquetado o desde el código)."""
    return Path(sys.executable).name if getattr(sys, "frozen", False) else "python main.py"


def _date(iso: str) -> str:
    try:
        d = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return iso or ""
    return short_date(d) if len(iso) <= 10 else short_datetime(d)


class AccessPage(QWidget):
    def __init__(self, service: BiometricService, parent=None):
        super().__init__(parent)
        self.service = service
        self.entries: list[dict] = []
        inner, lay = page_widget()
        head = QHBoxLayout()
        head.addWidget(page_title(_("Accesos"), _("Verificación por la forma de escribir al iniciar sesión en sistemas "
                                                 "sensibles, con una frase corta."), "lock"), 1)
        clear = button(_("Borrar registros"), "trash", "danger")
        clear.clicked.connect(self._clear)
        head.addWidget(clear)
        lay.addLayout(head)

        tiles = QHBoxLayout()
        tiles.setSpacing(12)
        self.t_total = Tile("lock", _("Verificaciones"))
        self.t_match = Tile("check_circle", _("Coinciden a la primera"))
        self.t_notices = Tile("alert", _("Avisos"))
        for t in (self.t_total, self.t_match, self.t_notices):
            tiles.addWidget(t)
        lay.addLayout(tiles)

        c, cl = card()
        top = QHBoxLayout()
        top.addWidget(card_header(_("Registros"), "history"), 1)
        self.only_notices = QCheckBox(_("Solo avisos"))
        self.only_notices.toggled.connect(self._fill)
        top.addWidget(self.only_notices)
        cl.addLayout(top)
        self.table = table([_("Fecha"), _("Persona"), _("Sistema"), _("Puntuación"), _("Resultado"),
                            _("Verificación adicional")])
        self.table.horizontalHeaderItem(3).setToolTip(_("Coincidencia con el perfil, de 0 a 100; 50 es el umbral."))
        cl.addWidget(self.table)
        self.empty = label(_("Todavía no hay verificaciones de acceso."), "subtitle", wrap=True)
        cl.addWidget(self.empty)
        lay.addWidget(c)

        c, cl = card()
        cl.addWidget(card_header(_("Qué se guarda"), "shield"))
        cl.addWidget(label(_(
            "La frase se analiza en este equipo y se descarta al terminar: <b>no se guardan las pulsaciones, ni lo "
            "que se escribe, ni la dirección IP o el nombre del equipo</b>, y no se añade al perfil.<br>"
            "• Si coincide: el día, la persona y la puntuación de coincidencia.<br>"
            "• Si no coincide (aviso): además la hora y el sistema, y si se superó la verificación adicional "
            "(un texto más largo). No se registra nada más."), "subtitle", wrap=True, rich=True))
        form = QFormLayout()
        self.retention = QSpinBox()
        self.retention.setRange(1, 365)
        self.retention.setSuffix(" " + _("días"))
        self.retention.setMaximumWidth(140)
        self.retention.setKeyboardTracking(False)   # al escribir «90» no se aplica antes un plazo de 9 días
        self.retention.valueChanged.connect(self._save_retention)
        form.addRow(_("Conservar los registros:"), self.retention)
        cl.addLayout(form)
        cl.addWidget(label(_("Pasado ese plazo se borran solos. No entran en las copias de seguridad."), "small",
                           wrap=True))
        lay.addWidget(c)

        c, cl = card()
        cl.addWidget(card_header(_("Cómo usarla al iniciar sesión"), "help"))
        self.usage = label("", "subtitle", wrap=True, rich=True)
        cl.addWidget(self.usage)
        lay.addWidget(c)
        lay.addStretch(1)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll(inner))

    def refresh(self):
        self.retention.blockSignals(True)
        self.retention.setValue(int(self.service.settings.get("access_retention_days", 30)))
        self.retention.blockSignals(False)
        self.entries = self.service.access_log()
        e = self.entries
        days = self.retention.value()
        notices = [x for x in e if not x.get("match")]
        unresolved = sum(x.get("extra") != "passed" for x in notices)
        self.t_total.set(str(len(e)), _("últimos {n} días", n=days))
        self.t_match.set(f"{100 * (len(e) - len(notices)) / len(e):.0f} %" if e else "—",
                         _("{ok} de {n}", ok=len(e) - len(notices), n=len(e)) if e else "")
        self.t_notices.set(str(len(notices)), _("{n} sin superar la verificación adicional", n=unresolved)
                           if notices else "")
        self.usage.setText(
            _("El sistema sensible (o el guion que lo abre) lanza KeyBio con la persona que inicia sesión:") + "<br>"
            f"<code>{command_name()} --acceso \"{_('Nombre')}\" --sistema \"{_('Nóminas')}\"</code><br>"
            + _("KeyBio pide una frase corta y termina con un código de salida: <b>0</b> identidad confirmada · "
                "<b>1</b> no confirmada (hay aviso) · <b>2</b> no se pudo comprobar. Cualquier código distinto de 0 "
                "debe tratarse como no confirmado. Ofrece también un procedimiento alternativo a quien no pueda o no "
                "quiera usar la verificación por tecleo."))
        self._fill()

    def _fill(self):
        names = {u.id: u.name for u in self.service.users()}
        shown = [x for x in self.entries if not (self.only_notices.isChecked() and x.get("match"))]
        self.table.setRowCount(0)
        for x in shown:
            r = self.table.rowCount()
            self.table.insertRow(r)
            match = bool(x.get("match"))
            extra, role = ("—", None) if match else EXTRA.get(x.get("extra"), ("—", None))
            vals = [(_date(x.get("date", "")), None), (names.get(x.get("user_id"), "—"), None),
                    (x.get("system") or "—", None), (str(x.get("score", "—")), None),
                    ("✔ " + _("coincide") if match else _("aviso: no coincide"), theme.GOOD if match else theme.WARN),
                    (_(extra), getattr(theme, role) if role else None)]
            for col, (v, color) in enumerate(vals):
                self.table.setItem(r, col, cell(v, color))
        self.table.setVisible(bool(shown))
        self.empty.setVisible(not shown)
        self.empty.setText(_("No hay avisos.") if self.entries else _("Todavía no hay verificaciones de acceso."))
        fit_height(self.table, 14)

    def _save_retention(self, days: int):
        self.service.settings["access_retention_days"] = days
        self.service.save_settings()
        self.refresh()

    def _clear(self):
        ans = QMessageBox.question(self, _("Borrar registros"), _("¿Borrar todos los registros de verificación de acceso?"))
        if ans == QMessageBox.StandardButton.Yes:
            self.service.clear_access_log()
            self.refresh()
