"""Integración con el escritorio de Linux: entrada en el menú de aplicaciones, iconos y paquete .deb.

Uso, después de tools/build.py (que ya llama a «prepare» en Linux):
    python tools/linux.py prepare   # añade a dist/KeyBio el instalador por usuario (instalar.sh),
                                    # la entrada del menú y los iconos
    python tools/linux.py deb       # crea dist/KeyBio-<versión>-linux-amd64.deb

Con el .deb (Ubuntu, Debian, Mint…) el programa se instala con doble clic en /opt/keybio. Con el
.tar.gz, «KeyBio/instalar.sh» lo instala solo para el usuario, sin permisos de administrador, en
~/.local/opt/keybio. En los dos casos aparece en el menú y en el buscador de aplicaciones. Los
perfiles están en otra carpeta (~/.local/share/keybio) y desinstalar no los borra.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ksb import APP_AUTHOR, APP_VERSION  # noqa: E402
from ksb.i18n import FALLBACK, LANGUAGES  # noqa: E402

APP_ID = "io.github.ryt0n18.keybio"   # también en ksb/gui/app.py (setDesktopFileName)
WM_CLASS = "KeyBio"
ICON_SIZES = (32, 48, 64, 128, 256, 512)
MAINTAINER = f"{APP_AUTHOR} <256401486+ryt0n18@users.noreply.github.com>"
# Bibliotecas del sistema que el ejecutable no lleva dentro (las de Qt para X11 y Wayland)
DEPENDS = ["libglib2.0-0", "libfontconfig1", "libdbus-1-3", "libegl1", "libgl1", "libxkbcommon0",
           "libxkbcommon-x11-0", "libxcb-cursor0"]

# Palabras con las que se encuentra en el buscador de aplicaciones, además del nombre
KEYWORDS = {
    "es": "biometría;tecleo;teclado;escritura;identidad;verificación;",
    "en": "biometrics;keystroke;typing;keyboard;identity;verification;authentication;",
    "ca": "biometria;tecleig;teclat;escriptura;identitat;verificació;",
    "gl": "biometría;tecleo;teclado;escritura;identidade;verificación;",
    "eu": "biometria;teklatzea;teklatua;idazketa;nortasuna;egiaztapena;",
    "fr": "biométrie;frappe;clavier;saisie;identité;vérification;",
    "pt": "biometria;digitação;teclado;escrita;identidade;verificação;",
    "de": "Biometrie;Tippen;Tastatur;Tippverhalten;Identität;Verifizierung;",
    "it": "biometria;digitazione;tastiera;scrittura;identità;verifica;",
}


def site_url() -> str:
    """La dirección de la web, de web/i18n/build.py (si cambia el dominio, se cambia solo allí)."""
    text = (ROOT / "web" / "i18n" / "build.py").read_text(encoding="utf-8")
    return re.search(r'^SITE_URL = "([^"]+)"', text, re.M).group(1)


def _web_texts() -> dict[str, tuple[str, str]]:
    """(nombre genérico, descripción) en cada idioma, de los catálogos de la web."""
    out = {}
    for code in LANGUAGES:
        page = json.loads((ROOT / "web" / "i18n" / f"{code}.json").read_text(encoding="utf-8"))["page"]
        out[code] = (page["index.hero.eyebrow"], page["index.hero.title"].rstrip("."))
    return out


def desktop_entry(executable: str) -> str:
    """Fichero .desktop (menú de aplicaciones). Sin idioma, en inglés, como el resto del programa."""
    texts = _web_texts()
    generic, comment = texts[FALLBACK]
    # Versión 1.4 del formato: la validan también los escritorios de Ubuntu 22.04 y Debian 12
    lines = ["[Desktop Entry]", "Type=Application", "Version=1.4", "Name=KeyBio",
             f"GenericName={generic}"]
    lines += [f"GenericName[{c}]={texts[c][0]}" for c in LANGUAGES if c != FALLBACK]
    lines.append(f"Comment={comment}")
    lines += [f"Comment[{c}]={texts[c][1]}" for c in LANGUAGES if c != FALLBACK]
    lines.append(f"Keywords={KEYWORDS[FALLBACK]}{KEYWORDS['es']}")
    lines += [f"Keywords[{c}]={KEYWORDS[c]}" for c in LANGUAGES if c != FALLBACK]
    quoted = f'"{executable}"' if " " in executable else executable
    lines += [f"Exec={quoted}", f"TryExec={executable}", f"Icon={APP_ID}", "Terminal=false",
              "Categories=Utility;", "StartupNotify=true", f"StartupWMClass={WM_CLASS}"]
    return "\n".join(lines) + "\n"


def metainfo() -> str:
    """Ficha AppStream: con ella las tiendas de aplicaciones (GNOME Software, Discover…) lo muestran bien."""
    texts = _web_texts()
    esc = {"&": "&amp;", "<": "&lt;", ">": "&gt;"}

    def x(text: str) -> str:
        return "".join(esc.get(ch, ch) for ch in text)

    summary = [f"  <summary>{x(texts[FALLBACK][1])}</summary>"]
    summary += [f'  <summary xml:lang="{c}">{x(texts[c][1])}</summary>' for c in LANGUAGES if c != FALLBACK]
    names = ", ".join(LANGUAGES.values())
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>{APP_ID}</id>
  <metadata_license>CC0-1.0</metadata_license>
  <project_license>LicenseRef-proprietary</project_license>
  <name>KeyBio</name>
{chr(10).join(summary)}
  <developer id="io.github.ryt0n18">
    <name>{x(APP_AUTHOR)}</name>
  </developer>
  <description>
    <p>KeyBio recognizes people by the way they type: how long each key is held down, the rhythm
    between keys, how capital letters are typed and how mistakes are corrected.</p>
    <p>Everything is processed and stored on your computer, optionally encrypted with a password.
    Nothing is sent over the network.</p>
    <p>Languages: {x(names)}.</p>
  </description>
  <launchable type="desktop-id">{APP_ID}.desktop</launchable>
  <url type="homepage">{site_url()}</url>
  <categories>
    <category>Utility</category>
  </categories>
  <content_rating type="oars-1.1"/>
  <provides>
    <binary>keybio</binary>
  </provides>
  <releases>
    <release version="{APP_VERSION}" date="{release_date()}"/>
  </releases>
</component>
"""


