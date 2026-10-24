"""Diálogos: contraseña de los datos cifrados."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout

from . import theme
from ..i18n import _
from .icons import IconLabel

MIN_PASSWORD = 8


class PasswordDialog(QDialog):
    """``mode="unlock"`` pide la contraseña; ``mode="new"`` pide una nueva dos veces."""

    def __init__(self, mode: str = "unlock", parent=None, message: str = ""):
        super().__init__(parent)
        self.mode = mode
        self.setWindowTitle("KeyBio · " + (_("Contraseña") if mode == "unlock" else _("Nueva contraseña")))
        self.setMinimumWidth(420)
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        head = QLabel()
        head.setWordWrap(True)
        head.setTextFormat(Qt.TextFormat.RichText)
        if mode == "unlock":
            head.setText(_("<b>Tus perfiles están protegidos.</b><br>Introduce la contraseña para abrirlos."))
        else:
            head.setText(_("<b>Elige una contraseña</b> (mínimo {n} caracteres).", n=MIN_PASSWORD) + "<br>"
                         f"<span style='color:{theme.BAD}'>"
                         + _("Si la olvidas, los perfiles cifrados no se podrán recuperar.") + "</span>")
        row = QVBoxLayout()
        row.addWidget(IconLabel("shield", "ACCENT", 32), alignment=Qt.AlignmentFlag.AlignLeft)
        lay.addLayout(row)
        lay.addWidget(head)
        form = QFormLayout()
        self.pw1 = QLineEdit()
        self.pw1.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow(_("Contraseña:"), self.pw1)
        self.pw2 = QLineEdit()
        self.pw2.setEchoMode(QLineEdit.EchoMode.Password)
        if mode != "unlock":
            form.addRow(_("Repítela:"), self.pw2)
        lay.addLayout(form)
        self.error = QLabel(message)
        self.error.setStyleSheet(f"color: {theme.BAD};")
        self.error.setWordWrap(True)
        self.error.setVisible(bool(message))
        lay.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(_("Abrir") if mode == "unlock" else _("Guardar"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(_("Cancelar"))
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self.pw1.setFocus()

    def _ok(self):
        p1 = self.pw1.text()
        if self.mode != "unlock":
            if len(p1) < MIN_PASSWORD:
                return self._fail(_("La contraseña debe tener al menos {n} caracteres.", n=MIN_PASSWORD))
            if p1 != self.pw2.text():
                return self._fail(_("Las contraseñas no coinciden."))
        elif not p1:
            return self._fail(_("Escribe la contraseña."))
        self.accept()

    def _fail(self, text: str):
        self.error.setText(text)
        self.error.setVisible(True)

    @property
    def password(self) -> str:
        return self.pw1.text()
