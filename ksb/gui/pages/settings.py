"""Ajustes."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QRunnable, Qt, QThreadPool, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout, QMessageBox,
                               QProgressBar, QSpinBox, QVBoxLayout, QWidget)

from ... import APP_AUTHOR, APP_NAME, APP_VERSION, crypto, i18n, licenses_dir
from ...evaluation import Calibration, calibrate
from ...i18n import N_, _, _n
from ...matcher import SENSITIVITY
from ...service import SENSITIVITY_NAMES, BiometricService
from ...texts import MIXED, text_languages
from .. import icons
from ..dialogs import PasswordDialog
from ..keyboard import LAYOUTS
from ..updater import UpdateController
from ..widgets import (Badge, HBox, button, card, card_header, label, notify, page_title, page_widget, primary,
                       scroll)
from .common import cell, fit_height, table

THEMES = [("system", N_("Igual que el sistema")), ("light", N_("Claro")), ("dark", N_("Oscuro"))]
SCALES = [(1.0, N_("Normal")), (1.15, N_("Grande")), (1.3, N_("Muy grande"))]


def restart_app() -> None:
    """Vuelve a abrir KeyBio (el ejecutable empaquetado o desde el código) y cierra este."""
    args = sys.argv[1:] if getattr(sys, "frozen", False) else sys.argv
    if QProcess.startDetached(sys.executable, args):
        QApplication.instance().quit()


class _CalSignals(QObject):
    done = Signal(object)


class _CalTask(QRunnable):
    def __init__(self, data, extra):
        super().__init__()
        self.data, self.extra = data, extra
        self.signals = _CalSignals()

    def run(self):
        try:
            res = calibrate(self.data, extra=self.extra)
        except Exception as exc:
            res = exc
        self.signals.done.emit(res)


class SettingsPage(QWidget):
    settings_changed = Signal()
    appearance_changed = Signal()
    users_changed = Signal()

    SENS_TEXT = {
        "estricto": N_("Estricto: casi nunca confunde a un desconocido con un usuario, pero rechaza más a menudo a "
                       "usuarios legítimos."),
        "normal": N_("Normal: equilibrio entre ambos tipos de error."),
        "permisivo": N_("Permisivo: reconoce mejor a los usuarios registrados aunque escriban distinto ese día, a "
                        "costa de aceptar más impostores."),
        "auto": N_("Automática: umbral y pesos calculados con vuestros propios datos (calibración de abajo)."),
    }

    def __init__(self, service: BiometricService, parent=None):
        super().__init__(parent)
        self.service = service
        self._cal: Calibration | None = None
        self._task = None
        inner, lay = page_widget()
        lay.addWidget(page_title(_("Ajustes"), "", "settings"))

        # -- apariencia
        c, cl = card()
        cl.addWidget(card_header(_("Apariencia e idioma"), "sun"))
        form = self._form()
        self.ui_lang = QComboBox()
        self.ui_lang.setIconSize(icons.FLAG_SIZE)
        self.ui_lang.addItem(icons.blank_flag(), _("Automático (idioma del sistema)"), "auto")
        for code, name in i18n.LANGUAGES.items():
            self.ui_lang.addItem(icons.flag_icon(code), name, code)
        self.ui_lang.currentIndexChanged.connect(self._save_language)
        form.addRow(_("Idioma:"), self.ui_lang)
        self.theme = QComboBox()
        for key, text in THEMES:
            self.theme.addItem(_(text), key)
        self.theme.currentIndexChanged.connect(self._save_appearance)
        form.addRow(_("Tema:"), self.theme)
        self.scale = QComboBox()
        for key, text in SCALES:
            self.scale.addItem(_(text), key)
        self.scale.currentIndexChanged.connect(self._save_appearance)
        form.addRow(_("Tamaño del texto:"), self.scale)
        self.show_kb = QCheckBox(_("Mostrar el teclado en pantalla mientras escribes"))
        self.show_kb.toggled.connect(self._save)
        form.addRow("", self.show_kb)
        self.layout_combo = QComboBox()
        self.layout_combo.addItem(_("Automático (según el idioma)"), "auto")
        for key, data in LAYOUTS.items():
            self.layout_combo.addItem(_(data["name"]), key)
        self.layout_combo.currentIndexChanged.connect(self._save)
        form.addRow(_("Distribución del teclado:"), self.layout_combo)
        cl.addLayout(form)
        lay.addWidget(c)

        # -- identificación
        c, cl = card()
        cl.addWidget(card_header(_("Identificación"), "target"))
        form = self._form()
        self.sens = QComboBox()
        for k in SENSITIVITY:
            self.sens.addItem(_(SENSITIVITY_NAMES[k]).capitalize(), k)
        self.sens.addItem(_("Automática (calibrada con tus datos)"), "auto")
        self.sens.currentIndexChanged.connect(self._save)
        form.addRow(_("Sensibilidad:"), self.sens)
        self.adapt = QCheckBox(_("Adaptar el perfil automáticamente con las comprobaciones muy seguras"))
        self.adapt.setToolTip(_("Si te reconoce con confianza alta y sin sospechas, la muestra se añade a tu perfil. "
                                "Así se adapta a cómo escribes en distintos días. Se puede deshacer marcando el "
                                "resultado como incorrecto."))
        self.adapt.toggled.connect(self._save)
        form.addRow("", self.adapt)
        self.live = QCheckBox(_("Mostrar la identificación en directo mientras escribes"))
        self.live.toggled.connect(self._save)
        form.addRow("", self.live)
        self.early = QCheckBox(_("Terminar en cuanto el resultado esté claro, sin escribir el texto entero"))
        self.early.setToolTip(_("Usa la identificación en directo: si tu forma de escribir ya coincide claramente "
                                "con un perfil (o con ninguno), la comprobación termina antes."))
        self.early.toggled.connect(self._save)
        form.addRow("", self.early)
        cl.addLayout(form)
        self.sens_help = label("", "subtitle", wrap=True)
        cl.addWidget(self.sens_help)
        lay.addWidget(c)

        # -- calibración
        c, cl = card()
        cl.addWidget(card_header(_("Calibración automática"), "gauge"))
        cl.addWidget(label(_(
            "Busca el umbral y el peso de cada medida que menos errores comete <b>con los usuarios de este equipo</b>: "
            "cada muestra guardada se compara con su propio perfil (sin ella) y con los de los demás, y se suman las "
            "comprobaciones que hayas marcado como correctas o incorrectas. Hacen falta al menos 3 usuarios con 3 "
            "muestras."), "subtitle", wrap=True, rich=True))
        self.cal_btn = primary(_("Calcular con mis datos"), "refresh")
        self.cal_btn.clicked.connect(self._calibrate)
        self.cal_apply = button(_("Aplicar recomendación"), "check")
        self.cal_apply.clicked.connect(self._apply_calibration)
        self.cal_apply.setEnabled(False)
        cl.addWidget(HBox(self.cal_btn, self.cal_apply))
        self.cal_msg = label("", "small", wrap=True, rich=True)
        cl.addWidget(self.cal_msg)
        self.cal_table = table([_("Sensibilidad"), _("Desconocidos aceptados (FAR)"), _("Legítimos rechazados (FRR)")])
        self.cal_table.setVisible(False)
        cl.addWidget(self.cal_table)
        lay.addWidget(c)

        # -- registro
        c, cl = card()
        cl.addWidget(card_header(_("Registro y textos"), "user_plus"))
        form = self._form()
        self.n_samples = QSpinBox()
        self.n_samples.setRange(2, 8)
        self.n_samples.valueChanged.connect(self._save)
        form.addRow(_("Textos por registro:"), self.n_samples)
        self.min_acc = QSpinBox()
        self.min_acc.setRange(50, 100)
        self.min_acc.setSuffix(" %")
        self.min_acc.valueChanged.connect(self._save)
        form.addRow(_("Precisión mínima de una muestra:"), self.min_acc)
        self.lang = QComboBox()
        self.lang.setIconSize(icons.FLAG_SIZE)
        self.lang.addItem(icons.blank_flag(), _("Automático (el de la interfaz)"), "auto")
        for code in text_languages():
            if code == MIXED:
                self.lang.addItem(icons.blank_flag(), _("Español e inglés"), code)
            else:
                self.lang.addItem(icons.flag_icon(code), i18n.LANGUAGES[code], code)
        self.lang.currentIndexChanged.connect(self._save)
        form.addRow(_("Idioma de los textos:"), self.lang)
        cl.addLayout(form)
        cl.addWidget(label(_("Más textos dan un perfil más fiable; lo ideal es registrarse en dos sesiones de días "
                             "distintos. Las muestras con demasiados errores o sospechosas se descartan."),
                           "subtitle", wrap=True))
        lay.addWidget(c)

        # -- protección
        c, cl = card()
        cl.addWidget(card_header(_("Protección con contraseña"), "shield"))
        self.prot_badge = Badge()
        self.prot_text = label("", "subtitle", wrap=True)
        cl.addWidget(HBox(self.prot_badge))
        cl.addWidget(self.prot_text)
        self.prot_on = primary(_("Activar protección"), "shield")
        self.prot_on.clicked.connect(self._enable_protection)
        self.prot_change = button(_("Cambiar contraseña"), "edit")
        self.prot_change.clicked.connect(self._change_password)
        self.prot_off = button(_("Quitar protección"), "x_circle", "danger")
        self.prot_off.clicked.connect(self._disable_protection)
        cl.addWidget(HBox(self.prot_on, self.prot_change, self.prot_off))
        lay.addWidget(c)

        # -- datos
        c, cl = card()
        cl.addWidget(card_header(_("Datos y copias de seguridad"), "file"))
        self.path = label("", "subtitle", wrap=True)
        self.path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        cl.addWidget(self.path)
        open_btn = button(_("Abrir carpeta de datos"), "file")
        open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.service.storage.root))))
        backup = button(_("Crear copia de seguridad…"), "download")
        backup.clicked.connect(self._backup)
        restore = button(_("Restaurar usuarios desde copia…"), "upload")
        restore.clicked.connect(self._restore)
        cl.addWidget(HBox(open_btn, backup, restore))
        cl.addWidget(label(_("Todo se guarda solo en este equipo y tus datos nunca se envían por la red. Las copias "
                             "(.zip) sirven también para pasar los perfiles entre Linux, Windows y macOS; se guardan "
                             "sin cifrar."), "subtitle", wrap=True))
        lay.addWidget(c)

        # -- actualizaciones (solo se conecta al pulsar el botón)
        c, cl = card()
        cl.addWidget(card_header(_("Actualizaciones"), "refresh"))
        cl.addWidget(label(_("Versión instalada: {version}", version=APP_VERSION), "subtitle"))
        cl.addWidget(label(_("KeyBio solo se conecta a internet cuando pulsas «Buscar actualizaciones»: consulta en "
                             "GitHub si hay una versión nueva y, si quieres, la descarga. No envía ningún dato tuyo."),
                           "small", wrap=True))
        self.updater = UpdateController(self)
        self.check_btn = button(_("Buscar actualizaciones"), "refresh")
        self.check_btn.clicked.connect(self.updater.check)
        self.install_btn = primary(_("Actualizar ahora"), "download")
        self.install_btn.clicked.connect(self._install_update)
        self.notes_btn = button(_("Ver novedades"), "file")
        self.notes_btn.clicked.connect(self.updater.open_page)
        for b in (self.install_btn, self.notes_btn):
            b.setVisible(False)
        cl.addWidget(HBox(self.check_btn, self.install_btn, self.notes_btn))
        self.update_bar = QProgressBar()
        self.update_bar.setTextVisible(False)
        self.update_bar.setVisible(False)
        cl.addWidget(self.update_bar)
        self.update_status = label("", "subtitle", wrap=True)
        cl.addWidget(self.update_status)
        self.updater.status.connect(self._update_status)
        self.updater.found.connect(self._update_found)
        self.updater.progress.connect(self._update_progress)
        self.updater.message.connect(lambda text: QMessageBox.information(self, APP_NAME, text))
        self.updater.quit_requested.connect(QApplication.instance().quit)
        self.updater.restart_requested.connect(restart_app)
        lay.addWidget(c)

        # -- cómo funciona
        c, cl = card()
        cl.addWidget(card_header(_("Cómo funciona"), "help"))
        cl.addWidget(label(_(
            "Por cada pulsación se registra el instante en que se pulsa y se suelta la tecla, con precisión de "
            "microsegundos. De ahí se obtienen el <b>tiempo de pulsación</b> de cada tecla, el <b>intervalo</b> y el "
            "<b>tiempo de vuelo</b> entre teclas, la duración de los <b>dígrafos y trígrafos</b>, el uso de "
            "<b>shift</b>, los <b>errores</b> y la forma de <b>corregirlos</b>.<br><br>"
            "Para comparar textos distintos se usan las medidas <b>R</b> (orden relativo de las combinaciones de "
            "teclas de más rápida a más lenta) y <b>A</b> (diferencia de duraciones) de Gunetti y Picardi, también "
            "sobre los tiempos de vuelo, junto con una distancia estadística sobre los rasgos globales. Cada usuario "
            "tiene un umbral propio calculado con validación deja-uno-fuera (deja-una-sesión-fuera si hay varias); si "
            "la muestra no entra en el umbral de nadie, se considera un usuario no registrado. Además se rechazan "
            "muestras con ritmo robótico o que repiten exactamente otra guardada.<br><br>"
            "<b>Atajos:</b> Ctrl+1…7 cambian de sección · Ctrl+T cambia el tema · F11 pantalla completa."),
            "subtitle", wrap=True, rich=True))
        cl.addWidget(label(f"{APP_NAME} {APP_VERSION} · © 2026 {APP_AUTHOR}. " + _("Todos los derechos reservados.")
                           + " " + _("Incluye Qt for Python (PySide6) y Qt, que se distribuyen bajo la licencia GNU "
                                     "LGPL versión 3."), "small", wrap=True))
        lic = button(_("Licencias de terceros"), "file")
        lic.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(licenses_dir()))))
        cl.addWidget(HBox(lic))
        lay.addWidget(c)
        lay.addStretch(1)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll(inner))

    @staticmethod
    def _form() -> QFormLayout:
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        return form

    def showEvent(self, e):
        super().showEvent(e)
        for w in (self.ui_lang, self.theme, self.scale, self.layout_combo, self.sens, self.n_samples, self.min_acc,
                  self.lang):
            w.setMaximumWidth(400)

    def refresh(self):
        s = self.service.settings
        widgets = (self.ui_lang, self.theme, self.scale, self.show_kb, self.layout_combo, self.sens, self.n_samples,
                   self.min_acc, self.adapt, self.live, self.early, self.lang)
        for w in widgets:
            w.blockSignals(True)
        self.ui_lang.setCurrentIndex(max(0, self.ui_lang.findData(s.get("language", "auto"))))
        self.theme.setCurrentIndex(max(0, self.theme.findData(s.get("theme", "system"))))
        scale = float(s.get("font_scale", 1.0))
        self.scale.setCurrentIndex(min(range(len(SCALES)), key=lambda i: abs(SCALES[i][0] - scale)))
        self.show_kb.setChecked(bool(s.get("show_keyboard", True)))
        self.layout_combo.setCurrentIndex(max(0, self.layout_combo.findData(s.get("keyboard_layout", "auto"))))
        self.sens.setCurrentIndex(max(0, self.sens.findData(s.get("sensitivity", "normal"))))
        self.n_samples.setValue(int(s.get("enroll_samples", 3)))
        self.min_acc.setValue(int(s.get("min_accuracy", 80)))
        self.adapt.setChecked(bool(s.get("auto_adapt", True)))
        self.live.setChecked(bool(s.get("live_identify", True)))
        self.early.setChecked(bool(s.get("early_stop", True)))
        self.early.setEnabled(self.live.isChecked())
        self.lang.setCurrentIndex(max(0, self.lang.findData(s.get("text_language", "auto"))))
        for w in widgets:
            w.blockSignals(False)
        self._update_sens_help()
        self.path.setText(_("Carpeta: {path}", path=self.service.storage.root))
        self._refresh_protection()

    def _update_sens_help(self):
        key = self.sens.currentData()
        text = _(self.SENS_TEXT[key]) if key in self.SENS_TEXT else ""
        if key == "auto":
            s = self.service.settings
            text += " " + _("Valores actuales: K = {k}, peso de las combinaciones de teclas {weight} %.",
                            k=f"{float(s.get('auto_k', 2.0)):.1f}", weight=f"{float(s.get('auto_weight', 0.55)) * 100:.0f}")
            if not s.get("calibrated_at"):
                text += " " + _("Todavía no se ha calibrado: usa «Calcular con mis datos».")
        self.sens_help.setText(text)

    def _save(self):
        s = self.service.settings
        s["sensitivity"] = self.sens.currentData()
        s["enroll_samples"] = self.n_samples.value()
        s["min_accuracy"] = self.min_acc.value()
        s["show_keyboard"] = self.show_kb.isChecked()
        s["keyboard_layout"] = self.layout_combo.currentData()
        s["auto_adapt"] = self.adapt.isChecked()
        s["live_identify"] = self.live.isChecked()
        s["early_stop"] = self.early.isChecked()
        self.early.setEnabled(self.live.isChecked())
        s["text_language"] = self.lang.currentData()
        self.service.save_settings()
        self._update_sens_help()
        self.settings_changed.emit()

    def _save_language(self):
        code = self.ui_lang.currentData()
        if code == self.service.settings.get("language", "auto"):
            return
        self.service.settings["language"] = code
        self.service.save_settings()
        ans = QMessageBox.question(self, _("Idioma"), _("El idioma cambiará al reiniciar KeyBio. ¿Reiniciar ahora?"))
        if ans == QMessageBox.StandardButton.Yes:
            restart_app()

    def _save_appearance(self):
        s = self.service.settings
        s["theme"] = self.theme.currentData()
        s["font_scale"] = self.scale.currentData()
        self.service.save_settings()
        self.appearance_changed.emit()

    # -- calibración ----------------------------------------------------------
    def _calibrate(self):
        self.cal_btn.setEnabled(False)
        self.cal_apply.setEnabled(False)
        self.cal_msg.setText(_("Calculando… (puede tardar unos segundos con muchos usuarios)"))
        task = _CalTask(self.service.evaluation_input(), self.service.history_trials())
        task.signals.done.connect(self._calibrated)
        self._task = task
        QThreadPool.globalInstance().start(task)

    def _calibrated(self, res):
        self.cal_btn.setEnabled(True)
        if isinstance(res, Exception):
            self.cal_msg.setText(_("No se pudo calibrar: {error}", error=res))
            return
        self._cal = res
        self.cal_table.setVisible(True)
        self.cal_table.setRowCount(0)
        rows = [(_(SENSITIVITY_NAMES[k]).capitalize(), *res.levels[k]) for k in SENSITIVITY if k in res.levels]
        recommended = _("Recomendada")
        if res.enough:
            rows.append((recommended, res.far, res.frr))
        for name, far, frr in rows:
            r = self.cal_table.rowCount()
            self.cal_table.insertRow(r)
            for col, v in enumerate((name, f"{far * 100:.1f} %", f"{frr * 100:.1f} %")):
                self.cal_table.setItem(r, col, cell(v, bold=name == recommended))
        fit_height(self.cal_table, 6)
        if res.enough:
            self.cal_msg.setText(
                res.message + " " + _("Recomendación: <b>K = {k}</b> y peso de las combinaciones de teclas "
                                      "<b>{weight} %</b>. Son estimaciones con pocos datos: revísalas cuando haya más "
                                      "usuarios o comprobaciones verificadas.", k=f"{res.k:.1f}",
                                      weight=f"{res.weight * 100:.0f}"))
            self.cal_apply.setEnabled(True)
        else:
            self.cal_msg.setText(res.message + " " + _("Mientras tanto se muestran las tasas de los niveles fijos."))

    def _apply_calibration(self):
        if not self._cal or not self._cal.enough:
            return
        self.service.apply_calibration(self._cal)
        self.service.settings["calibrated_at"] = datetime.now().isoformat(timespec="seconds")
        self.service.save_settings()
        self.refresh()
        self.settings_changed.emit()
        notify(self, _("Sensibilidad automática aplicada"))

    # -- protección -----------------------------------------------------------
    def _refresh_protection(self):
        st = self.service.storage
        if not crypto.AVAILABLE:
            self.prot_badge.set(_("No disponible"), "warn")
            self.prot_text.setText(_("Falta el paquete «cryptography». Instálalo con: pip install cryptography"))
            for b in (self.prot_on, self.prot_change, self.prot_off):
                b.setEnabled(False)
            return
        on = st.protected
        self.prot_badge.set(_("Protegido") if on else _("Sin proteger"), "good" if on else "warn")
        self.prot_text.setText(
            _("Los perfiles y el historial se guardan cifrados (AES) y se pide la contraseña al abrir el programa. "
              "Si la olvidas no se pueden recuperar: haz una copia de seguridad.") if on else
            _("Los perfiles biométricos se guardan sin cifrar. Con una contraseña se cifran y nadie puede leerlos "
              "sin ella, aunque tenga acceso a tus ficheros."))
        self.prot_on.setVisible(not on)
        self.prot_change.setVisible(on)
        self.prot_off.setVisible(on)

    def _enable_protection(self):
        dlg = PasswordDialog("new", self)
        if dlg.exec():
            self.service.storage.enable_protection(dlg.password)
            self._refresh_protection()
            notify(self, _("Datos cifrados con contraseña"))

    def _change_password(self):
        dlg = PasswordDialog("new", self)
        if dlg.exec():
            self.service.storage.change_password(dlg.password)
            notify(self, _("Contraseña cambiada"))

    def _disable_protection(self):
        ans = QMessageBox.question(self, _("Quitar protección"),
                                   _("Los perfiles y el historial se guardarán sin cifrar. ¿Continuar?"))
        if ans == QMessageBox.StandardButton.Yes:
            self.service.storage.disable_protection()
            self._refresh_protection()
            notify(self, _("Protección desactivada"), "warn")

    # -- copias -------------------------------------------------------------
    def _update_status(self, text: str, kind: str) -> None:
        self.update_status.setText(text)
        if kind != "muted":   # terminó (bien o mal): se puede volver a pulsar
            self.check_btn.setEnabled(True)
            self.install_btn.setEnabled(True)

    def _update_found(self, release) -> None:
        for b in (self.install_btn, self.notes_btn):
            b.setVisible(release is not None)

    def _update_progress(self, pct: int) -> None:
        self.update_bar.setVisible(pct >= 0)
        if pct >= 0:
            self.update_bar.setValue(pct)

    def _install_update(self) -> None:
        self.install_btn.setEnabled(False)
        self.check_btn.setEnabled(False)
        self.updater.update()

    def _backup(self):
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        path = QFileDialog.getSaveFileName(self, _("Crear copia de seguridad"),
                                           str(Path.home() / f"keybio_copia_{stamp}.zip"),
                                           _("Copia de KeyBio (*.zip)"))[0]
        if path:
            self.service.storage.export_backup(Path(path))
            notify(self, _("Copia de seguridad creada"))

    def _restore(self):
        path = QFileDialog.getOpenFileName(self, _("Restaurar usuarios"), str(Path.home()),
                                           "KeyBio (*.zip *.json);;" + _("Todos los ficheros (*)"))[0]
        if not path:
            return
        try:
            imported = self.service.storage.import_users(Path(path))
        except Exception as exc:
            QMessageBox.warning(self, _("Restaurar"), _("No se pudo leer la copia:\n{error}", error=exc))
            return
        lines = "\n".join("• " + _n("{name}: {n} muestra nueva", "{name}: {n} muestras nuevas", n, name=name)
                          for name, n in imported) or _("Nada que importar.")
        QMessageBox.information(self, _("Restaurar"), _("Usuarios restaurados:\n\n{lines}", lines=lines))
        self.users_changed.emit()
