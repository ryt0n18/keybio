"""Verificación de acceso: la ventana que se abre al iniciar sesión en un sistema sensible.

Se lanza con ``keybio --acceso NOMBRE [--sistema SISTEMA]`` y termina con un código de salida
para el sistema que la llama:

    0  identidad confirmada (con la frase corta o con la verificación adicional)
    1  no confirmada: no coincide y la verificación adicional no se superó o se abandonó
    2  no se pudo comprobar (sin perfil, datos bloqueados o cancelada antes de terminar la frase)

La muestra se analiza en el equipo y se descarta; solo se guarda la puntuación de coincidencia
(``BiometricService.log_access``).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QHBoxLayout, QMessageBox, QStackedWidget, QVBoxLayout, QWidget

from .. import APP_NAME
from ..capture import Sample
from ..i18n import _
from ..service import BiometricService
from ..storage import User, clean_name
from ..texts import pick_access_phrase, pick_verify_text
from . import icons
from .icons import IconLabel
from .typing_widget import TypingPanel
from .widgets import HBox, button, card, label, page_title, primary, set_status

EXIT_OK, EXIT_DENIED, EXIT_UNCHECKED = 0, 1, 2
AUTO_CLOSE_MS = 1500     # la ventana se cierra sola tras confirmar la identidad


class AccessDialog(QDialog):
    def __init__(self, service: BiometricService, user: User, system: str = "", parent=None):
        super().__init__(parent)
        self.service, self.user, self.system = service, user, clean_name(system)
        self.code = EXIT_UNCHECKED
        self.notice: dict | None = None   # aviso abierto mientras se hace la verificación adicional
        self.step = "phrase"              # phrase | extra
        self.setWindowTitle(f"{APP_NAME} · {_('Verificación de acceso')}")
        self.setWindowIcon(icons.app_icon())
        self.resize(860, 640)

        where = _("Para entrar en <b>{system}</b>", system=self.system) if self.system else _("Para entrar en el sistema")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)
        lay.addWidget(page_title(_("Verificación de acceso"), "", "lock"))
        self.intro = label("", "subtitle", wrap=True, rich=True)
        lay.addWidget(self.intro)

        self.stack = QStackedWidget()
        w = QWidget()
        wl = QVBoxLayout(w)
        wl.setContentsMargins(0, 0, 0, 0)
        self.panel = TypingPanel()
        self.panel.configure(bool(service.settings.get("show_keyboard", True)),
                             service.keyboard_layout)
        self.panel.finished.connect(self._on_sample)
        wl.addWidget(self.panel, 1)
        self.stack.addWidget(w)

        self.result, rl = card(margins=22)
        top = QHBoxLayout()
        self.result_icon = IconLabel("shield", "GOOD", 30)
        self.result_title = label("", "hero")
        self.result_title.setWordWrap(True)
        top.addWidget(self.result_icon, alignment=Qt.AlignmentFlag.AlignTop)
        top.addWidget(self.result_title, 1)
        rl.addLayout(top)
        self.result_sub = label("", "subtitle", wrap=True, rich=True)
        rl.addWidget(self.result_sub)
        self.next_btn = primary(_("Continuar"), "arrow_right")
        self.next_btn.clicked.connect(self._next)
        rl.addWidget(HBox(self.next_btn))
        rw = QWidget()
        rwl = QVBoxLayout(rw)
        rwl.setContentsMargins(0, 0, 0, 0)
        rwl.addWidget(self.result)
        rwl.addStretch(1)
        self.stack.addWidget(rw)
        lay.addWidget(self.stack, 1)

        lay.addWidget(label(_("Tu forma de escribir se analiza en este equipo y se descarta al terminar: no se guardan "
                              "las pulsaciones ni lo que escribes, solo la puntuación de coincidencia."), "small",
                            wrap=True))
        self.cancel_btn = button(_("Cancelar"), "x_circle")
        self.cancel_btn.clicked.connect(self.reject)
        lay.addWidget(HBox(self.cancel_btn))
        self._start(pick_access_phrase(language=self._language()), _("Frase de acceso"),
                    _("{where}, escribe esta frase con naturalidad para confirmar que eres <b>{name}</b>.",
                      where=where, name=self.user.name))

    def _language(self) -> str:
        return self.service.text_language

    def _start(self, text: tuple[str, str], header: str, intro: str) -> None:
        tid, target = text
        self.intro.setText(intro)
        self.intro.setVisible(True)
        self.panel.start(target, tid, "verify", header)
        self.stack.setCurrentIndex(0)
        self.panel.input.setFocus()

    def _show(self, status: str, icon: str, title: str, sub: str, next_text: str | None) -> None:
        set_status(self.result, status)
        self.result_icon.set_icon(icon, {"good": "GOOD", "warn": "WARN", "bad": "BAD"}[status])
        self.result_title.setText(title)
        self.result_sub.setText(sub)
        self.next_btn.setText(next_text or "")
        self.next_btn.setVisible(next_text is not None)
        self.intro.setVisible(False)
        self.stack.setCurrentIndex(1)
        self.next_btn.setFocus()

    # -- flujo ----------------------------------------------------------------
    def _on_sample(self, sample: Sample) -> None:
        reason = self.service.check_quality(sample)
        if reason:   # no cuenta como intento: no se compara ni se guarda nada
            QMessageBox.warning(self, _("Vuelve a escribirlo"), reason + "\n\n" + _("Vuelve a escribir el texto."))
            self.panel.restart()
            return
        score, match = self.service.access_check(sample, self.user.id)
        if self.step == "phrase":
            entry = self.service.log_access(self.user.id, score, match, self.system)
            if match:
                self._confirmed(_("Tu forma de escribir coincide con tu perfil (puntuación <b>{score}</b> de 100).",
                                  score=score))
                return
            self.notice = entry
            self.code = EXIT_DENIED
            self._show("warn", "alert", _("Hace falta una verificación adicional"),
                       _("Tu forma de escribir no ha coincidido con tu perfil (puntuación <b>{score}</b> de 100). "
                         "Puede pasar por cansancio, con otro teclado o con una lesión.", score=score) + "<br>"
                       + _("Se ha avisado al administrador solo con la fecha, el sistema y la puntuación."),
                       _("Hacer la verificación adicional"))
            return
        self.service.finish_access(self.notice["id"], "passed" if match else "failed")
        self.notice = None
        if match:
            self._confirmed(_("La verificación adicional coincide con tu perfil."))
            return
        self.cancel_btn.setVisible(False)
        self._show("bad", "x_circle", _("No se ha podido confirmar tu identidad"),
                   _("El administrador ya tiene el aviso. Si eres tú, pídele que lo revise o usa el procedimiento "
                     "alternativo de tu organización."), _("Cerrar"))

    def _confirmed(self, sub: str) -> None:
        self.code = EXIT_OK
        self.cancel_btn.setVisible(False)
        self._show("good", "shield", _("Identidad confirmada"), sub, _("Continuar"))
        QTimer.singleShot(AUTO_CLOSE_MS, self.accept)

    def _next(self) -> None:
        if self.notice is not None and self.step == "phrase":
            self.step = "extra"
            self._start(pick_verify_text(language=self._language()), _("Verificación adicional"),
                        _("Verificación adicional: escribe este texto, algo más largo. Con más texto la comprobación "
                          "es más fiable."))
        else:
            self.accept()

    def reject(self) -> None:
        """Cancelar o cerrar la ventana. Si había un aviso abierto, queda como abandonado."""
        self.panel.stop()
        if self.notice is not None:
            self.service.finish_access(self.notice["id"], "abandoned")
            self.notice = None
        super().reject()

    def accept(self) -> None:
        self.panel.stop()
        super().accept()


def run_access(service: BiometricService, name: str, system: str = "") -> int:
    """Abre la verificación de acceso de ``name`` y devuelve el código de salida."""
    user = service.storage.find_by_name(clean_name(name))
    if user is None or not service.has_profile(user.id):
        QMessageBox.critical(None, APP_NAME, _("No hay ningún perfil de «{name}» con muestras suficientes en este "
                                               "equipo.\nRegístralo primero en KeyBio.", name=clean_name(name)))
        return EXIT_UNCHECKED
    dlg = AccessDialog(service, user, system)
    dlg.exec()
    return dlg.code
