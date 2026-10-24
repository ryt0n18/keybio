"""Ventana principal."""

from __future__ import annotations

import argparse
import os
import sys
import traceback

from PySide6.QtCore import QEasingCurve, QLibraryInfo, QLocale, QPropertyAnimation, QSize, Qt, QTimer, QTranslator
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QStackedWidget, QVBoxLayout,
                               QWidget)

from .. import APP_NAME, APP_VERSION, crypto, i18n, logutil
from ..i18n import N_, _
from ..service import BiometricService
from .access import EXIT_UNCHECKED, run_access
from .dialogs import PasswordDialog
from . import icons, theme
from .pages import AccessPage, DashboardPage, EnrollPage, HistoryPage, IdentifyPage, SettingsPage, UsersPage
from .typing_widget import TypingPanel
from .widgets import Badge, label, refresh_button_icon

NAV = [(N_("Panel de control"), "dashboard"), (N_("Registrar"), "user_plus"), (N_("Identificar"), "scan"),
       (N_("Usuarios"), "users"), (N_("Historial"), "history"), (N_("Accesos"), "lock"), (N_("Ajustes"), "settings")]
# traducciones de Qt para sus propios diálogos (Sí/No, Abrir...); sin gallego ni euskera, se usa el español
QT_LANGUAGES = {"es": "es", "en": "en", "ca": "ca", "gl": "es", "eu": "es", "fr": "fr", "pt": "pt_BR", "de": "de",
                "it": "it"}
# formato de fechas y números de cada idioma (el mismo que en la web)
QT_LOCALES = {"en": "en_GB", "pt": "pt_PT"}
# nombre de la entrada del menú de aplicaciones en Linux (tools/linux.py)
DESKTOP_ID = "io.github.ryt0n18.keybio"


