"""Genera un ejecutable de KeyBio con PyInstaller.

Uso:  python tools/build.py [--onefile] [--distpath DIR] [--workpath DIR]

PyInstaller crea el ejecutable para el sistema en el que se ejecuta:
Windows → dist/KeyBio/KeyBio.exe, Linux → dist/KeyBio/KeyBio, macOS → dist/KeyBio.app.
Las licencias de terceros (tools/notices.py) van dentro, en la carpeta «licenses».
Para distribuir es mejor no usar --onefile: con la carpeta, las bibliotecas de Qt (LGPL)
quedan como ficheros aparte que se pueden sustituir.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def make_icons(folder: Path) -> Path:
    """Dibuja el icono de la aplicación (.ico y .png; en macOS, también .icns) y devuelve el del sistema."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(ROOT))
    from PySide6.QtGui import QGuiApplication

    from ksb.gui.icons import app_pixmap

    make_icons.app = QGuiApplication.instance() or QGuiApplication([])   # necesaria para pintar
    folder.mkdir(parents=True, exist_ok=True)
    ico = folder / "keybio.ico"
    app_pixmap(256).save(str(ico), "ICO")
    app_pixmap(512).save(str(folder / "keybio.png"), "PNG")
    if sys.platform == "darwin":
        iconset = folder / "keybio.iconset"
        iconset.mkdir(exist_ok=True)
        for size in (16, 32, 128, 256, 512):
            app_pixmap(size).save(str(iconset / f"icon_{size}x{size}.png"), "PNG")
            app_pixmap(size * 2).save(str(iconset / f"icon_{size}x{size}@2x.png"), "PNG")
        icns = folder / "keybio.icns"
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(icns)], check=True)
        return icns
    return ico


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--onefile", action="store_true", help="un único fichero ejecutable (arranca más lento)")
    ap.add_argument("--distpath", default=str(ROOT / "dist"))
    ap.add_argument("--workpath", default=str(ROOT / "build"))
    args = ap.parse_args()

    ico = make_icons(Path(args.workpath) / "icon")
    sys.path.insert(0, str(ROOT / "tools"))
    from notices import write_notices

    from ksb import APP_VERSION, COPYRIGHT

    env = {**os.environ, "KEYBIO_ICON": str(ico), "KEYBIO_VERSION": APP_VERSION, "KEYBIO_COPYRIGHT": COPYRIGHT,
           "KEYBIO_LICENSES": str(write_notices(Path(args.workpath) / "licenses")),
           "KEYBIO_ONEFILE": "1" if args.onefile else "0"}
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", args.distpath,
           "--workpath", args.workpath, str(ROOT / "tools" / "keybio.spec")]
    print(" ".join(cmd))
    code = subprocess.call(cmd, cwd=ROOT, env=env)
    if code == 0 and sys.platform.startswith("linux") and not args.onefile:
        from linux import prepare   # tools/linux.py: instalar.sh, entrada del menú e iconos

        prepare(Path(args.distpath) / "KeyBio")
    return code


if __name__ == "__main__":
    sys.exit(main())
