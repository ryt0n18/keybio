"""Historial de comprobaciones."""

from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtWidgets import QComboBox, QFileDialog, QHBoxLayout, QLineEdit, QMessageBox, QVBoxLayout, QWidget

from ...i18n import N_, _
from ...service import BiometricService
from .. import theme
from ..widgets import Tile, button, label, notify, page_title
from .common import cell, table

FILTERS = [N_("Todas"), N_("Reconocidas"), N_("No reconocidas"), N_("Verificadas como correctas"),
           N_("Verificadas como incorrectas"), N_("Sin verificar"), N_("Sospechosas")]


def csv_cell(value):
    """Texto que Excel no interpretará como fórmula (un nombre como «=HIPERVINCULO(...)»)."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


class HistoryPage(QWidget):
    def __init__(self, service: BiometricService, parent=None):
        super().__init__(parent)
        self.service = service
        self.entries: list[dict] = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 22)
        lay.setSpacing(12)
        head = QHBoxLayout()
        head.addWidget(page_title(_("Historial"), _("Todas las comprobaciones realizadas en este equipo."), "history"), 1)
        export = button(_("Exportar CSV…"), "download")
        export.clicked.connect(self._export)
        clear = button(_("Borrar historial"), "trash", "danger")
        clear.clicked.connect(self._clear)
        head.addWidget(export)
        head.addWidget(clear)
        lay.addLayout(head)

        tiles = QHBoxLayout()
        tiles.setSpacing(12)
        self.t_total = Tile("scan", _("Comprobaciones"))
        self.t_rec = Tile("check_circle", _("Reconocidas"))
        self.t_unk = Tile("help", _("No reconocidas"))
        self.t_ok = Tile("shield", _("Acierto verificado"))
        for t in (self.t_total, self.t_rec, self.t_unk, self.t_ok):
            tiles.addWidget(t)
        lay.addLayout(tiles)

        filters = QHBoxLayout()
        filters.addWidget(label(_("Mostrar:")))
        self.filter = QComboBox()
        self.filter.addItems([_(f) for f in FILTERS])
        self.filter.currentIndexChanged.connect(self._fill)
        filters.addWidget(self.filter)
        self.search = QLineEdit()
        self.search.setPlaceholderText(_("Buscar por usuario…"))
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(240)
        self.search.setMaximumWidth(320)
        self.search.textChanged.connect(self._fill)
        filters.addWidget(self.search)
        filters.addStretch(1)
        self.count = label("", "small")
        filters.addWidget(self.count)
        lay.addLayout(filters)

        self.table = table([_("Fecha"), _("Modo"), _("Resultado"), _("Confianza"), _("Distancia"), _("Umbral"),
                            _("PPM"), _("Precisión"), _("Texto"), _("Sensibilidad"), _("Notas"), _("Verificación")])
        lay.addWidget(self.table, 1)

    def refresh(self):
        self.entries = self.service.history()
        e = self.entries
        rec = sum(bool(x.get("accepted", x.get("user_id"))) for x in e)
        verified = [x for x in e if x.get("feedback")]
        ok = sum(x["feedback"] == "correct" for x in verified)
        self.t_total.set(str(len(e)))
        self.t_rec.set(str(rec), _("{pct} % del total", pct=f"{100 * rec / len(e):.0f}") if e else "")
        self.t_unk.set(str(len(e) - rec), _("{pct} % del total", pct=f"{100 * (len(e) - rec) / len(e):.0f}") if e else "")
        self.t_ok.set(f"{100 * ok / len(verified):.0f} %" if verified else "—",
                      _("{ok} de {n} verificadas", ok=ok, n=len(verified)) if verified else _("sin verificar aún"))
        self._fill()

    def _matches(self, e: dict) -> bool:
        accepted = bool(e.get("accepted", e.get("user_id")))
        fb = e.get("feedback")
        idx = self.filter.currentIndex()
        if idx == 1 and not accepted or idx == 2 and accepted:
            return False
        if idx == 3 and fb != "correct" or idx == 4 and fb != "incorrect" or idx == 5 and fb:
            return False
        if idx == 6 and not e.get("suspicious"):
            return False
        q = self.search.text().strip().casefold()
        if q:
            names = " ".join(str(x) for x in (e.get("user_name"), e.get("claimed")) if x).casefold()
            return q in names
        return True

    def _fill(self):
        names = {u.id: u.name for u in self.service.users()}
        self.table.setRowCount(0)
        shown = [e for e in self.entries if self._matches(e)]
        for e in shown:
            r = self.table.rowCount()
            self.table.insertRow(r)
            mode = e.get("mode")
            verify = mode == "verify"
            accepted = bool(e.get("accepted", e.get("user_id")))
            if mode == "challenge":
                result = ("✘ " + _("engañado: pasó por {name}", name=e.get("claimed")) if accepted
                          else "✔ " + _("no pasó por {name}", name=e.get("claimed")))
                res_color = theme.BAD if accepted else theme.GOOD
            elif verify:
                result = ("✔ " + _("es {name}", name=e.get("claimed")) if accepted
                          else "✘ " + _("no es {name}", name=e.get("claimed")))
                res_color = theme.GOOD if accepted else theme.BAD
            else:
                result = e.get("user_name") if accepted else _("No registrado")
                res_color = theme.GOOD if accepted else theme.WARN
            fb = e.get("feedback")
            if fb == "correct":
                fb_text, fb_color = "✔ " + _("correcto"), theme.GOOD
            elif fb == "incorrect":
                who = names.get(e.get("true_user"), _("no registrado")) if e.get("true_user") else _("no registrado")
                fb_text, fb_color = "✘ " + _("era {name}", name=who), theme.BAD
            else:
                fb_text, fb_color = _("sin verificar"), theme.MUTED
            vals = [
                (e["date"].replace("T", " "), None),
                ({"verify": _("Verificación"), "challenge": _("Desafío")}.get(mode, _("Identificación")), None),
                (result, res_color),
                (f"{e['confidence']:.0f} %" if e.get("confidence") is not None else "—", None),
                (f"{e['distance']:.3f}" if e.get("distance") is not None else "—", None),
                (f"{e['threshold']:.3f}" if e.get("threshold") is not None else "—", None),
                (f"{e['wpm']:.0f}" if e.get("wpm") else "—", None),
                (f"{e.get('accuracy', 0):.0f} %", None),
                (e.get("text_id", ""), None),
                (e.get("sensitivity", ""), None),
                (", ".join(n for n, on in ((_("sospechosa"), bool(e.get("suspicious"))),
                                           (_("perfil adaptado"), bool(e.get("adapted_user"))),
                                           (_("texto libre"), bool(e.get("free")))) if on),
                 theme.BAD if e.get("suspicious") else None),
                (fb_text, fb_color),
            ]
            for col, (v, c) in enumerate(vals):
                self.table.setItem(r, col, cell(v, c))
        self.count.setText(_("{n} de {total}", n=len(shown), total=len(self.entries)))

    def _export(self):
        if not self.entries:
            QMessageBox.information(self, _("Exportar"), _("El historial está vacío."))
            return
        path = QFileDialog.getSaveFileName(self, _("Exportar historial"),
                                           str(Path.home() / f"{_('historial')}_keybio.csv"), "CSV (*.csv)")[0]
        if not path:
            return
        fields = ["date", "mode", "user_name", "claimed", "accepted", "confidence", "distance", "threshold", "wpm",
                  "accuracy", "text_id", "free", "sensitivity", "ambiguous", "suspicious", "feedback"]
        # utf-8-sig y ';' para que Excel en Windows lo abra correctamente
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=fields, delimiter=";", extrasaction="ignore")
            w.writeheader()
            for e in self.entries:
                row = {**e, "suspicious": " ".join(e.get("suspicious") or [])}
                w.writerow({k: csv_cell(v) for k, v in row.items()})
        notify(self, _("Historial exportado"))

    def _clear(self):
        ans = QMessageBox.question(self, _("Borrar historial"), _("¿Borrar todo el historial de comprobaciones?"))
        if ans == QMessageBox.StandardButton.Yes:
            self.service.clear_history()
            self.refresh()