class MainWindow(QMainWindow):
    def __init__(self, service: BiometricService):
        super().__init__()
        self.service = service
        self.setWindowTitle(f"{APP_NAME} · {_('Biometría de tecleo')}")
        self.setWindowIcon(icons.app_icon())
        self.resize(1240, 860)
        self.setMinimumSize(QSize(960, 660))

        root = QWidget()
        root.setObjectName("root")
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        side = QWidget()
        side.setObjectName("sidebar")
        side.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        side.setFixedWidth(232)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 18, 0, 12)
        sl.setSpacing(4)
        brand = QHBoxLayout()
        brand.setContentsMargins(18, 0, 12, 0)
        brand.setSpacing(10)
        self.logo = QLabel()
        self.logo.setPixmap(icons.app_pixmap(64).scaled(34, 34, Qt.AspectRatioMode.KeepAspectRatio,
                                                         Qt.TransformationMode.SmoothTransformation))
        brand.addWidget(self.logo)
        names = QVBoxLayout()
        names.setSpacing(0)
        names.addWidget(label(APP_NAME, "brand"))
        names.addWidget(label(_("Biometría de tecleo"), "brandSub"))
        brand.addLayout(names, 1)
        sl.addLayout(brand)
        sl.addSpacing(14)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setIconSize(QSize(20, 20))
        self.nav.setCursor(Qt.CursorShape.PointingHandCursor)
        sl.addWidget(self.nav, 1)
        self.theme_btn = QPushButton()
        self.theme_btn.setObjectName("flat")
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_btn.setToolTip(_("Cambiar entre tema claro y oscuro (Ctrl+T)"))
        self.theme_btn.clicked.connect(self.toggle_theme)
        tb = QHBoxLayout()
        tb.setContentsMargins(8, 0, 8, 0)
        tb.addWidget(self.theme_btn)
        sl.addLayout(tb)
        ver = label(f"v{APP_VERSION} · {_('datos locales')}", "brandSub")
        ver.setToolTip(_("Todos los datos se guardan solo en este equipo"))
        ver.setContentsMargins(18, 4, 0, 0)
        sl.addWidget(ver)
        h.addWidget(side)

        self.pages = QStackedWidget()
        h.addWidget(self.pages, 1)
        self.setCentralWidget(root)

        self.dashboard = DashboardPage(service)
        self.enroll = EnrollPage(service)
        self.identify = IdentifyPage(service)
        self.users = UsersPage(service)
        self.history = HistoryPage(service)
        self.access = AccessPage(service)
        self.settings = SettingsPage(service)
        for (title, _icon), page in zip(NAV, (self.dashboard, self.enroll, self.identify, self.users,
                                              self.history, self.access, self.settings)):
            QListWidgetItem(_(title), self.nav)
            self.pages.addWidget(page)
        self.nav.currentRowChanged.connect(self._go)

        for page in (self.enroll, self.identify, self.users, self.settings):
            page.users_changed.connect(self._users_changed)
        self.dashboard.go_identify.connect(lambda: self.nav.setCurrentRow(2))
        self.dashboard.go_enroll.connect(self._enroll_new)
        self.dashboard.go_users.connect(lambda: self.nav.setCurrentRow(3))
        self.dashboard.go_history.connect(lambda: self.nav.setCurrentRow(4))
        self.dashboard.go_access.connect(lambda: self.nav.setCurrentRow(5))
        self.dashboard.go_settings.connect(lambda: self.nav.setCurrentRow(6))
        self.dashboard.add_samples_for.connect(self._add_samples_id)
        self.enroll.go_identify.connect(lambda: self.nav.setCurrentRow(2))
        self.identify.go_enroll.connect(self._enroll_new)
        self.users.add_samples.connect(self._add_samples)
        self.settings.settings_changed.connect(self._settings_changed)
        self.settings.appearance_changed.connect(self.apply_appearance)

        for i in range(len(NAV)):
            QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self, activated=lambda i=i: self.nav.setCurrentRow(i))
        QShortcut(QKeySequence("Ctrl+T"), self, activated=self.toggle_theme)
        QShortcut(QKeySequence("F11"), self, activated=self._toggle_fullscreen)

        self._toast = QLabel(root)
        self._toast.setObjectName("toast")
        self._toast.hide()
        self._toast_fx = QGraphicsOpacityEffect(self._toast)
        self._toast.setGraphicsEffect(self._toast_fx)
        self._toast_anim = QPropertyAnimation(self._toast_fx, b"opacity", self)
        self._toast_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self._hide_toast)

        try:
            QGuiApplication.styleHints().colorSchemeChanged.connect(self._system_scheme_changed)
        except AttributeError:   # Qt < 6.5
            pass

        self._refresh_chrome()
        self.nav.setCurrentRow(0)

    # -- navegación -----------------------------------------------------------
    def _go(self, row: int):
        self.pages.setCurrentIndex(row)
        page = self.pages.widget(row)
        if hasattr(page, "refresh"):
            page.refresh()

    def _users_changed(self):
        self.users.refresh()
        self.identify.refresh()
        self.dashboard.refresh()

    def _settings_changed(self):
        self.identify.refresh()
        self.enroll.refresh()

    def _enroll_new(self):
        if not self.enroll.is_busy():
            self.enroll.reset()
        self.nav.setCurrentRow(1)

    def _add_samples(self, user):
        self.nav.setCurrentRow(1)
        self.enroll.start_for_user(user, 2)

    def _add_samples_id(self, user_id: str):
        user = self.service.storage.get_user(user_id)
        if user:
            self._add_samples(user)

    def _toggle_fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    # -- tema -------------------------------------------------------------------
    def toggle_theme(self):
        self.service.settings["theme"] = "light" if theme.MODE == "dark" else "dark"
        self.service.save_settings()
        self.apply_appearance()

    def _system_scheme_changed(self, *_args):
        if self.service.settings.get("theme", "system") == "system":
            self.apply_appearance()

    def apply_appearance(self):
        app = QApplication.instance()
        theme.apply(app, self.service.settings.get("theme", "system"),
                    float(self.service.settings.get("font_scale", 1.0)))
        self._refresh_chrome()
        for b in self.findChildren(QPushButton):
            refresh_button_icon(b)
        for badge in self.findChildren(Badge):
            badge.restyle()
        for panel in self.findChildren(TypingPanel):
            panel.fit_heights()
            panel.render()
        for w in self.findChildren(QWidget):
            w.update()
        page = self.pages.currentWidget()
        if hasattr(page, "refresh"):
            page.refresh()

    def _refresh_chrome(self):
        for i, (_title, name) in enumerate(NAV):
            item = self.nav.item(i)
            if item:
                item.setIcon(icons.icon(name, theme.TEXT_2, theme.ACCENT, 20))
        dark = theme.MODE == "dark"
        self.theme_btn.setText("  " + (_("Tema claro") if dark else _("Tema oscuro")))
        self.theme_btn.setIcon(icons.icon("sun" if dark else "moon", theme.TEXT_2, theme.TEXT_2, 18))
        self.settings.refresh()

    # -- avisos -------------------------------------------------------------
    def toast(self, text: str, kind: str = "good") -> None:
        mark = {"good": "✓  ", "warn": "!  ", "bad": "✕  "}.get(kind, "")
        self._toast.setText(mark + text)
        self._toast.adjustSize()
        parent = self._toast.parentWidget()
        self._toast.move((parent.width() - self._toast.width() + 232) // 2, parent.height() - self._toast.height() - 28)
        self._toast.raise_()
        self._toast.show()
        self._toast_anim.stop()
        self._toast_anim.setDuration(180)
        self._toast_anim.setStartValue(0.0)
        self._toast_anim.setEndValue(1.0)
        self._toast_anim.start()
        self._toast_timer.start(2600)

    def _hide_toast(self):
        self._toast_anim.stop()
        self._toast_anim.setDuration(400)
        self._toast_anim.setStartValue(1.0)
        self._toast_anim.setEndValue(0.0)
        self._toast_anim.start()
        QTimer.singleShot(420, self._toast.hide)


def _install_excepthook(log_path) -> None:
    """Los errores inesperados se registran y se muestran en lugar de cerrar el programa en silencio."""
    def hook(exc_type, exc, tb):
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        logutil.log.error("Error no controlado:\n%s", text)
        if QApplication.instance():
            QMessageBox.critical(None, APP_NAME, _("Ha ocurrido un error inesperado:\n\n{error}\n\n"
                                                   "Los detalles se han guardado en:\n{path}", error=exc, path=log_path))
    sys.excepthook = hook


def unlock(service: BiometricService) -> bool:
    """Pide la contraseña si los datos están cifrados. Devuelve False si se cancela."""
    if not service.storage.protected:
        return True
    if not crypto.AVAILABLE:
        QMessageBox.critical(None, APP_NAME, _("Los datos están cifrados pero falta el paquete «cryptography».\n"
                                               "Instálalo con: pip install cryptography"))
        return False
    message = ""
    while True:
        dlg = PasswordDialog("unlock", None, message)
        dlg.setWindowIcon(icons.app_icon())
        if not dlg.exec():
            return False
        try:
            service.storage.unlock(dlg.password)
            return True
        except crypto.WrongPassword:
            message = _("Contraseña incorrecta. Inténtalo de nuevo.")
            logutil.log.warning("Contraseña incorrecta al desbloquear")


def setup_language(app: QApplication, service: BiometricService) -> str:
    """Idioma de la interfaz (Ajustes o el del sistema) y traducciones de los diálogos de Qt."""
    code = i18n.resolve(service.settings.get("language"), QLocale.system().name())
    i18n.set_language(code)
    QLocale.setDefault(QLocale(QT_LOCALES.get(code, code)))
    translator = QTranslator(app)
    if translator.load(f"qtbase_{QT_LANGUAGES.get(code, code)}",
                       QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)
    return code


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Opciones propias; el resto (las de Qt, como -platform) se dejan para Qt."""
    parser = argparse.ArgumentParser(prog="keybio", description="Biometría de la dinámica de tecleo.")
    parser.add_argument("--acceso", metavar="NOMBRE",
                        help="verificación de acceso de esa persona con una frase corta (código de salida 0 si "
                             "se confirma su identidad)")
    parser.add_argument("--sistema", metavar="SISTEMA", default="",
                        help="nombre del sistema al que se accede (aparece en el aviso al administrador)")
    return parser.parse_known_args(argv[1:])[0]


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv
    args = parse_args(argv)
    # Aviso inofensivo de Wayland al desactivar el método de entrada en la caja de escritura
    os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.wayland.textinput=false")
    if sys.platform.startswith("win"):
        try:  # icono propio en la barra de tareas de Windows
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("KeyBio.KeystrokeBiometrics")
        except Exception:
            pass
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setDesktopFileName(DESKTOP_ID)   # Linux: une la ventana con su entrada del menú (tools/linux.py)
    app.setWindowIcon(icons.app_icon())
    app.setStyle("Fusion")
    service = BiometricService()
    setup_language(app, service)
    log_path = logutil.setup(service.storage.root)
    _install_excepthook(log_path)
    theme.apply(app, service.settings.get("theme", "system"), float(service.settings.get("font_scale", 1.0)))
    if args.acceso is not None:
        # sin contraseña no se puede comprobar: nunca se devuelve 0 si se cancela
        return run_access(service, args.acceso, args.sistema) if unlock(service) else EXIT_UNCHECKED
    if not unlock(service):
        return 0
    win = MainWindow(service)
    win.show()
    return app.exec()
