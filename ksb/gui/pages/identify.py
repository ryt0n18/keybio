"""Identificación (1:N) y verificación de identidad (1:1), con texto fijo o libre."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QInputDialog, QMessageBox,
                               QProgressBar, QStackedWidget, QVBoxLayout, QWidget)

from ...capture import TYPING_KINDS, Sample
from ...features import SampleFeatures
from ...i18n import _, _n
from ...liveness import Finding, is_blocking
from ...matcher import Candidate, Identification, early_decision
from ...service import MIN_TYPING_KEYS, BiometricService
from ...texts import pick_verify_text
from .. import theme
from ..charts import Gauge, RadarChart
from ..icons import IconLabel
from ..typing_widget import TypingPanel
from ..widgets import (AnalysisView, HBox, Segmented, SimilarityList, Tile, button, card, card_header, label,
                       notify, page_title, page_widget, primary, radar_series, scroll, set_status)
from .common import cell, fit_height, table

LIVE_MIN_KEYS = 50       # pulsaciones antes de la primera estimación en directo
LIVE_STEP_KEYS = 15      # nueva estimación cada N pulsaciones


class _LiveSignals(QObject):
    done = Signal(int, object)


class _LiveTask(QRunnable):
    """Identifica una muestra parcial en segundo plano (no bloquea la captura de teclas)."""

    def __init__(self, seq: int, service: BiometricService, sample: Sample, profiles):
        super().__init__()
        self.seq, self.service, self.sample, self.profiles = seq, service, sample, profiles
        self.signals = _LiveSignals()

    def run(self):
        try:
            res = self.service.identify_partial(self.sample, self.profiles)
        except Exception as exc:  # una estimación fallida no debe interrumpir la escritura
            res = exc
        self.signals.done.emit(self.seq, res)


class IdentifyPage(QWidget):
    users_changed = Signal()
    go_enroll = Signal()

    def __init__(self, service: BiometricService, parent=None):
        super().__init__(parent)
        self.service = service
        self.last_text: str | None = None
        self.sample: Sample | None = None
        self.features: SampleFeatures | None = None
        self.result: Identification | None = None
        self.claimed: Candidate | None = None
        self.shown: Candidate | None = None
        self.findings: list[Finding] = []
        self.adapted = None
        self.mode = "identify"
        self._n_users = 0
        self.entry: dict | None = None
        self._verdict_text = ("", "")
        self._live_profiles = []
        self._live_seq = 0
        self._live_keys = 0
        self._live_busy = False
        self._live_task = None
        self._early = False      # la última comprobación terminó antes del final del texto
        self.stack = QStackedWidget()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.stack)
        self._build_intro()
        self._build_typing()
        self._build_result()
        self._live_timer = QTimer(self)
        self._live_timer.setInterval(900)
        self._live_timer.timeout.connect(self._live_tick)

    # -- vistas ---------------------------------------------------------------
    def _build_intro(self):
        w, lay = page_widget()
        lay.addWidget(page_title(_("Identificar"), _("Escribe un texto y el sistema dirá quién eres por tu forma de "
                                                    "teclear."), "scan"))
        c, cl = card(margins=24)
        cl.addWidget(label(_("Modo de comprobación"), "section"))
        self.mode_sel = Segmented([_("¿Quién soy?  (identificación)"), _("Soy…  (verificación 1:1)"),
                                   _("Desafío  (imitar a otra persona)")])
        self.mode_sel.changed.connect(self._mode_changed)
        cl.addWidget(self.mode_sel)
        self.claim_row = QWidget()
        cr = QHBoxLayout(self.claim_row)
        cr.setContentsMargins(0, 4, 0, 0)
        self.claim_label = label(_("Usuario que dices ser:"))
        cr.addWidget(self.claim_label)
        self.claim_combo = QComboBox()
        self.claim_combo.setMinimumWidth(220)
        self.claim_combo.currentIndexChanged.connect(lambda _: self._update_mode_help())
        cr.addWidget(self.claim_combo)
        self.challenger_label = label(_("Tú eres:"))
        cr.addWidget(self.challenger_label)
        self.challenger_combo = QComboBox()
        self.challenger_combo.setMinimumWidth(200)
        cr.addWidget(self.challenger_combo)
        cr.addStretch(1)
        cl.addWidget(self.claim_row)
        self.mode_help = label("", "subtitle", wrap=True, rich=True)
        cl.addWidget(self.mode_help)
        self.free_check = QCheckBox(_("Texto libre: escribir lo que yo quiera en lugar de copiar un texto"))
        self.free_check.setToolTip(_("El análisis es independiente del texto, así que puedes escribir cualquier cosa. "
                                     "Hacen falta al menos 280 caracteres."))
        cl.addWidget(self.free_check)
        self.intro_info = label(wrap=True, rich=True)
        cl.addWidget(self.intro_info)
        self.start_btn = primary(_("Comenzar comprobación"), "arrow_right")
        self.start_btn.clicked.connect(self.start)
        cl.addWidget(HBox(self.start_btn))
        lay.addWidget(c)
        lay.addStretch(1)
        self.stack.addWidget(w)
        self._mode_changed(0)

    def _build_typing(self):
        w, lay = page_widget()
        self.live = QFrame()
        self.live.setObjectName("card")
        ll = QHBoxLayout(self.live)
        ll.setContentsMargins(14, 8, 14, 8)
        ll.addWidget(IconLabel("activity", "ACCENT", 20))
        self.live_text = label("", "small", rich=True)
        ll.addWidget(self.live_text, 1)
        self.live_bar = QProgressBar()
        self.live_bar.setTextVisible(False)
        self.live_bar.setFixedWidth(180)
        self.live_bar.setRange(0, 100)
        ll.addWidget(self.live_bar)
        lay.addWidget(self.live)
        self.panel = TypingPanel()
        self.panel.finished.connect(self._on_sample)
        lay.addWidget(self.panel, 1)
        cancel = button(_("Cancelar"), "x_circle")
        cancel.clicked.connect(self.reset)
        restart = button(_("Reiniciar texto"), "refresh")
        restart.clicked.connect(self._restart_typing)
        lay.addWidget(HBox(cancel, restart))
        self.stack.addWidget(scroll(w))   # con letra muy grande puede no caber

    def _build_result(self):
        inner, lay = page_widget()
        self.verdict, vl = card(margins=22)
        top = QHBoxLayout()
        top.setSpacing(18)
        self.gauge = Gauge()
        top.addWidget(self.gauge, alignment=Qt.AlignmentFlag.AlignTop)
        texts = QVBoxLayout()
        texts.setSpacing(6)
        title_row = QHBoxLayout()
        self.verdict_icon = IconLabel("check_circle", "GOOD", 30)
        self.verdict_title = label("", "hero")
        self.verdict_title.setWordWrap(True)
        title_row.addWidget(self.verdict_icon)
        title_row.addWidget(self.verdict_title, 1)
        texts.addLayout(title_row)
        self.verdict_sub = label("", "subtitle", wrap=True, rich=True)
        texts.addWidget(self.verdict_sub)
        self.feedback_q = label(_("¿Es correcto el resultado?"))
        self.yes_btn = button(_("Sí, es correcto"), "check")
        self.no_btn = button(_("No, es incorrecto"), "x_circle")
        self.yes_btn.clicked.connect(self._feedback_yes)
        self.no_btn.clicked.connect(self._feedback_no)
        self.feedback_row = HBox(self.feedback_q, self.yes_btn, self.no_btn)
        texts.addWidget(self.feedback_row)
        self.adapt_btn = primary("", "plus")
        self.adapt_btn.clicked.connect(self._adapt)
        self.enroll_btn = primary(_("Registrarme ahora"), "user_plus")
        self.enroll_btn.clicked.connect(self.go_enroll)
        self.feedback_done = label("", "small", wrap=True)
        texts.addWidget(HBox(self.adapt_btn, self.enroll_btn))
        texts.addWidget(self.feedback_done)
        texts.addStretch(1)
        top.addLayout(texts, 1)
        vl.addLayout(top)
        lay.addWidget(self.verdict)

        again = primary(_("Nueva comprobación"), "refresh")
        again.clicked.connect(self.start)
        back = button(_("Volver"), "arrow_right")
        back.clicked.connect(self.reset)
        pdf = button(_("Guardar informe PDF"), "download")
        pdf.clicked.connect(self._save_pdf)
        lay.addWidget(HBox(again, back, pdf))

        row = QHBoxLayout()
        row.setSpacing(14)
        c, cl = card()
        cl.addWidget(card_header(_("¿Por qué?"), "help"))
        self.why_sub = label("", "small", wrap=True)
        cl.addWidget(self.why_sub)
        self.similarity = SimilarityList()
        cl.addWidget(self.similarity)
        cl.addStretch(1)
        row.addWidget(c, 3)
        c, cl = card()
        cl.addWidget(card_header(_("Huella de tecleo"), "fingerprint"))
        self.radar = RadarChart()
        cl.addWidget(self.radar)
        cl.addWidget(label(_("Componentes de la distancia"), "section"))
        parts = QHBoxLayout()
        self.t_ra = Tile(None, _("Combinaciones de teclas"))
        self.t_z = Tile(None, _("Rasgos estadísticos"))
        self.t_ra.setToolTip(_("Medidas R y A: qué combinaciones de teclas son rápidas o lentas y cuánto duran "
                               "(incluido el tiempo de vuelo). 0 = idéntico, 1 = nada parecido."))
        self.t_z.setToolTip(_("Velocidad, tiempos de pulsación, solapamiento, uso del shift, errores… "
                              "0 = idéntico, 1 = nada parecido."))
        parts.addWidget(self.t_ra)
        parts.addWidget(self.t_z)
        cl.addLayout(parts)
        cl.addStretch(1)
        row.addWidget(c, 2)
        lay.addLayout(row)

        c, cl = card()
        cl.addWidget(card_header(_("Comparación con todos los usuarios"), "users"))
        cl.addWidget(label(_("Distancia: 0 = idéntico. Cada usuario tiene su propio umbral, calculado a partir de "
                             "lo mucho o poco que varía su forma de escribir. «Ritmo» compara las combinaciones de "
                             "teclas (medidas R/A) y «Estadística» el resto de rasgos."), "small", wrap=True))
        self.ranking = table([_("Usuario"), _("Distancia"), _("Umbral"), _("Ritmo"), _("Estadística"), _("Confianza"),
                              _("Resultado")])
        cl.addWidget(self.ranking)
        lay.addWidget(c)

        lay.addWidget(label(_("Análisis de la muestra"), "title"))
        self.analysis = AnalysisView()
        lay.addWidget(self.analysis)
        lay.addStretch(1)
        self.stack.addWidget(scroll(inner))

    # -- flujo ------------------------------------------------------------------
    def _mode_changed(self, idx: int):
        self.mode = ("identify", "verify", "challenge")[idx]
        self.claim_row.setVisible(self.mode != "identify")
        self.claim_label.setText(_("Persona a imitar:") if self.mode == "challenge" else _("Usuario que dices ser:"))
        self.challenger_label.setVisible(self.mode == "challenge")
        self.challenger_combo.setVisible(self.mode == "challenge")
        self._update_mode_help()
        self._update_intro()

    def _update_mode_help(self):
        if self.mode == "verify":
            self.mode_help.setText(_("Dices quién eres y el sistema comprueba si tu forma de escribir coincide con "
                                     "<b>ese</b> perfil, como al iniciar sesión."))
        elif self.mode == "challenge":
            self.mode_help.setText(_("Intenta escribir como otra persona para engañar a KeyBio. Los intentos se guardan "
                                     "(sin tocar ningún perfil) y la calibración los usa para aprender a rechazar "
                                     "imitaciones.") + self._challenge_hint())
        else:
            self.mode_help.setText(_("El sistema compara tu forma de escribir con <b>todos</b> los perfiles y dice "
                                     "quién eres, o que no estás registrado."))

    def _challenge_hint(self) -> str:
        """Pista sobre cómo escribe la persona a imitar (para que la imitación sea realista)."""
        user = self.service.storage.get_user(self.claim_combo.currentData()) if self.claim_combo.currentData() else None
        if user is None or len(user.samples) < 2:
            return ""
        metrics = [f.metrics for f in self.service.profile(user).features]
        avg = lambda k: sum(m[k] for m in metrics) / len(metrics)  # noqa: E731
        return "<br>" + _("<b>Pista:</b> {name} escribe a unas <b>{cpm}</b> pulsaciones por minuto, mantiene cada "
                          "tecla unos <b>{dwell} ms</b> y pulsa la siguiente antes de soltar la anterior el "
                          "<b>{overlap} %</b> de las veces.", name=user.name, cpm=f"{avg('cpm'):.0f}",
                          dwell=f"{avg('dwell_mean'):.0f}", overlap=f"{avg('rollover_pct'):.0f}")

    def refresh(self):
        self.panel.configure(bool(self.service.settings.get("show_keyboard", True)),
                             self.service.keyboard_layout)
        if self.stack.currentIndex() != 0:
            return
        users = [u for u in self.service.users() if len(u.samples) >= 2]
        current = self.claim_combo.currentData()
        self.claim_combo.clear()
        for u in users:
            self.claim_combo.addItem(u.name, u.id)
        if current:
            self.claim_combo.setCurrentIndex(max(0, self.claim_combo.findData(current)))
        current = self.challenger_combo.currentData()
        self.challenger_combo.clear()
        self.challenger_combo.addItem(_("No estoy registrado"), None)
        for u in users:
            self.challenger_combo.addItem(u.name, u.id)
        if current:
            self.challenger_combo.setCurrentIndex(max(0, self.challenger_combo.findData(current)))
        self._update_mode_help()
        self._n_users = len(users)
        self._update_intro()

    def _update_intro(self):
        n = self._n_users
        if not n:
            self.intro_info.setText(_("Todavía no hay usuarios registrados. Registra al menos uno en la sección "
                                      "<b>Registrar</b>."))
            self.start_btn.setEnabled(False)
            return
        adapt = (" " + _("Si te reconoce con mucha seguridad, la muestra se añade sola a tu perfil para que se "
                         "adapte a ti (puedes deshacerlo).") if self.service.settings.get("auto_adapt", True)
                 and self.mode != "challenge" else "")
        self.intro_info.setText(
            _n("Hay <b>{n} usuario registrado</b>.", "Hay <b>{n} usuarios registrados</b>.", n) + " "
            + _("Escribe con naturalidad.") + adapt + "<br>"
            + _("Sensibilidad: <b>{sensitivity}</b> (se cambia en Ajustes).", sensitivity=self.service.sensitivity_label))
        self.start_btn.setEnabled(True)

    def is_busy(self) -> bool:
        return self.stack.currentIndex() == 1

    def reset(self):
        self.panel.stop()
        self._live_timer.stop()
        self.stack.setCurrentIndex(0)
        self.refresh()

    def start(self):
        if not self.service.profiles():
            QMessageBox.information(self, _("Identificar"), _("No hay usuarios registrados todavía."))
            return
        if self.mode != "identify" and not self.claim_combo.currentData():
            QMessageBox.information(self, _("Verificar"), _("Elige qué usuario dices ser.") if self.mode == "verify"
                                    else _("Elige a quién quieres imitar."))
            return
        if self.mode == "challenge" and self.challenger_combo.currentData() == self.claim_combo.currentData():
            QMessageBox.information(self, _("Desafío"), _("Para el desafío tienes que imitar a otra persona, no a ti."))
            return
        free = self.free_check.isChecked()
        lang = self.service.text_language
        if free:
            tid, text = "libre", ""
        else:
            tid, text = pick_verify_text(self.last_text, lang)
            self.last_text = tid
        header = {"identify": _("Texto de comprobación"),
                  "verify": _("Verificación: ¿eres {name}?", name=self.claim_combo.currentText()),
                  "challenge": _("Desafío: escribe como {name}", name=self.claim_combo.currentText())}[self.mode]
        self.panel.start(text, tid, "verify", header, free=free)
        self._start_live()
        self.stack.setCurrentIndex(1)
        self.panel.input.setFocus()

    def _restart_typing(self):
        self.panel.restart()
        self._start_live()

    # -- identificación en directo -----------------------------------------------
    def _start_live(self):
        on = bool(self.service.settings.get("live_identify", True))
        self.live.setVisible(on)
        self._live_seq += 1
        self._live_keys = 0
        self._live_busy = False
        self._early = False
        self.live_bar.setValue(0)
        self.live_text.setText(_("Identificación en directo: escribe unas cuantas palabras…"))
        if on:
            self._live_profiles = self.service.profiles()     # se leen aquí, no en el hilo
            self._live_timer.start()
        else:
            self._live_timer.stop()

    def _live_tick(self):
        rec = self.panel.recorder
        if self._live_busy or rec is None or not rec.started or self.panel.input.locked:
            return
        keys = sum(k.kind in TYPING_KINDS for k in rec.keystrokes)
        if keys < LIVE_MIN_KEYS:
            self.live_text.setText(_n("Identificación en directo: falta {n} pulsación para la primera estimación…",
                                      "Identificación en directo: faltan {n} pulsaciones para la primera estimación…",
                                      LIVE_MIN_KEYS - keys))
            return
        if keys - self._live_keys < LIVE_STEP_KEYS:
            return
        sample = self.panel.snapshot()
        if sample is None:
            return
        self._live_keys = keys
        self._live_busy = True
        task = _LiveTask(self._live_seq, self.service, sample, self._live_profiles)
        task.signals.done.connect(self._live_done)
        self._live_task = task
        QThreadPool.globalInstance().start(task)

    def _live_done(self, seq: int, res):
        self._live_busy = False
        if seq != self._live_seq or self.stack.currentIndex() != 1 or isinstance(res, Exception):
            return
        n = self._live_keys
        if self.mode != "identify":
            c = next((c for c in res.candidates if c.user_id == self.claim_combo.currentData()), None)
            if c:
                self.live_text.setText(_("En directo ({n} pulsaciones): coincidencia con <b>{name}</b> {conf} %",
                                         n=n, name=c.name, conf=f"{c.confidence:.0f}"))
                self.live_bar.setValue(int(c.confidence))
        elif res.best:
            self.live_text.setText(_("En directo ({n} pulsaciones): te pareces a <b>{name}</b> · {conf} %",
                                     n=n, name=res.best.name, conf=f"{res.best.confidence:.0f}"))
            self.live_bar.setValue(int(res.best.confidence))
        elif res.candidates:
            c = res.candidates[0]
            self.live_text.setText(_("En directo ({n} pulsaciones): todavía no coincides con nadie "
                                     "(el más parecido es {name})", n=n, name=c.name))
            self.live_bar.setValue(int(c.confidence))
        # Decisión progresiva: si el resultado ya está claro no hace falta terminar el texto
        claimed = self.claim_combo.currentData() if self.mode == "verify" else None
        # en el desafío se escribe el texto entero: se quiere el intento completo
        if self.mode != "challenge" and self.service.settings.get("early_stop", True) \
                and early_decision(res, n, claimed):
            self._early = True
            self.live_text.setText(self.live_text.text() + " · " + _("resultado claro: no hace falta terminar el texto"))
            self.panel.finish_now()

    # -- resultado -----------------------------------------------------------
    def _on_sample(self, sample: Sample):
        self._live_timer.stop()
        self._live_seq += 1
        reason = self.service.check_quality(sample)
        too_short = sum(k.kind in TYPING_KINDS for k in sample.keystrokes) < MIN_TYPING_KEYS
        if reason and (sample.accuracy < 0.5 or too_short):
            QMessageBox.warning(self, _("Muestra no válida"), reason + "\n\n" + _("Vuelve a intentarlo."))
            self._restart_typing()
            return
        self.sample = sample
        if self.mode != "identify":
            self.result, self.claimed, f = self.service.verify(sample, self.claim_combo.currentData())
        else:
            self.result, f = self.service.identify(sample)
            self.claimed = None
        self.features = f
        self.findings = self.service.liveness(sample)
        accepted = self.claimed if self.mode == "verify" else self.result.best
        self.adapted = None
        if self.mode == "challenge":   # una imitación nunca se añade a un perfil
            self.entry = self.service.log_challenge(sample, self.result, self.claimed,
                                                    self.challenger_combo.currentData(), self.findings)
            self._show_result(f, reason)
            return
        if not reason:
            self.adapted = self.service.maybe_adapt(sample, accepted, self.result, self.findings)
        self.entry = self.service.log_identification(sample, self.result, self.mode, self.claimed,
                                                     self.findings, self.adapted, self._early)
        if self.adapted:
            self.users_changed.emit()
        self._show_result(f, reason)

    def _show_result(self, f: SampleFeatures, warning: str | None):
        res = self.result
        best = res.best
        verify = self.mode != "identify"   # verificación o desafío: se compara con un perfil concreto
        blocked = is_blocking(self.findings)
        if verify:
            shown = self.claimed
            accepted = bool(shown and shown.accepted) and not blocked
        else:
            shown = best or (res.candidates[0] if res.candidates else None)
            accepted = best is not None and not blocked
        self.shown = shown

        if blocked:
            status, icon, title = "bad", "alert", _("Muestra sospechosa")
            sub = _("No se acepta la identificación: la forma de teclear no parece humana o es una copia.")
        elif self.mode == "challenge":
            target = self.claim_combo.currentText()
            if accepted:
                status, icon, title = "warn", "alert", _("¡Has engañado a KeyBio!")
                sub = _("Tu forma de escribir ha pasado por la de <b>{name}</b>. El intento queda guardado para "
                        "que la calibración aprenda a rechazar imitaciones como la tuya.", name=target)
            else:
                status, icon, title = "good", "shield", _("KeyBio no se ha dejado engañar")
                sub = _("No escribes como <b>{name}</b>.", name=target)
            if shown:
                sub += " " + _("Te has quedado al <b>{ratio} %</b> de su umbral (se acepta por debajo del 100 %).",
                               ratio=f"{shown.ratio * 100:.0f}")
        elif verify and accepted:
            status, icon, title = "good", "shield", _("Identidad verificada: {name}", name=shown.name)
            sub = _("Tu forma de escribir coincide con el perfil indicado.")
            if best and best.user_id != shown.user_id:
                sub += (f'<br><span style="color:{theme.WARN}">'
                        + _("Atención: se parece todavía más al perfil de <b>{name}</b>.", name=best.name) + "</span>")
        elif verify:
            status, icon, title = "bad", "x_circle", _("Identidad rechazada")
            sub = _("La forma de escribir no coincide con el perfil de <b>{name}</b>.",
                    name=self.claim_combo.currentText())
            if best:
                sub += " " + _("Se parece más a <b>{name}</b>.", name=best.name)
        elif accepted:
            status, icon, title = "good", "check_circle", _("Hola, {name}", name=best.name)
            sub = _("Te hemos reconocido por tu forma de escribir.")
            if res.ambiguous:
                other = next(c for c in res.candidates if c.accepted and c is not best)
                sub += (f'<br><span style="color:{theme.WARN}">'
                        + _("El patrón también se parece al de <b>{name}</b>: el resultado es poco concluyente.",
                            name=other.name) + "</span>")
        else:
            status, icon, title = "warn", "help", _("Usuario no registrado")
            sub = _("Tu forma de escribir no coincide con ningún perfil registrado.")
            if shown:
                sub += " " + _("El más parecido es <b>{name}</b>, pero queda fuera de su umbral.", name=shown.name)
        for finding in self.findings:
            col = theme.BAD if finding.level == "bad" else theme.WARN
            sub += f'<br><span style="color:{col}">⚠ {finding.message}</span>'
        if shown:
            details = _("{wpm} ppm", wpm=f"{f.metrics['wpm']:.0f}")
            details += (" · " + _("texto libre") if self.sample.free
                        else ", " + _("precisión {accuracy} %", accuracy=f"{f.metrics['accuracy']:.0f}"))
            sub += "<br>" + _("Distancia <b>{distance}</b> · umbral {threshold}", distance=f"{shown.distance:.3f}",
                              threshold=f"{shown.threshold:.3f}") + f" · {details}"
        if warning:
            sub += f'<br><span style="color:{theme.BAD}">{warning} ' + _("El resultado puede no ser fiable.") + "</span>"
        if self._early:
            keys = sum(k.kind in TYPING_KINDS for k in self.sample.keystrokes)
            sub += "<br>" + _("Decidido con {n} pulsaciones: el resultado estaba claro y no ha hecho falta "
                              "terminar el texto.", n=keys)

        set_status(self.verdict, status)
        self.verdict_icon.set_icon(icon, {"good": "GOOD", "warn": "WARN", "bad": "BAD"}[status])
        self.verdict_title.setText(title)
        self.verdict_sub.setText(sub)
        conf = 0.0 if blocked else (shown.confidence if shown else 0.0)
        self.gauge.set_value(conf, "good" if conf >= 50 else "warn" if conf >= 25 else "bad", _("confianza"))

        self.feedback_row.setVisible(self.mode != "challenge")   # en el desafío ya se sabe la verdad
        self.adapt_btn.setVisible(False)
        self.enroll_btn.setVisible(False)
        if self.mode == "challenge":
            tries, fooled = self.service.challenge_stats()
            self.feedback_done.setText(_n("Marcador de desafíos: {n} intento", "Marcador de desafíos: {n} intentos", tries)
                                       + ", " + _n("KeyBio engañado {n} vez.", "KeyBio engañado {n} veces.", fooled))
        elif self.adapted:
            self.feedback_done.setText(_("La muestra se ha añadido automáticamente al perfil de {name} para que se "
                                         "adapte a cómo escribes. Si el resultado no es correcto, pulsa «No, es "
                                         "incorrecto» y se retirará.", name=self.adapted.name))
        else:
            self.feedback_done.setText("")

        self.ranking.setRowCount(0)
        for c in res.candidates:
            r = self.ranking.rowCount()
            self.ranking.insertRow(r)
            mine = shown is not None and c.user_id == shown.user_id and (accepted or verify)
            if mine and accepted:
                verdict, col = ("✔ " + (_("engañado") if self.mode == "challenge" else _("verificado") if verify
                                        else _("identificado"))), theme.GOOD
            elif c.accepted:
                verdict, col = _("dentro del umbral"), theme.WARN
            else:
                verdict, col = _("fuera del umbral"), theme.TEXT_2
            vals = [c.name, f"{c.distance:.3f}", f"{c.threshold:.3f}", "—" if c.ra is None else f"{c.ra:.3f}",
                    "—" if c.z is None else f"{c.z:.3f}", f"{c.confidence:.0f} %", verdict]
            for col_i, v in enumerate(vals):
                self.ranking.setItem(r, col_i, cell(v, col if col_i == len(vals) - 1 else None,
                                                    bold=mine and col_i == 0))
        fit_height(self.ranking, 12)

        prof = None
        if shown:
            user = self.service.storage.get_user(shown.user_id)
            prof = self.service.profile(user) if user else None
        layout = self.service.keyboard_layout
        if prof:
            self.similarity.set_data(f, prof, shown.name)
            self.why_sub.setText(_("Cada rasgo de esta muestra comparado con el perfil de {name} (valor de la "
                                   "muestra · valor del perfil), de más distinto a más parecido.", name=shown.name))
            axes, series = radar_series([f.metrics], _("Esta muestra"), [x.metrics for x in prof.features],
                                        _("Perfil de {name}", name=shown.name))
            self.radar.set_data(axes, series)
            self.t_ra.set("—" if shown.ra is None else f"{shown.ra:.3f}", _("combinaciones de 2 y 3 teclas (R/A)"))
            self.t_z.set("—" if shown.z is None else f"{shown.z:.3f}", _("velocidad, pulsación, shift…"))
            self.analysis.show_features(f, prof, (_("Esta muestra"), _("Perfil de {name}", name=shown.name)), layout)
        else:
            self.analysis.show_features(f, layout=layout)
        self._verdict_text = (title, f"{title}. {sub}")
        self.stack.setCurrentIndex(2)

    def _save_pdf(self):
        if self.features is None:
            return
        from ..report import result_report
        path = QFileDialog.getSaveFileName(self, _("Guardar informe"),
                                           str(Path.home() / f"{_('comprobacion')}_keybio.pdf"), "PDF (*.pdf)")[0]
        if not path:
            return
        title, text = self._verdict_text
        plain = re.sub(r"<[^>]+>", "", text.replace("<br>", " · "))
        result_report(self.service, self.features, self.result, self.shown, title, plain, Path(path),
                      self.service.keyboard_layout)
        notify(self, _("Informe guardado"))

    # -- realimentación ------------------------------------------------------
    def _feedback_yes(self):
        verify = self.mode == "verify"
        blocked = is_blocking(self.findings)
        accepted_user = None
        if not blocked:
            accepted_user = (self.claimed if verify and self.claimed and self.claimed.accepted
                             else None if verify else self.result.best)
        self.service.set_feedback(self.entry["id"], "correct", accepted_user.user_id if accepted_user else None)
        self.feedback_row.setVisible(False)
        if accepted_user and not self.adapted:
            self._offer_adapt(accepted_user.user_id, accepted_user.name,
                              _("Gracias. Añadir la muestra ayuda a que el perfil se adapte a cómo escribes en "
                                "distintos días."))
        elif accepted_user:
            self.feedback_done.setText(_("Gracias. La muestra ya forma parte de tu perfil."))
        elif not verify and not blocked:
            self.enroll_btn.setVisible(True)
            self.feedback_done.setText(_("Gracias. Puedes registrarte para que el sistema te reconozca."))
        else:
            self.feedback_done.setText(_("Gracias, queda anotado en el historial."))

    def _feedback_no(self):
        users = self.service.users()
        options = [u.name for u in users] + [_("Nadie: no estoy registrado")]
        choice, ok = QInputDialog.getItem(self, _("Resultado incorrecto"), _("¿Quién ha escrito el texto?"), options, 0,
                                          False)
        if not ok:
            return
        true_user = next((u for u in users if u.name == choice), None)
        was_adapted = self.adapted
        undone = self.service.set_feedback(self.entry["id"], "incorrect", true_user.id if true_user else None)
        self.feedback_row.setVisible(False)
        note = " " + _("Se ha retirado la muestra del perfil de {name}.", name=undone) if undone else ""
        if undone:
            self.adapted = None
            self.users_changed.emit()
        if true_user and not is_blocking(self.findings):
            if was_adapted is not None and was_adapted.id == true_user.id and not undone:
                self.feedback_done.setText(_("Gracias, queda anotado.") + note)
            else:
                self._offer_adapt(true_user.id, true_user.name,
                                  _("Gracias. Añadir la muestra al perfil correcto mejorará la identificación."), note)
        else:
            self.enroll_btn.setVisible(not is_blocking(self.findings))
            self.feedback_done.setText(_("Gracias, queda anotado en el historial.") + note)

    def _offer_adapt(self, user_id: str, name: str, text: str, note: str = ""):
        if self.sample is not None and self.service.adapt_problem(self.sample):
            # una muestra corta (decisión rápida) no sirve para el perfil: no se ofrece añadirla
            self.feedback_done.setText(_("Gracias, queda anotado.") + note)
            return
        self.adapt_btn.setText(_("Añadir esta muestra al perfil de {name}", name=name))
        self.adapt_btn.setProperty("target_user", user_id)
        self.adapt_btn.setVisible(True)
        self.feedback_done.setText(text + note)

    def _adapt(self):
        uid = self.adapt_btn.property("target_user")
        if not uid or self.sample is None:
            return
        reason = self.service.adapt_problem(self.sample)
        if reason:
            QMessageBox.warning(self, _("Muestra no válida"), _("No se puede añadir: {reason}", reason=reason))
            return
        user = self.service.storage.get_user(uid)
        if user and any(s.id == self.sample.id for s in user.samples):
            self.adapt_btn.setVisible(False)
            return
        user = self.service.add_samples(uid, [self.sample])
        self.adapt_btn.setVisible(False)
        self.feedback_done.setText(_n("Muestra añadida. {name} tiene ahora {n} muestra.",
                                      "Muestra añadida. {name} tiene ahora {n} muestras.", len(user.samples),
                                      name=user.name))
        notify(self, _("Perfil de {name} actualizado", name=user.name))
        self.users_changed.emit()
