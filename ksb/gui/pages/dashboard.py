"""Panel de control: resumen con widgets."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QLocale, QThreadPool, Qt, Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from ...evaluation import EvalResult
from ...service import BiometricService
from .. import theme
from ..charts import HBarChart, RatioHistogram, StackedBars
from ..icons import IconLabel
from ..widgets import (Avatar, Badge, HBox, Tile, button, card, card_header, label, page_widget, primary,
                       scroll, separator)
from ...i18n import _, _n
from .common import EvalTask, long_date, time_ago, weekday_short


def _clear(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.hide()            # desaparece ya, sin esperar a que se procese deleteLater
            w.deleteLater()
        elif item.layout():
            _clear(item.layout())


class DashboardPage(QWidget):
    go_identify = Signal()
    go_enroll = Signal()
    go_users = Signal()
    go_history = Signal()
    go_access = Signal()
    go_settings = Signal()
    add_samples_for = Signal(str)   # id de usuario

    def __init__(self, service: BiometricService, parent=None):
        super().__init__(parent)
        self.service = service
        self._eval_key = None
        self._task: EvalTask | None = None
        inner, lay = page_widget()

        # cabecera
        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.greeting = label("", "title")
        self.today = label("", "subtitle")
        titles.addWidget(self.greeting)
        titles.addWidget(self.today)
        head.addLayout(titles, 1)
        b_id = primary(_("Identificar"), "scan")
        b_id.clicked.connect(self.go_identify)
        b_en = button(_("Registrar usuario"), "user_plus")
        b_en.clicked.connect(self.go_enroll)
        head.addWidget(b_en, alignment=Qt.AlignmentFlag.AlignBottom)
        head.addWidget(b_id, alignment=Qt.AlignmentFlag.AlignBottom)
        lay.addLayout(head)

        # indicadores
        kpis = QGridLayout()
        kpis.setSpacing(12)
        self.k_users = Tile("users", _("Usuarios registrados"))
        self.k_samples = Tile("keyboard", _("Muestras de escritura"))
        self.k_checks = Tile("scan", _("Comprobaciones"))
        self.k_acc = Tile("shield", _("Acierto verificado"))
        for i, t in enumerate((self.k_users, self.k_samples, self.k_checks, self.k_acc)):
            kpis.addWidget(t, 0, i)
        lay.addLayout(kpis)

        # estado vacío
        self.empty, el = card(margins=26)
        row = QHBoxLayout()
        row.setSpacing(18)
        row.addWidget(IconLabel("fingerprint", "ACCENT", 56), alignment=Qt.AlignmentFlag.AlignTop)
        texts = QVBoxLayout()
        texts.addWidget(label(_("Bienvenido a KeyBio"), "hero"))
        texts.addWidget(label(_(
            "KeyBio reconoce a las personas por su forma de escribir: el tiempo que mantienen pulsada cada "
            "tecla, el ritmo entre teclas, cómo usan las mayúsculas y cómo corrigen sus errores.<br><br>"
            "<b>1.</b> Registra a una persona escribiendo unos textos cortos.&nbsp;&nbsp;"
            "<b>2.</b> Haz una comprobación con un texto nuevo y el programa dirá quién es."),
            "subtitle", wrap=True, rich=True))
        start = primary(_("Registrar el primer usuario"), "user_plus")
        start.clicked.connect(self.go_enroll)
        texts.addWidget(HBox(start))
        row.addLayout(texts, 1)
        el.addLayout(row)
        lay.addWidget(self.empty)

        # widgets en dos columnas independientes (cada una con su altura natural)
        columns = QHBoxLayout()
        columns.setSpacing(14)
        left = QVBoxLayout()
        left.setSpacing(14)
        right = QVBoxLayout()
        right.setSpacing(14)
        columns.addLayout(left, 3)
        columns.addLayout(right, 2)

        c, cl = card()
        cl.addWidget(card_header(_("Actividad de los últimos 14 días"), "activity"))
        self.activity = StackedBars()
        cl.addWidget(self.activity)
        left.addWidget(c)

        c, cl = card()
        cl.addWidget(card_header(_("Velocidad media por usuario"), "gauge"))
        self.speed = HBarChart(unit=_("ppm"), label_fn=str)
        cl.addWidget(self.speed)
        left.addWidget(c)

        c, cl = card()
        top = QHBoxLayout()
        top.addWidget(card_header(_("Actividad reciente"), "history"), 1)
        all_btn = button(_("Ver historial"))
        all_btn.setObjectName("flat")
        all_btn.clicked.connect(self.go_history)
        top.addWidget(all_btn)
        cl.addLayout(top)
        self.recent_box = QVBoxLayout()
        self.recent_box.setSpacing(0)
        cl.addLayout(self.recent_box)
        left.addWidget(c)
        left.addStretch(1)

        c, cl = card()
        cl.addWidget(card_header(_("Sugerencias"), "bolt"))
        self.tips_box = QVBoxLayout()
        self.tips_box.setSpacing(8)
        cl.addLayout(self.tips_box)
        self.tips_card = c
        right.addWidget(c)

        c, cl = card()
        top = QHBoxLayout()
        top.addWidget(card_header(_("Perfiles"), "users"), 1)
        see = button(_("Ver todos"))
        see.setObjectName("flat")
        see.clicked.connect(self.go_users)
        top.addWidget(see)
        cl.addLayout(top)
        self.profiles_box = QVBoxLayout()
        self.profiles_box.setSpacing(6)
        cl.addLayout(self.profiles_box)
        right.addWidget(c)

        c, cl = card()
        top = QHBoxLayout()
        top.addWidget(card_header(_("Rendimiento del sistema"), "target"), 1)
        self.recalc = button("", "refresh")
        self.recalc.setToolTip(_("Volver a calcular"))
        self.recalc.clicked.connect(lambda: self._start_eval(force=True))
        top.addWidget(self.recalc)
        cl.addLayout(top)
        nums = QHBoxLayout()
        self.e_ident = Tile(None, _("Acierto al identificar"))
        self.e_far = Tile(None, _("Desconocidos aceptados"))
        nums.addWidget(self.e_ident)
        nums.addWidget(self.e_far)
        cl.addLayout(nums)
        self.e_note = label("", "small", wrap=True)
        cl.addWidget(self.e_note)
        self.hist = RatioHistogram()
        cl.addWidget(self.hist)
        right.addWidget(c)
        right.addStretch(1)

        self.columns = QWidget()
        self.columns.setLayout(columns)
        lay.addWidget(self.columns)
        lay.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll(inner))

    # ------------------------------------------------------------------------
    def refresh(self):
        now = datetime.now()
        h = now.hour
        hello = _("Buenos días") if 6 <= h < 13 else _("Buenas tardes") if 13 <= h < 21 else _("Buenas noches")
        self.greeting.setText(f"{hello} · {_('Panel de control')}")
        self.today.setText(f"{long_date(now)} · " + _("sensibilidad {name}", name=self.service.sensitivity_label))

        st = self.service.dashboard_stats()
        users = sorted(self.service.users(), key=lambda u: u.created)
        self.k_users.set(str(st["users"]), _("{n} con perfil sólido", n=st["solid"]) if st["users"]
                         else _("ninguno todavía"))
        self.k_samples.set(str(st["samples"]), _("{n} pulsaciones analizadas", n=QLocale().toString(st["keystrokes"])))
        self.k_checks.set(str(st["checks"]), _("{n} en los últimos 7 días", n=st["checks_week"]))
        if st["verified"]:
            self.k_acc.set(f"{100 * st['verified_ok'] / st['verified']:.0f} %",
                           _("{ok} de {n} verificadas por el usuario", ok=st["verified_ok"], n=st["verified"]))
        else:
            self.k_acc.set("—", _("marca los resultados como correctos o no"))

        has_users = bool(users)
        self.empty.setVisible(not has_users)
        self.columns.setVisible(has_users)
        if not has_users:
            return

        self.activity.set_data(
            [(f"{weekday_short(d)} {d.day}", a, b) for d, a, b in st["days"]],
            (_("Reconocidos"), _("No reconocidos")))

        # perfiles
        _clear(self.profiles_box)
        for idx, u in enumerate(users[:6]):
            prof = self.service.profile(u) if len(u.samples) >= 2 else None
            level, text = self.service.quality(u, prof)
            row = QHBoxLayout()
            row.setSpacing(10)
            av = Avatar(30)
            av.set_user(u.name, idx)
            row.addWidget(av)
            col = QVBoxLayout()
            col.setSpacing(0)
            col.addWidget(label(u.name, "section"))
            col.addWidget(label(_n("{n} muestra", "{n} muestras", len(u.samples)), "small"))
            row.addLayout(col, 1)
            row.addWidget(Badge(text, level))
            self.profiles_box.addLayout(row)
        if len(users) > 6:
            self.profiles_box.addWidget(label(_("y {n} más…", n=len(users) - 6), "small"))

        # velocidad por usuario (color = identidad de la persona)
        rows, colors = [], []
        for idx, u in enumerate(users):
            ms = [self.service.features(s).metrics["wpm"] for s in u.samples]
            if ms:
                rows.append((u.name, sum(ms) / len(ms), None))
                colors.append(theme.category(idx))
        self.speed.set_data(rows, ("", ""), colors)

        # sugerencias
        _clear(self.tips_box)
        tips = self.service.tips()
        self.tips_card.setVisible(bool(tips))
        for level, text, action, uid in tips[:5]:
            self.tips_box.addWidget(self._tip_row(level, text, action, uid))

        # actividad reciente
        _clear(self.recent_box)
        if not st["recent"]:
            self.recent_box.addWidget(label(_("Aún no hay comprobaciones. Pulsa «Identificar» para hacer la "
                                              "primera."), "subtitle", wrap=True))
        for i, e in enumerate(st["recent"]):
            if i:
                self.recent_box.addWidget(separator())
            self.recent_box.addWidget(self._recent_row(e))

        self._start_eval()

    def _tip_row(self, level: str, text: str, action: str, uid: str | None) -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        row.addWidget(IconLabel("alert" if level == "warn" else "bolt", "WARN" if level == "warn" else "GOOD", 18),
                      alignment=Qt.AlignmentFlag.AlignTop)
        row.addWidget(label(text, "small", wrap=True), 1)
        names = {"add_samples": _("Añadir muestras"), "calibrate": _("Calibrar"), "enroll": _("Registrar"),
                 "protect": _("Proteger"), "access": _("Ver avisos")}
        b = button(names.get(action, _("Ver")))
        b.setObjectName("flat")
        if action == "add_samples" and uid:
            b.clicked.connect(lambda _=False, u=uid: self.add_samples_for.emit(u))
        elif action == "enroll":
            b.clicked.connect(self.go_enroll)
        elif action == "access":
            b.clicked.connect(self.go_access)
        else:
            b.clicked.connect(self.go_settings)
        row.addWidget(b, alignment=Qt.AlignmentFlag.AlignTop)
        return w

    def _recent_row(self, e: dict) -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 8, 0, 8)
        row.setSpacing(12)
        accepted = e.get("accepted", e.get("user_id") is not None)
        verify = e.get("mode") == "verify"
        challenge = e.get("mode") == "challenge"
        if e.get("suspicious") and not accepted and any(c in ("robotic", "repeated", "instant", "replay")
                                                         for c in e["suspicious"]):
            icon, role, title = "alert", "BAD", _("Muestra sospechosa rechazada")
        elif challenge:
            icon, role = ("alert", "WARN") if accepted else ("shield", "GOOD")
            title = (_("Desafío: alguien pasó por {name}", name=e.get("claimed")) if accepted
                     else _("Desafío: imitación de {name} rechazada", name=e.get("claimed")))
        elif accepted:
            icon, role = "check_circle", "GOOD"
            title = (_("Identidad verificada: {name}", name=e.get("user_name")) if verify
                     else _("Identificado: {name}", name=e.get("user_name")))
        else:
            icon, role = ("x_circle", "BAD") if verify else ("help", "WARN")
            title = (_("Verificación rechazada: {name}", name=e.get("claimed")) if verify
                     else _("Usuario no registrado"))
        row.addWidget(IconLabel(icon, role, 22))
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(label(title))
        details = [(_("Desafío") if challenge else _("Verificación 1:1") if verify else _("Identificación")),
                   _("texto {id}", id=e.get("text_id", ""))]
        if e.get("wpm"):
            details.append(_("{wpm} ppm", wpm=f"{e['wpm']:.0f}"))
        if e.get("free"):
            details.append(_("texto libre"))
        if e.get("adapted_user"):
            details.append(_("perfil adaptado"))
        col.addWidget(label(" · ".join(details), "small"))
        row.addLayout(col, 1)
        fb = e.get("feedback")
        if fb == "correct":
            row.addWidget(Badge(_("correcto"), "good"))
        elif fb == "incorrect":
            row.addWidget(Badge(_("incorrecto"), "bad"))
        if e.get("confidence") is not None and accepted:
            row.addWidget(label(f"{e['confidence']:.0f} %", "section"))
        row.addWidget(label(time_ago(e.get("date", "")), "small"))
        return w

    # -- evaluación en segundo plano -----------------------------------------
    def _start_eval(self, force: bool = False):
        users = self.service.users()
        key = (tuple((u.id, len(u.samples), u.samples[-1].id if u.samples else "") for u in users),
               self.service.sensitivity_label)
        if key == self._eval_key and not force:
            return
        self._eval_key = key
        self.e_ident.set("…")
        self.e_far.set("…")
        self.e_note.setText(_("Calculando con validación cruzada…"))
        self.recalc.setEnabled(False)
        task = EvalTask(key, self.service.evaluation_input(), self.service.sensitivity)
        task.signals.done.connect(self._eval_done)
        self._task = task
        QThreadPool.globalInstance().start(task)

    def _eval_done(self, key, res):
        if key != self._eval_key:
            return
        self.recalc.setEnabled(True)
        if isinstance(res, Exception):
            self.e_note.setText(_("No se pudo calcular: {error}", error=res))
            return
        r: EvalResult = res
        ir, far = r.identification_rate, r.false_accept_rate
        self.e_ident.set(f"{100 * ir:.0f} %" if ir is not None else "—",
                         _("{ok} de {n} muestras", ok=r.genuine_correct, n=r.genuine_total) if r.genuine_total else
                         _("necesita 3+ muestras por usuario"))
        self.e_far.set(f"{100 * far:.0f} %" if far is not None else "—",
                       _("{ok} de {n} intentos", ok=r.impostor_accepted, n=r.impostor_total) if r.impostor_total else
                       _("necesita 2+ usuarios"))
        notes = []
        if r.genuine_rejected:
            notes.append(_n("{n} muestra legítima rechazada", "{n} muestras legítimas rechazadas", r.genuine_rejected))
        if r.genuine_confused:
            notes.append(_n("{n} confundida con otro usuario", "{n} confundidas con otro usuario", r.genuine_confused))
        self.e_note.setText(
            _("Cada muestra guardada se prueba contra los perfiles: con el suyo apartado (¿la reconoce?) y "
              "sin el suyo (¿la rechaza como desconocida?). En la gráfica, lo que queda a la izquierda de la línea "
              "del umbral se acepta.") + (" " + "; ".join(notes) + "." if notes else ""))
        self.hist.set_data(r.genuine_ratios, r.impostor_ratios)