def release_date() -> str:
    """Fecha del último commit (la misma en cada compilación de esa versión); si no hay git, la de hoy."""
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cs"], cwd=ROOT, capture_output=True, text=True,
                             check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        out = ""
    return out or datetime.date.today().isoformat()


def _icons(folder: Path) -> None:
    """Iconos en los tamaños habituales: <folder>/<n>x<n>/<id>.png."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication

    from ksb.gui.icons import app_pixmap

    _icons.app = QGuiApplication.instance() or QGuiApplication([])   # necesaria para pintar
    for size in ICON_SIZES:
        target = folder / f"{size}x{size}"
        target.mkdir(parents=True, exist_ok=True)
        app_pixmap(size).save(str(target / f"{APP_ID}.png"), "PNG")


def prepare(app_dir: Path) -> None:
    """Añade al programa empaquetado lo que usa instalar.sh: el propio script, la entrada y los iconos."""
    linux = app_dir / "linux"
    shutil.rmtree(linux, ignore_errors=True)
    linux.mkdir(parents=True)
    _icons(linux / "icons")
    # instalar.sh pone la ruta real del ejecutable en Exec y TryExec
    (linux / f"{APP_ID}.desktop").write_text(desktop_entry("/opt/keybio/KeyBio"), encoding="utf-8")
    script = app_dir / "instalar.sh"
    shutil.copyfile(ROOT / "tools" / "linux" / "instalar.sh", script)
    script.chmod(0o755)


def _glibc_needed(app_dir: Path) -> str | None:
    """Versión de glibc más alta que piden el ejecutable y sus bibliotecas (para «Depends: libc6»)."""
    if not shutil.which("objdump"):
        return None
    found = set()
    for path in app_dir.rglob("*"):
        if path.is_file() and (path.suffix == ".so" or ".so." in path.name or path.name == "KeyBio"):
            out = subprocess.run(["objdump", "-T", str(path)], capture_output=True, text=True).stdout
            found.update(re.findall(r"GLIBC_(\d+(?:\.\d+)+)", out))
    return max(found, key=lambda v: tuple(int(p) for p in v.split("."))) if found else None


def build_deb(app_dir: Path, out_dir: Path) -> Path:
    """Paquete .deb: el programa en /opt/keybio, «keybio» en el PATH, el menú, los iconos y la ficha."""
    if not shutil.which("dpkg-deb"):
        raise SystemExit("Hace falta dpkg-deb (paquete dpkg) para crear el .deb.")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "pkg"
        opt = root / "opt" / "keybio"
        shutil.copytree(app_dir, opt, symlinks=True, ignore=shutil.ignore_patterns("instalar.sh", "linux"))
        (root / "usr" / "bin").mkdir(parents=True)
        (root / "usr" / "bin" / "keybio").symlink_to("/opt/keybio/KeyBio")
        apps = root / "usr" / "share" / "applications"
        apps.mkdir(parents=True)
        (apps / f"{APP_ID}.desktop").write_text(desktop_entry("/opt/keybio/KeyBio"), encoding="utf-8")
        meta = root / "usr" / "share" / "metainfo"
        meta.mkdir(parents=True)
        (meta / f"{APP_ID}.metainfo.xml").write_text(metainfo(), encoding="utf-8")
        icons = Path(tmp) / "icons"
        _icons(icons)
        for size_dir in icons.iterdir():
            target = root / "usr" / "share" / "icons" / "hicolor" / size_dir.name / "apps"
            target.mkdir(parents=True)
            shutil.copy(size_dir / f"{APP_ID}.png", target)
        root.chmod(0o755)
        for path in root.rglob("*"):   # permisos normales de un paquete
            if path.is_symlink():
                continue
            if path.is_dir():
                path.chmod(0o755)
            else:
                path.chmod(0o755 if os.access(path, os.X_OK) else 0o644)
        size_kb = sum(p.stat().st_size for p in root.rglob("*") if p.is_file() and not p.is_symlink()) // 1024
        glibc = _glibc_needed(opt)
        depends = ([f"libc6 (>= {glibc})"] if glibc else []) + DEPENDS
        control = root / "DEBIAN" / "control"
        control.parent.mkdir()
        control.write_text(f"""Package: keybio
