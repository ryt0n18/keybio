"""Buscar e instalar actualizaciones desde Ajustes (la lógica está en ksb/updates.py).

Solo se conecta cuando se pulsa el botón. Las descargas van a una carpeta temporal y no se
abren si su suma SHA-256 no coincide con la publicada en la misma versión.
"""

from __future__ import annotations

import json
import shutil
import tarfile
import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from .. import APP_NAME, APP_VERSION, updates
from ..i18n import _

API_TIMEOUT_MS = 20_000
DOWNLOAD_TIMEOUT_MS = 60_000   # sin recibir datos durante este tiempo, se cancela


class UpdateController(QObject):
    """Busca la última versión, la descarga y la instala según cómo esté instalado KeyBio."""

    status = Signal(str, str)          # texto, tipo (muted / good / warn / bad)
    found = Signal(object)             # Release más nueva, o None si ya está al día
    progress = Signal(int)             # porcentaje de la descarga (-1 = sin barra)
    message = Signal(str)              # aviso importante antes de cerrar o abrir el instalador
    quit_requested = Signal()          # el instalador necesita que KeyBio se cierre
    restart_requested = Signal()       # actualizado en el sitio: volver a abrir KeyBio

    def __init__(self, parent=None, kind: str | None = None):
        super().__init__(parent)
        self.net = QNetworkAccessManager(self)
        self.kind = kind or updates.install_kind()
        self.release: updates.Release | None = None
        self._dir: Path | None = None
        self._proc: QProcess | None = None
        self._busy = False

    # -- red
    def _request(self, url: str, timeout: int) -> QNetworkReply:
        req = QNetworkRequest(QUrl(url))
        req.setRawHeader(b"User-Agent", f"{APP_NAME}/{APP_VERSION}".encode())
        req.setRawHeader(b"Accept", b"application/vnd.github+json, application/octet-stream")
        req.setTransferTimeout(timeout)
        return self.net.get(req)

    @staticmethod
    def _error(reply: QNetworkReply) -> str | None:
        if reply.error() != QNetworkReply.NetworkError.NoError:
            return reply.errorString()
        code = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        return None if code is None or 200 <= int(code) < 300 else f"HTTP {code}"

    # -- buscar
    def check(self) -> None:
        if self._busy:
            return
        self._busy = True
        self.status.emit(_("Buscando…"), "muted")
        reply = self._request(updates.API_LATEST, API_TIMEOUT_MS)
        reply.finished.connect(lambda: self._checked(reply))

    def _checked(self, reply: QNetworkReply) -> None:
        self._busy = False
        reply.deleteLater()
        error = self._error(reply)
        try:
            if error:
                raise ValueError(error)
            release = updates.parse_release(json.loads(bytes(reply.readAll()).decode("utf-8")))
        except ValueError as exc:
            self.status.emit(_("No se ha podido comprobar: {error}", error=str(exc)), "bad")
            return
        if updates.is_newer(release, APP_VERSION):
            self.release = release
            self.status.emit(_("Hay una versión nueva: {version}.", version=release.name), "good")
            self.found.emit(release)
        else:
            self.release = None
            self.status.emit(_("Tienes la última versión ({version}).", version=APP_VERSION), "good")
            self.found.emit(None)

    def open_page(self) -> None:
        QDesktopServices.openUrl(QUrl(self.release.page if self.release else updates.RELEASES_PAGE))

    # -- actualizar
    def update(self) -> None:
        if self._busy or self.release is None:
            return
        name = updates.asset_for(self.kind, self.release)
        if name is None:   # portable o desde el código: que descargue la persona
            self.message.emit(_("Esta copia de KeyBio no se puede actualizar sola. Se abre la página de descargas."))
            self.open_page()
            return
        self._busy = True
        self._dir = Path(tempfile.mkdtemp(prefix="keybio-update-"))
        self._download(updates.SUMS_NAME, lambda sums_path: self._download(name, lambda path: self._downloaded(
            name, path, sums_path)))

    def _download(self, name: str, then) -> None:
        url, size = self.release.assets[name]
        target = self._dir / name
        fh = open(target, "wb")
        reply = self._request(url, DOWNLOAD_TIMEOUT_MS)
        state = {"written": 0}

        def chunk():
            data = bytes(reply.readAll())
            state["written"] += len(data)
            if state["written"] > updates.MAX_DOWNLOAD:
                reply.abort()
                return
            fh.write(data)

        def done():
            chunk()
            fh.close()
            reply.deleteLater()
            error = self._error(reply) or (_("descarga incompleta") if state["written"] != size else None)
            if error:
                self._fail(_("No se ha podido comprobar: {error}", error=error))
                return
            then(target)

        def moved(received, total):
            if name != updates.SUMS_NAME and total > 0:
                pct = int(100 * received / total)
                self.progress.emit(pct)
                self.status.emit(_("Descargando… {pct} %", pct=pct), "muted")

        reply.readyRead.connect(chunk)
        reply.downloadProgress.connect(moved)
        reply.finished.connect(done)

    def _downloaded(self, name: str, path: Path, sums_path: Path) -> None:
        sums = updates.parse_sums(sums_path.read_text(encoding="utf-8", errors="replace"))
        if not updates.verify(path, name, sums):
            self._fail(_("La descarga no coincide con la que se publicó; no se ha instalado nada."))
            return
        self.progress.emit(-1)
        try:
            self._install(path)
        except OSError as exc:
            self._fail(_("No se ha podido instalar: {error}", error=str(exc)))

    def _install(self, path: Path) -> None:
        if self.kind in (updates.WINDOWS_SETUP, updates.MAC_APP):
            # se abre como con doble clic: así Windows pide permisos si hacen falta y macOS monta el .dmg
            if self.kind == updates.WINDOWS_SETUP:
                self.message.emit(_("Se abre el instalador. KeyBio se cerrará para que pueda reemplazarlo."))
            else:
                self.message.emit(_("Se abre la imagen de KeyBio: arrastra KeyBio a Aplicaciones y elige "
                                    "«Reemplazar». KeyBio se cerrará ahora."))
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
                raise OSError(str(path))
            self.quit_requested.emit()
        elif self.kind == updates.LINUX_DEB:
            pkexec, apt = shutil.which("pkexec"), shutil.which("apt-get")
            if pkexec and apt:
                # pkexec pide la contraseña en una ventana del sistema; apt instala el .deb comprobado
                self._run([pkexec, apt, "install", "-y", str(path)])
                return
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
                raise OSError(str(path))
            self._busy = False
            self.status.emit(_("Se abre el instalador del sistema: pulsa «Instalar» y escribe tu contraseña. "
                               "Cuando termine, vuelve a abrir KeyBio."), "good")
        elif self.kind == updates.LINUX_USER:
            # instalar.sh (sin administrador): se descomprime y se ejecuta el de la versión nueva
            out = self._dir / "nuevo"
            with tarfile.open(path) as tar:
                tar.extractall(out, filter="data")   # nada fuera de la carpeta ni enlaces peligrosos
            script = out / "KeyBio" / "instalar.sh"
            if not script.is_file():
                raise OSError(_("descarga incompleta"))
            self._run(["sh", str(script)])

    def _run(self, command: list[str]) -> None:
        """Ejecuta el instalador y, si termina bien, reinicia KeyBio ya actualizado."""
        self.status.emit(_("Instalando…"), "muted")
        self._proc = proc = QProcess(self)

        def done(code, _exit_status):
            if code == 0:
                self._busy = False
                self.status.emit(_("Actualizado. KeyBio se reinicia."), "good")
                shutil.rmtree(self._dir, ignore_errors=True)
                self.restart_requested.emit()
            elif Path(command[0]).name == "pkexec" and code == 126:   # se cerró la ventana de la contraseña
                self._fail(_("Instalación cancelada."))
            else:
                self._fail(_("No se ha podido instalar: {error}",
                             error=bytes(proc.readAllStandardError()).decode(errors="replace").strip()[-300:]))

        proc.finished.connect(done)
        proc.start(command[0], command[1:])

    def _fail(self, text: str) -> None:
        self._busy = False
        self.progress.emit(-1)
        self.status.emit(text, "bad")
        if self._dir:
            shutil.rmtree(self._dir, ignore_errors=True)
            self._dir = None
