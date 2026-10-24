"""Actualizaciones: versiones, archivos de la publicación, tipo de instalación y comprobación de la
descarga. Sin red: la descarga real se prueba a mano (ver docs/desarrollo.md)."""

import hashlib
import os
from pathlib import Path

import pytest

from ksb import updates

BASE = updates.DOWNLOAD_PREFIX + "v2.2.0/"


def release_data(**extra):
    names = ["KeyBio-2.2.0-setup.exe", "KeyBio-windows-x64.zip", "KeyBio-2.2.0-macos-arm64.dmg",
             "KeyBio-2.2.0-linux-amd64.deb", "KeyBio-linux-x64.tar.gz", "SHA256SUMS.txt"]
    data = {"tag_name": "v2.2.0", "html_url": "https://github.com/ryt0n18/keybio/releases/tag/v2.2.0",
            "draft": False, "prerelease": False,
            "assets": [{"name": n, "browser_download_url": BASE + n, "size": 1000} for n in names]}
    data.update(extra)
    return data


def test_versions():
    assert updates.parse_version("v2.1.10") == (2, 1, 10)
    assert updates.parse_version("2.1") is None and updates.parse_version("v2.1.0-beta") is None
    r = updates.parse_release(release_data())
    assert updates.is_newer(r, "2.1.2") and updates.is_newer(r, "2.1.10")
    assert not updates.is_newer(r, "2.2.0") and not updates.is_newer(r, "3.0.0")


def test_release_only_trusts_keybio_downloads():
    data = release_data()
    data["assets"].append({"name": "otro.exe", "browser_download_url": "https://malo.example/otro.exe", "size": 10})
    data["assets"].append({"name": "../x", "browser_download_url": BASE + "x", "size": 10})
    data["assets"].append({"name": "enorme.dmg", "browser_download_url": BASE + "enorme.dmg",
                           "size": updates.MAX_DOWNLOAD + 1})
    r = updates.parse_release(data)
    assert "otro.exe" not in r.assets and "../x" not in r.assets and "enorme.dmg" not in r.assets
    assert len(r.assets) == 6
    for bad in (release_data(draft=True), release_data(prerelease=True), release_data(tag_name="ultima"), [], None):
        with pytest.raises(ValueError):
            updates.parse_release(bad)
    assert updates.parse_release(release_data(html_url="https://malo.example/")).page == updates.RELEASES_PAGE


def test_install_kind(tmp_path):
    k = updates.install_kind
    assert k(frozen=False) == updates.OTHER
    win = tmp_path / "KeyBio"
    win.mkdir()
    (win / "KeyBio.exe").write_bytes(b"")
    assert k(True, str(win / "KeyBio.exe"), "win32") == updates.OTHER          # portable (.zip)
    (win / "unins000.exe").write_bytes(b"")
    assert k(True, str(win / "KeyBio.exe"), "win32") == updates.WINDOWS_SETUP
    if os.name == "nt":   # las rutas de macOS y Linux solo tienen sentido en esos sistemas
        return
    assert k(True, "/Applications/KeyBio.app/Contents/MacOS/KeyBio", "darwin") == updates.MAC_APP
    assert k(True, "/opt/keybio/KeyBio", "linux") == updates.LINUX_DEB
    home = tmp_path / "casa"
    assert k(True, str(home / ".local/opt/keybio/KeyBio"), "linux", home) == updates.LINUX_USER
    assert k(True, str(tmp_path / "Descargas/KeyBio/KeyBio"), "linux", home) == updates.OTHER


def test_asset_for_each_installation():
    r = updates.parse_release(release_data())
    assert updates.asset_for(updates.WINDOWS_SETUP, r) == "KeyBio-2.2.0-setup.exe"
    assert updates.asset_for(updates.MAC_APP, r) == "KeyBio-2.2.0-macos-arm64.dmg"
    assert updates.asset_for(updates.LINUX_DEB, r) == "KeyBio-2.2.0-linux-amd64.deb"
    assert updates.asset_for(updates.LINUX_USER, r) == "KeyBio-linux-x64.tar.gz"
    assert updates.asset_for(updates.OTHER, r) is None
    without_sums = updates.parse_release(release_data(assets=[a for a in release_data()["assets"]
                                                              if a["name"] != "SHA256SUMS.txt"]))
    assert updates.asset_for(updates.LINUX_DEB, without_sums) is None   # sin sumas no se instala nada


