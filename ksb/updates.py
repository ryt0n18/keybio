"""Buscar e instalar versiones nuevas desde las publicaciones de GitHub.

KeyBio solo se conecta a internet cuando la persona pulsa «Buscar actualizaciones» en Ajustes:
consulta la última versión publicada y, si la persona quiere, descarga el instalador de su
sistema, comprueba su suma SHA-256 con la que se publicó en la misma versión y lo abre. No envía
ningún dato de KeyBio. Aquí solo está la lógica; la descarga la hace ksb/gui/updater.py.
"""

from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = "ryt0n18/keybio"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
DOWNLOAD_PREFIX = f"https://github.com/{REPO}/releases/download/"
SUMS_NAME = "SHA256SUMS.txt"
MAX_DOWNLOAD = 400 * 1024 * 1024   # ningún instalador se acerca; evita descargas absurdas

# Cómo está instalado este KeyBio (decide qué se descarga y cómo se instala)
WINDOWS_SETUP = "windows-setup"   # instalador de Windows (hay desinstalador junto al .exe)
MAC_APP = "mac"                   # KeyBio.app (desde el .dmg)
LINUX_DEB = "linux-deb"           # paquete .deb en /opt/keybio
LINUX_USER = "linux-user"         # instalar.sh en ~/.local/opt/keybio
OTHER = "other"                   # portable, carpeta descomprimida o desde el código: página de descargas


@dataclass
class Release:
    tag: str
    version: tuple[int, ...]
    page: str
    assets: dict[str, tuple[str, int]] = field(default_factory=dict)   # nombre -> (url, tamaño)

    @property
    def name(self) -> str:
        return ".".join(map(str, self.version))


def parse_version(text: str) -> tuple[int, ...] | None:
    """'v2.1.10' -> (2, 1, 10); None si no es una versión."""
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", (text or "").strip())
    return tuple(int(x) for x in m.groups()) if m else None


def is_newer(release: Release, current: str) -> bool:
    mine = parse_version(current)
    return mine is not None and release.version > mine


def parse_release(data: dict) -> Release:
    """Respuesta de la API de GitHub -> Release. Solo acepta archivos de las publicaciones de KeyBio."""
    if not isinstance(data, dict) or data.get("draft") or data.get("prerelease"):
        raise ValueError("respuesta inesperada")
    version = parse_version(str(data.get("tag_name", "")))
    if version is None:
        raise ValueError("versión no válida")
    page = str(data.get("html_url") or RELEASES_PAGE)
    if not page.startswith(f"https://github.com/{REPO}/"):
        page = RELEASES_PAGE
    assets = {}
    for a in data.get("assets") or []:
        if not isinstance(a, dict):
            continue
        name, url, size = a.get("name"), a.get("browser_download_url"), a.get("size")
        if (isinstance(name, str) and isinstance(url, str) and isinstance(size, int)
                and url.startswith(DOWNLOAD_PREFIX) and "/" not in name and 0 < size <= MAX_DOWNLOAD):
            assets[name] = (url, size)
    return Release(str(data["tag_name"]), version, page, assets)


def install_kind(frozen: bool | None = None, executable: str | None = None, platform: str | None = None,
                 home: Path | None = None) -> str:
    """Cómo está instalado el KeyBio que se está ejecutando."""
    frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    exe = Path(executable or sys.executable).resolve()
    platform = platform or sys.platform
    home = home or Path.home()
    if not frozen:
        return OTHER
    if platform.startswith("win"):
        return WINDOWS_SETUP if any(exe.parent.glob("unins*.exe")) else OTHER
    if platform == "darwin":
        return MAC_APP if ".app/Contents/MacOS" in exe.as_posix() else OTHER
    if exe.is_relative_to("/opt/keybio"):
        return LINUX_DEB
    if exe.is_relative_to(home / ".local" / "opt" / "keybio"):
        return LINUX_USER
    return OTHER


def asset_for(kind: str, release: Release) -> str | None:
    """Nombre del archivo que actualiza esta instalación, si la versión lo trae."""
    v = release.name
    name = {WINDOWS_SETUP: f"KeyBio-{v}-setup.exe", MAC_APP: f"KeyBio-{v}-macos-arm64.dmg",
            LINUX_DEB: f"KeyBio-{v}-linux-amd64.deb", LINUX_USER: "KeyBio-linux-x64.tar.gz"}.get(kind)
    return name if name in release.assets and SUMS_NAME in release.assets else None


def parse_sums(text: str) -> dict[str, str]:
    """Contenido de SHA256SUMS.txt (formato de sha256sum) -> {nombre: suma}."""
    sums = {}
    for line in text.splitlines():
        m = re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?(\S+)", line.strip())
        if m:
            sums[m.group(2)] = m.group(1).lower()
    return sums


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def verify(path: Path, name: str, sums: dict[str, str]) -> bool:
    expected = sums.get(name)
    return bool(expected) and sha256_of(path) == expected
