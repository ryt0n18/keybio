"""Registro de usuarios."""

from __future__ import annotations

import statistics

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QFormLayout, QHBoxLayout, QLineEdit, QMessageBox, QStackedWidget,
                               QVBoxLayout, QWidget)

from ...capture import Sample
from ...i18n import N_, _, _n
from ...service import SENSITIVITY_NAMES, BiometricService
from ...storage import User, clean_name
from ...texts import pick_enroll_texts
from ..charts import RadarChart
from ..icons import IconLabel
from ..typing_widget import TypingPanel
from ..widgets import (AnalysisView, Badge, HBox, HeatmapCard, MetricsGrid, Stepper, button, card, card_header,
                       label, notify, page_title, page_widget, primary, radar_series, scroll)


class EnrollPage(QWidget):
    users_changed = Signal()
    go_identify = Signal()

    def __init__(self, service: BiometricService, parent=None):
        super().__init__(parent)
        self.service = service
        self.existing: User | None = None
        self.name = ""
        self.texts: list[tuple[str, str]] = []
        self.samples: list[Sample] = []
        self.stack = QStackedWidget()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.stack)
        self._build_intro()
        self._build_typing()
        self._build_interim()
        self._build_done()

    # -- vistas ---------------------------------------------------------------
    def _build_intro(self):
        w, lay = page_widget()
        lay.addWidget(page_title(_("Registrar usuario"), _("Crea un perfil biométrico a partir de tu forma de escribir."),
                                 "user_plus"))
        c, cl = card(margins=24)
        row = QHBoxLayout()
        row.setSpacing(18)
        row.addWidget(IconLabel("keyboard", "ACCENT", 48), alignment=Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        self.intro_text = label(wrap=True, rich=True)
        col.addWidget(self.intro_text)
        form = QFormLayout()
        form.setContentsMargins(0, 8, 0, 0)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(_("Nombre o alias"))
        self.name_edit.setMaxLength(40)
        self.name_edit.setMaximumWidth(360)
        self.name_edit.returnPressed.connect(self._start_new)
        form.addRow(_("Nombre:"), self.name_edit)
        col.addLayout(form)
        # La forma de teclear es un dato biométrico: hace falta el permiso de quien se registra
        col.addWidget(label(_("La forma de escribir es un dato biométrico: registra solo a personas que sepan que "
                              "KeyBio la guardará en este equipo y estén de acuerdo."), "subtitle", wrap=True))
        self.consent = QCheckBox(_("Tengo el permiso de la persona que se registra"))
        col.addWidget(self.consent)
        start = primary(_("Comenzar registro"), "arrow_right")
        start.clicked.connect(self._start_new)
        col.addWidget(HBox(start))
        row.addLayout(col, 1)
        cl.addLayout(row)
        lay.addWidget(c)

        tips, tl = card()
        tl.addWidget(card_header(_("Consejos para un buen perfil"), "help"))
        for tip in (N_("Siéntate cómodo y usa tu teclado habitual."),
                    N_("Escribe a tu ritmo normal: no es una prueba de velocidad."),
                    N_("Si te equivocas, corrige como lo harías siempre."),
                    N_("Las tildes no son obligatorias, pero puedes ponerlas.")):
            tl.addWidget(label("•  " + _(tip), "subtitle"))
        lay.addWidget(tips)
        lay.addStretch(1)
        self.stack.addWidget(w)

    def _build_typing(self):
        w, lay = page_widget()
        self.stepper = Stepper()
        lay.addWidget(self.stepper)
        self.panel = TypingPanel()
        self.panel.finished.connect(self._on_sample)
        lay.addWidget(self.panel, 1)
        cancel = button(_("Cancelar registro"), "x_circle")
        cancel.clicked.connect(self._cancel)
        restart = button(_("Reiniciar texto"), "refresh")
        restart.clicked.connect(self.panel.restart)
        lay.addWidget(HBox(cancel, restart))
        self.stack.addWidget(scroll(w))   # con letra muy grande puede no caber

    def _build_interim(self):
        inner, lay = page_widget()
        self.stepper2 = Stepper()
        lay.addWidget(self.stepper2)
        self.interim_title = label("", "title")
        self.interim_sub = label("", "subtitle", wrap=True)
        lay.addWidget(self.interim_title)
        lay.addWidget(self.interim_sub)
        self.next_btn = primary(_("Continuar"), "arrow_right")
        self.next_btn.clicked.connect(self._next)
        redo = button(_("Repetir este texto"), "refresh")
        redo.clicked.connect(self._redo)
        lay.addWidget(HBox(self.next_btn, redo))
        self.interim_analysis = AnalysisView()
        lay.addWidget(self.interim_analysis)
        lay.addStretch(1)
        self.stack.addWidget(scroll(inner))

    def _build_done(self):
        inner, lay = page_widget()
        head = QHBoxLayout()
        head.addWidget(IconLabel("check_circle", "GOOD", 40))
        texts = QVBoxLayout()
        texts.setSpacing(2)
        self.done_title = label("", "title")
        self.done_sub = label("", "subtitle", wrap=True, rich=True)
        texts.addWidget(self.done_title)
        texts.addWidget(self.done_sub)
        head.addLayout(texts, 1)
        self.done_badge = Badge()
        head.addWidget(self.done_badge, alignment=Qt.AlignmentFlag.AlignTop)
        lay.addLayout(head)
        again = primary(_("Registrar otro usuario"), "user_plus")
        again.clicked.connect(self.reset)
        ident = button(_("Probar identificación"), "scan")
        ident.clicked.connect(self.go_identify)
        lay.addWidget(HBox(again, ident))
        self.done_metrics = MetricsGrid(4)
        lay.addWidget(self.done_metrics)
        row = QHBoxLayout()
        row.setSpacing(14)
        c, cl = card()
        cl.addWidget(card_header(_("Tu huella de tecleo"), "fingerprint"))
        cl.addWidget(label(_("Rasgos principales de tu estilo, frente a la media del resto de usuarios."),
                           "small", wrap=True))
        self.done_radar = RadarChart()
        cl.addWidget(self.done_radar)
        row.addWidget(c, 2)
        self.done_heat = HeatmapCard(_("Tus teclas"))
        row.addWidget(self.done_heat, 3)
        lay.addLayout(row)
        lay.addStretch(1)
        self.stack.addWidget(scroll(inner))

    # -- flujo ------------------------------------------------------------------
    @property
    def n_samples(self) -> int:
        return int(self.service.settings.get("enroll_samples", 3))

    def refresh(self):
        self.panel.configure(bool(self.service.settings.get("show_keyboard", True)),
                             self.service.keyboard_layout)
        if self.stack.currentIndex() == 0:
            self.intro_text.setText(
                _("Escribirás <b>{n} textos cortos</b> (alrededor de un minuto cada uno). El programa mide cuánto "
                  "tiempo mantienes pulsada cada tecla, cuánto tardas entre una tecla y la siguiente, cómo usas las "
                  "mayúsculas, tus errores y cómo los corriges.", n=self.n_samples))
            self.name_edit.setFocus()

    def is_busy(self) -> bool:
        return self.stack.currentIndex() in (1, 2)

    def reset(self):
        self.panel.stop()
        self.existing = None
        self.samples = []
        self.name_edit.clear()
        self.consent.setChecked(False)
        self.stack.setCurrentIndex(0)
        self.refresh()

    def _start_new(self):
        name = clean_name(self.name_edit.text())
        if not name:
            QMessageBox.information(self, _("Registrar usuario"), _("Escribe un nombre para el usuario (sin los signos < y >)."))
            return
        existing = self.service.storage.find_by_name(name)
        if not existing and not self.consent.isChecked():
            QMessageBox.information(self, _("Registrar usuario"),
                                    _("Antes de registrar a una persona hace falta su permiso: marca la casilla "
                                      "para confirmar que lo sabe y está de acuerdo."))
            return
        if existing:
            ans = QMessageBox.question(
                self, _("Usuario existente"),
                _n("Ya existe un usuario llamado «{name}» con {n} muestra.",
                   "Ya existe un usuario llamado «{name}» con {n} muestras.", len(existing.samples), name=existing.name)
                + "\n\n" + _("¿Quieres añadir nuevas muestras a su perfil?"))
            if ans != QMessageBox.StandardButton.Yes:
                return
        self._begin(name, existing, self.n_samples)

    def start_for_user(self, user: User, n: int = 2):
        self.refresh()
        self._begin(user.name, user, n)

    def _begin(self, name: str, existing: User | None, n: int):
        self.name = name
        self.existing = existing
        used = {s.text_id for s in existing.samples} if existing else set()
        self.texts = pick_enroll_texts(n, used, self.service.text_language)
        self.samples = []
        self._show_typing()

    def _steps(self) -> list[str]:
        return [_("Texto {n}", n=i + 1) for i in range(len(self.texts))] + [_("Perfil")]

    def _show_typing(self):
        i = len(self.samples)
        tid, text = self.texts[i]
        self.stepper.set_steps(self._steps(), i)
        doing = (_("Añadiendo muestras a {name}", name=self.name) if self.existing
                 else _("Registrando a {name}", name=self.name))
        self.panel.start(text, tid, "enroll", doing + " · " + _("texto {i} de {n}", i=i + 1, n=len(self.texts)))
        self.stack.setCurrentIndex(1)
        self.panel.input.setFocus()

    def _cancel(self):
        if self.samples or (self.panel.recorder and self.panel.recorder.started):
            ans = QMessageBox.question(self, _("Cancelar registro"),
                                       _("Se perderán las muestras de esta sesión. ¿Cancelar?"))
            if ans != QMessageBox.StandardButton.Yes:
                return
        self.reset()

    def _on_sample(self, sample: Sample):
        reason = self.service.check_quality(sample)
        findings = [f for f in self.service.liveness(sample) if f.level == "bad"]
        if findings and not reason:
            reason = findings[0].message
        if reason:
            QMessageBox.warning(self, _("Muestra no válida"), reason + "\n\n" + _("Vuelve a escribir el texto con calma."))
            self.panel.restart()
            return
        self.samples.append(sample)
        f = self.service.features(sample)
        i, n = len(self.samples), len(self.texts)
        self.stepper2.set_steps(self._steps(), i)
        self.interim_title.setText(_("Texto {i} de {n} completado", i=i, n=n))
        self.interim_sub.setText(
            _("{wpm} palabras por minuto con un {accuracy} % de precisión.", wpm=f"{f.metrics['wpm']:.0f}",
              accuracy=f"{f.metrics['accuracy']:.1f}") + " "
            + (_("Revisa el análisis o continúa.") if i < n else
               _("Era el último texto: pulsa «Crear perfil» para terminar.")))
        self.next_btn.setText(_("Continuar con el texto {n}", n=i + 1) if i < n else _("Crear perfil"))
        self.interim_analysis.show_features(f, layout=self.service.keyboard_layout)
        self.stack.setCurrentIndex(2)
        self.next_btn.setFocus()

    def _redo(self):
        self.samples.pop()
        self._show_typing()

    def _next(self):
        if len(self.samples) < len(self.texts):
            self._show_typing()
        else:
            self._finish()

    def _finish(self):
        exclude = self.existing.id if self.existing else None
        similar = self.service.similar_existing(self.samples, exclude=exclude)
        if similar:
            ans = QMessageBox.question(
                self, _("Posible usuario duplicado"),
                _("Este patrón de escritura se parece mucho al de «{name}».", name=similar) + "\n\n"
                + _("Si sois la misma persona, es mejor añadir las muestras a ese usuario. ¿Guardar de todos modos?"))
            if ans != QMessageBox.StandardButton.Yes:
                return
        if self.existing:
            user = self.service.add_samples(self.existing.id, self.samples)
            title = _("Perfil de {name} actualizado", name=user.name)
        else:
            user = self.service.create_user(self.name, self.samples)
            title = _("¡{name} ya está registrado!", name=user.name)
        self.users_changed.emit()
        notify(self, title)
        self._show_done(user, title)

    def _show_done(self, user: User, title: str):
        prof = self.service.profile(user)
        level, qtext = self.service.quality(user, prof)
        ms = [self.service.features(s).metrics for s in user.samples]

        def avg(k):
            return statistics.fmean(m[k] for m in ms)

        sens = self.service.sensitivity
        self.done_title.setText(title)
        self.done_badge.set(qtext, level)
        self.done_sub.setText(
            _n("El perfil tiene <b>{n} muestra</b>.", "El perfil tiene <b>{n} muestras</b>.", len(user.samples)) + " "
            + _("Distancia típica consigo mismo <b>{m}</b> (variación {s}); umbral de aceptación ({sensitivity}) "
                "<b>{threshold}</b>.", m=f"{prof.m:.3f}", s=f"{prof.s:.3f}",
                sensitivity=_(SENSITIVITY_NAMES.get(sens, sens)) if sens != "auto" else self.service.sensitivity_label,
                threshold=f"{prof.threshold(sens):.3f}")
            + (" " + _("Añade más muestras desde «Usuarios» para hacerlo más fiable.") if level != "good" else ""))
        self.done_metrics.set_items([
            (f"{avg('wpm'):.0f}", _("Palabras por minuto"), ""),
            (f"{avg('accuracy'):.1f} %", _("Precisión media"), ""),
            (f"{avg('dwell_mean'):.0f} ms", _("Pulsación media"), ""),
            (f"{avg('flight_mean'):.0f} ms", _("Vuelo medio"), ""),
        ])
        others = [self.service.features(s).metrics for u in self.service.users() if u.id != user.id
                  for s in u.samples]
        axes, series = radar_series(ms, user.name, others or None, _("Media del resto"))
        self.done_radar.set_data(axes, series)
        dwell, errors = {}, {}
        for f in prof.features:
            for k, v in f.dwell.items():
                dwell.setdefault(k, []).extend(v)
            for k, v in f.metrics.get("error_counts", {}).items():
                errors[k] = errors.get(k, 0) + v
        self.done_heat.set_data(dwell, errors, self.service.keyboard_layout)
        self.stack.setCurrentIndex(3)