def test_checksums(tmp_path):
    f = tmp_path / "KeyBio-2.2.0-linux-amd64.deb"
    f.write_bytes(b"contenido del paquete")
    good = hashlib.sha256(b"contenido del paquete").hexdigest()
    sums = updates.parse_sums(f"{good}  {f.name}\n{'0' * 64} *KeyBio-2.2.0-setup.exe\nbasura\n")
    assert sums == {f.name: good, "KeyBio-2.2.0-setup.exe": "0" * 64}
    assert updates.verify(f, f.name, sums)
    f.write_bytes(b"contenido manipulado")
    assert not updates.verify(f, f.name, sums)
    assert not updates.verify(f, "otro.deb", sums)


@pytest.fixture
def controller(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtWidgets import QApplication

    from ksb.gui import updater

    QApplication.instance() or QApplication([])
    calls = []
    monkeypatch.setattr(updater.QProcess, "start", lambda self, prog, args: calls.append(("run", [prog, *args])))
    monkeypatch.setattr(updater.QDesktopServices, "openUrl",
                        lambda url: calls.append(("open", str(Path(url.toLocalFile())))) or True)
    monkeypatch.setattr(updater.shutil, "which", lambda name: f"/usr/bin/{name}")

    def make(kind):
        ctl = updater.UpdateController(kind=kind)
        ctl.release = updates.parse_release(release_data())
        ctl._dir = tmp_path
        ctl.events = []
        ctl.status.connect(lambda text, k: ctl.events.append((k, text)))
        ctl.quit_requested.connect(lambda: ctl.events.append(("quit", "")))
        ctl.restart_requested.connect(lambda: ctl.events.append(("restart", "")))
        ctl.calls = calls
        return ctl

    return make


def _files(tmp_path, name, content=b"instalador", sums_for=None):
    path = tmp_path / name
    path.write_bytes(content)
    sums = tmp_path / "SHA256SUMS.txt"
    sums.write_text(f"{hashlib.sha256(sums_for or content).hexdigest()}  {name}\n")
    return path, sums


def test_tampered_download_is_never_installed(controller, tmp_path):
    ctl = controller(updates.WINDOWS_SETUP)
    path, sums = _files(tmp_path, "KeyBio-2.2.0-setup.exe", b"instalador manipulado", sums_for=b"instalador")
    ctl._downloaded(path.name, path, sums)
    assert ctl.events[-1][0] == "bad" and not ctl.calls and ("quit", "") not in ctl.events


@pytest.mark.parametrize("kind,name", [
    (updates.WINDOWS_SETUP, "KeyBio-2.2.0-setup.exe"),
    (updates.MAC_APP, "KeyBio-2.2.0-macos-arm64.dmg"),
])
def test_windows_and_mac_open_the_installer_and_close(controller, tmp_path, kind, name):
    ctl = controller(kind)
    path, sums = _files(tmp_path, name)
    ctl._downloaded(name, path, sums)
    assert ctl.calls == [("open", str(path))]
    assert ("quit", "") in ctl.events


def test_deb_installs_with_password_and_restarts(controller, tmp_path):
    from PySide6.QtCore import QProcess

    ctl = controller(updates.LINUX_DEB)
    path, sums = _files(tmp_path, "KeyBio-2.2.0-linux-amd64.deb")
    ctl._downloaded(path.name, path, sums)
    assert ctl.calls == [("run", ["/usr/bin/pkexec", "/usr/bin/apt-get", "install", "-y", str(path)])]
    ctl._proc.finished.emit(126, QProcess.ExitStatus.NormalExit)   # cerró la ventana de la contraseña
    assert ctl.events[-1][0] == "bad" and ("restart", "") not in ctl.events
    ctl._dir = tmp_path / "otra"   # al fallar se borra la carpeta de la descarga
    ctl._dir.mkdir(parents=True)
    path, sums = _files(ctl._dir, "KeyBio-2.2.0-linux-amd64.deb")
    ctl._downloaded(path.name, path, sums)
    ctl._proc.finished.emit(0, QProcess.ExitStatus.NormalExit)
    assert ("restart", "") in ctl.events and ("quit", "") not in ctl.events


def test_deb_without_pkexec_opens_the_system_installer(controller, tmp_path, monkeypatch):
    from ksb.gui import updater

    ctl = controller(updates.LINUX_DEB)
    monkeypatch.setattr(updater.shutil, "which", lambda name: None)
    path, sums = _files(tmp_path, "KeyBio-2.2.0-linux-amd64.deb")
    ctl._downloaded(path.name, path, sums)
    assert ctl.calls == [("open", str(path))] and ("quit", "") not in ctl.events