Version: {APP_VERSION}
Architecture: amd64
Maintainer: {MAINTAINER}
Installed-Size: {size_kb}
Depends: {", ".join(depends)}
Section: utils
Priority: optional
Homepage: {site_url()}
Description: Keystroke dynamics biometrics
 KeyBio recognizes people by the way they type: how long each key is held
 down, the rhythm between keys, capital letters and corrections. Everything
 stays on the computer. Available in Spanish, English, Catalan, Galician,
 Basque, French, Portuguese, German and Italian.
""", encoding="utf-8")
        out_dir.mkdir(parents=True, exist_ok=True)
        deb = out_dir / f"KeyBio-{APP_VERSION}-linux-amd64.deb"
        subprocess.run(["dpkg-deb", "--root-owner-group", "-Zxz", "--build", str(root), str(deb)], check=True)
    return deb


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["prepare", "deb"])
    ap.add_argument("--app", default=str(ROOT / "dist" / "KeyBio"), help="carpeta del programa empaquetado")
    ap.add_argument("--out", default=str(ROOT / "dist"), help="dónde dejar el .deb")
    args = ap.parse_args(argv)
    app_dir = Path(args.app)
    if not (app_dir / "KeyBio").is_file():
        raise SystemExit(f"No está el programa empaquetado en {app_dir} (ejecuta antes tools/build.py).")
    if args.action == "prepare":
        prepare(app_dir)
        print(f"Listo: {app_dir / 'instalar.sh'}")
    else:
        print(f"Listo: {build_deb(app_dir, Path(args.out))}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
