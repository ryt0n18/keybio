"""Gestión de usuarios y perfiles."""

from __future__ import annotations

import statistics
from collections import defaultdict
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QHeaderView, QInputDialog, QMessageBox, QSplitter,
                               QVBoxLayout, QWidget)

from ...features import median
from ...i18n import _, _n
from ...service import BiometricService, sessions_of
from ...storage import User, clean_name
from .. import theme
from ..charts import LineChart, RadarChart
from ..widgets import (Avatar, Badge, FlowBox, HBox, HeatmapCard, MetricsGrid, button, card, card_header, digraph_text, label,
                       notify, page_title, page_widget, primary, radar_series, scroll)
from .common import cell, fit_height, table, time_ago


def avatar_icon(name: str, index: int, size: int = 26) -> QIcon:
    av = Avatar(size)
    av.set_user(name, index)
    pm = QPixmap(av.size() * 2)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.GlobalColor.transparent)
    av.render(pm)
    return QIcon(pm)


class UsersPage(QWidget):
    users_changed = Signal()
    add_samples = Signal(object)   # User

    def __init__(self, service: BiometricService, parent=None):
        super().__init__(parent)
        self.service = service
        self.users: list[User] = []
        self.order: dict[str, int] = {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 22, 28, 12)
        outer.setSpacing(12)
        head = QHBoxLayout()
        head.addWidget(page_title(_("Usuarios"), _("Perfiles biométricos guardados en este equipo."), "users"), 1)
        imp = button(_("Importar…"), "upload")
        imp.clicked.connect(self._import)
        exp = button(_("Exportar todos…"), "download")
        exp.clicked.connect(self._export_all)
        head.addWidget(imp, alignment=Qt.AlignmentFlag.AlignBottom)
        head.addWidget(exp, alignment=Qt.AlignmentFlag.AlignBottom)
        outer.addLayout(head)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(10)
        outer.addWidget(split, 1)

        self.table = table([_("Nombre"), _("Muestras"), _("PPM"), _("Perfil")])
        self.table.setIconSize(QSize(26, 26))
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.itemSelectionChanged.connect(self._show_selected)
        self.table.setMinimumWidth(360)
        split.addWidget(self.table)

        inner, lay = page_widget(margins=14)
        lay.setContentsMargins(14, 0, 6, 12)
        head = QHBoxLayout()
        head.setSpacing(14)
        self.d_avatar = Avatar(58)
        head.addWidget(self.d_avatar)
        col = QVBoxLayout()
        col.setSpacing(2)
        trow = QHBoxLayout()
        self.d_title = label(_("Selecciona un usuario"), "title")
        self.d_badge = Badge()
        trow.addWidget(self.d_title)
        trow.addWidget(self.d_badge)
        trow.addStretch(1)
        col.addLayout(trow)
        self.d_sub = label("", "subtitle", wrap=True, rich=True)
        col.addWidget(self.d_sub)
        head.addLayout(col, 1)
        lay.addLayout(head)

        self.add_btn = primary(_("Añadir muestras"), "plus")
        self.add_btn.clicked.connect(self._add)
        self.rename_btn = button(_("Renombrar"), "edit")
        self.rename_btn.clicked.connect(self._rename)
        self.export_btn = button(_("Exportar"), "download")
        self.export_btn.clicked.connect(self._export_one)
        self.delete_btn = button(_("Eliminar"), "trash", "danger")
        self.delete_btn.clicked.connect(self._delete)
        self.pdf_btn = button(_("Informe PDF"), "file")
        self.pdf_btn.clicked.connect(self._pdf)
        self.actions = FlowBox(self.add_btn, self.rename_btn, self.export_btn, self.pdf_btn, self.delete_btn)
        lay.addWidget(self.actions)

        self.d_metrics = MetricsGrid(3)
        lay.addWidget(self.d_metrics)

        c, cl = card()
        cl.addWidget(card_header(_("Huella de tecleo"), "fingerprint"))
        cl.addWidget(label(_("Rasgos de este usuario frente a la media del resto."), "small"))
        self.d_radar = RadarChart()
        cl.addWidget(self.d_radar)
        self.radar_card = c
        lay.addWidget(c)

        self.d_heat = HeatmapCard(_("Teclas de este usuario"))
        lay.addWidget(self.d_heat)

        c, cl = card()
        cl.addWidget(card_header(_("Evolución"), "activity"))
        cl.addWidget(label(_("Cómo cambia la forma de escribir de una muestra a otra, por fecha; las líneas "
                             "discontinuas separan sesiones. Si va mejorando con el tiempo, conviene seguir añadiendo "
                             "muestras para que el perfil lo refleje."), "small", wrap=True))
        evo = QHBoxLayout()
        left, right = QVBoxLayout(), QVBoxLayout()
        left.addWidget(label(_("Velocidad (ppm)"), "section"))
        self.evo_speed = LineChart(_("ppm"))
        left.addWidget(self.evo_speed)
        right.addWidget(label(_("Regularidad (%)"), "section"))
        self.evo_reg = LineChart("%")
        right.addWidget(self.evo_reg)
        evo.addLayout(left)
        evo.addLayout(right)
        cl.addLayout(evo)
        self.evo_card = c
        lay.addWidget(c)

        c, cl = card()
        cl.addWidget(card_header(_("Muestras guardadas"), "file"))
        self.samples_table = table([_("Fecha"), _("Tipo"), _("Texto"), _("PPM"), _("Precisión"), _("Errores")])
        cl.addWidget(self.samples_table)
        self.del_sample = button(_("Eliminar muestra seleccionada"), "trash", "danger")
        self.del_sample.clicked.connect(self._delete_sample)
        cl.addWidget(HBox(self.del_sample))
        self.d_digraphs = label(wrap=True, rich=True)
        cl.addWidget(self.d_digraphs)
        self.samples_card = c
        lay.addWidget(c)
        lay.addStretch(1)
        split.addWidget(scroll(inner))
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 5)
        split.setSizes([400, 900])
        self._set_detail_visible(False)

    def _set_detail_visible(self, visible: bool):
        for w in (self.actions, self.d_metrics, self.radar_card, self.d_heat, self.evo_card, self.samples_card,
                  self.d_avatar,
                  self.d_badge):
            w.setVisible(visible)

    def refresh(self):
        selected = self._selected_id()
        self.users = self.service.users()
        self.order = {u.id: i for i, u in enumerate(sorted(self.users, key=lambda u: u.created))}
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for u in self.users:
            r = self.table.rowCount()
            self.table.insertRow(r)
            ms = [self.service.features(s).metrics for s in u.samples]
            wpm = statistics.fmean(m["wpm"] for m in ms) if ms else 0
            level, qtext = self.service.quality(u)
            name_item = cell(u.name, data=u.id, bold=True)
            name_item.setIcon(avatar_icon(u.name, self.order[u.id]))
            self.table.setItem(r, 0, name_item)
            self.table.setItem(r, 1, cell(len(u.samples)))
            self.table.setItem(r, 2, cell(f"{wpm:.0f}"))
            self.table.setItem(r, 3, cell(qtext, theme.status_color(level)))
            if u.id == selected:
                self.table.selectRow(r)
        self.table.blockSignals(False)
        if not self.users:
            self.d_title.setText(_("No hay usuarios"))
            self.d_sub.setText(_("Registra uno desde la sección <b>Registrar</b> o importa un fichero."))
            self._set_detail_visible(False)
        elif self._selected_id() is None:
            self.table.selectRow(0)
        else:
            self._show_selected()

    def _selected_id(self) -> str | None:
        sm = self.table.selectionModel()
        rows = sm.selectedRows() if sm else []
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _selected_user(self) -> User | None:
        uid = self._selected_id()
        return next((u for u in self.users if u.id == uid), None)

    def _show_selected(self):
        u = self._selected_user()
        if u is None:
            return
        self._set_detail_visible(True)
        self.d_avatar.set_user(u.name, self.order.get(u.id, -1))
        prof = self.service.profile(u) if len(u.samples) >= 2 else None
        level, qtext = self.service.quality(u, prof)
        self.d_badge.set(qtext, level)
        ms = [self.service.features(s).metrics for s in u.samples]

        def avg(k):
            return statistics.fmean(m[k] for m in ms) if ms else 0.0

        sens = self.service.sensitivity
        self.d_title.setText(u.name)
        n_ses = self.service.session_count(u)
        sub = (_n("{n} muestra", "{n} muestras", len(u.samples)) + " · "
               + _n("{n} sesión", "{n} sesiones", n_ses) + " · " + _("alta {date}", date=u.created[:10]))
        if u.samples:
            sub += " · " + _("última muestra {when}", when=time_ago(u.samples[-1].created))
        if prof:
            sub += "<br>" + _("Distancia típica consigo mismo <b>{m}</b>, variación <b>{s}</b>, umbral ({sensitivity}) "
                              "<b>{threshold}</b>", m=f"{prof.m:.3f}", s=f"{prof.s:.3f}",
                              sensitivity=self.service.sensitivity_label, threshold=f"{prof.threshold(sens):.3f}")
        self.d_sub.setText(sub)
        shifts_r = sum(m["shift_right"] for m in ms)
        shifts = shifts_r + sum(m["shift_left"] for m in ms)
        self.d_metrics.set_items([
            (f"{avg('wpm'):.0f}", _("Palabras por minuto"), ""),
            (f"{avg('accuracy'):.1f} %", _("Precisión media"), ""),
            (f"{avg('errors_committed'):.1f}", _("Errores por texto"), ""),
            (f"{avg('dwell_mean'):.0f} ms", _("Pulsación media"), ""),
            (f"{avg('flight_mean'):.0f} ms", _("Vuelo medio"), ""),
            (f"{avg('rollover_pct'):.0f} %", _("Solapamiento"), ""),
            (f"{100 * shifts_r / shifts:.0f} %" if shifts else "—", _("Usa el shift derecho"), ""),
            (f"{avg('consistency'):.0f} %", _("Regularidad"), ""),
            (f"{avg('backspaces'):.1f}", _("Retrocesos por texto"), ""),
        ])
        others = [self.service.features(s).metrics for o in self.users if o.id != u.id for s in o.samples]
        axes, series = radar_series(ms, u.name, others or None, _("Media del resto"))
        self.d_radar.set_data(axes, series)

        feats = [self.service.features(s) for s in u.samples]
        dwell, errors, pooled = defaultdict(list), defaultdict(int), defaultdict(list)
        for f in feats:
            for k, v in f.dwell.items():
                dwell[k].extend(v)
            for k, v in f.metrics.get("error_counts", {}).items():
                errors[k] += v
            for k, v in f.di.items():
                if all(len(x) == 1 for x in k):
                    pooled[k].extend(v)
        self.d_heat.set_data(dict(dwell), dict(errors), self.service.keyboard_layout)

        order = sorted(u.samples, key=lambda s: s.created)
        labels = sessions_of(order)
        marks = [i for i in range(1, len(order)) if labels[i] != labels[i - 1]]
        stamp = [s.created[:16].replace("T", " ") for s in order]
        self.evo_speed.set_data([(t, self.service.features(s).metrics["wpm"]) for t, s in zip(stamp, order)], marks)
        self.evo_reg.set_data([(t, self.service.features(s).metrics["consistency"]) for t, s in zip(stamp, order)],
                              marks)
        meds = {k: median(v) for k, v in pooled.items() if len(v) >= 3}
        fast = sorted(meds.items(), key=lambda kv: kv[1])[:5]
        slow = sorted(meds.items(), key=lambda kv: -kv[1])[:5]
        self.d_digraphs.setText(_("Dígrafos más rápidos:") + "&nbsp; " + digraph_text(fast) +
                                "<br>" + _("Dígrafos más lentos:") + "&nbsp; " + digraph_text(slow))

        self.samples_table.setRowCount(0)
        for s in reversed(u.samples):
            m = self.service.features(s).metrics
            r = self.samples_table.rowCount()
            self.samples_table.insertRow(r)
            kind = {"enroll": _("registro"), "adapt": _("adaptación automática")}.get(s.kind, _("comprobación"))
            if s.free:
                kind += " (" + _("texto libre") + ")"
            vals = [s.created.replace("T", " ")[:16], kind,
                    s.text_id, f"{m['wpm']:.0f}", f"{m['accuracy']:.1f} %", m["errors_committed"]]
            for col, v in enumerate(vals):
                self.samples_table.setItem(r, col, cell(v, data=s.id if col == 0 else None))
        fit_height(self.samples_table, 12)

    # -- acciones ----------------------------------------------------------
    def _add(self):
        u = self._selected_user()
        if u:
            self.add_samples.emit(u)

    def _rename(self):
        u = self._selected_user()
        if not u:
            return
        name, ok = QInputDialog.getText(self, _("Renombrar usuario"), _("Nuevo nombre:"), text=u.name)
        name = clean_name(name)
        if ok and name and name != u.name:
            other = self.service.storage.find_by_name(name)
            if other and other.id != u.id:
                QMessageBox.warning(self, _("Renombrar"), _("Ya existe un usuario con ese nombre."))
                return
            self.service.rename_user(u.id, name)
            self.users_changed.emit()

    def _delete(self):
        u = self._selected_user()
        if not u:
            return
        ans = QMessageBox.question(self, _("Eliminar usuario"),
                                   _("¿Eliminar a «{name}» y todas sus muestras? No se puede deshacer.", name=u.name)
                                   + "\n\n" + _("Consejo: exporta antes el usuario si quieres conservar una copia."))
        if ans == QMessageBox.StandardButton.Yes:
            self.service.delete_user(u.id)
            notify(self, _("{name} eliminado", name=u.name), "warn")
            self.users_changed.emit()

    def _delete_sample(self):
        u = self._selected_user()
        rows = self.samples_table.selectionModel().selectedRows()
        if not u or not rows:
            QMessageBox.information(self, _("Eliminar muestra"), _("Selecciona una muestra de la tabla."))
            return
        sid = self.samples_table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        ans = QMessageBox.question(self, _("Eliminar muestra"),
                                   _("¿Eliminar esta muestra del perfil? Útil si la escribiste con prisa, cansado o "
                                     "con otro teclado."))
        if ans != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete_sample(u.id, sid)
        except ValueError as exc:
            QMessageBox.warning(self, _("Eliminar muestra"), str(exc))
            return
        notify(self, _("Muestra eliminada"), "warn")
        self.users_changed.emit()

    def _pdf(self):
        u = self._selected_user()
        if not u:
            return
        from ..report import user_report
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in u.name) or "usuario"
        path = QFileDialog.getSaveFileName(self, _("Informe del usuario"),
                                           str(Path.home() / f"{_('informe')}_{safe}.pdf"), "PDF (*.pdf)")[0]
        if path:
            user_report(self.service, u, Path(path), self.service.keyboard_layout)
            notify(self, _("Informe guardado"))

    def _confirm_plain_export(self) -> bool:
        if not self.service.storage.protected:
            return True
        ans = QMessageBox.question(self, _("Exportar"), _("Tus datos están protegidos con contraseña, pero el fichero "
                                                          "exportado NO estará cifrado (para poder abrirlo en otro "
                                                          "equipo). Guárdalo en un lugar seguro. ¿Continuar?"))
        return ans == QMessageBox.StandardButton.Yes

    def _export_one(self):
        u = self._selected_user()
        if not u or not self._confirm_plain_export():
            return
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in u.name) or "usuario"
        path = QFileDialog.getSaveFileName(self, _("Exportar usuario"), str(Path.home() / f"{safe}.keybio.json"),
                                           _("Usuarios de KeyBio (*.json)"))[0]
        if path:
            self.service.storage.export_users([u], Path(path))
            notify(self, _("{name} exportado", name=u.name))

    def _export_all(self):
        if not self.users:
            QMessageBox.information(self, _("Exportar"), _("No hay usuarios que exportar."))
            return
        if not self._confirm_plain_export():
            return
        path = QFileDialog.getSaveFileName(self, _("Exportar todos los usuarios"),
                                           str(Path.home() / f"{_('usuarios')}.keybio.json"),
                                           _("Usuarios de KeyBio (*.json)"))[0]
        if path:
            self.service.storage.export_users(self.users, Path(path))
            notify(self, _n("{n} usuario exportado", "{n} usuarios exportados", len(self.users)))

    def _import(self):
        path = QFileDialog.getOpenFileName(self, _("Importar usuarios"), str(Path.home()),
                                           "KeyBio (*.json *.zip);;" + _("Todos los ficheros (*)"))[0]
        if not path:
            return
        try:
            imported = self.service.storage.import_users(Path(path))
        except (OSError, ValueError, KeyError) as exc:
            QMessageBox.warning(self, _("Importar"), _("No se pudo importar el fichero:\n{error}", error=exc))
            return
        if not imported:
            QMessageBox.information(self, _("Importar"), _("El fichero no contiene usuarios."))
            return
        lines = "\n".join("• " + _n("{name}: {n} muestra nueva", "{name}: {n} muestras nuevas", n, name=name)
                          for name, n in imported)
        QMessageBox.information(self, _("Importar"), _("Importación completada:\n\n{lines}", lines=lines))
        self.users_changed.emit()
