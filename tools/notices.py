"""Avisos y licencias de terceros que acompañan a los ejecutables (carpeta «licenses»).

Qt for Python y Qt se distribuyen bajo la LGPL-3.0: hay que entregar su licencia (y la GPL-3.0,
en la que se apoya), avisar de que se usan, decir dónde está su código fuente y permitir
sustituirlas, lo que es posible porque PyInstaller las deja como bibliotecas dinámicas aparte
(por eso no se recomienda --onefile para distribuir). El resto de licencias se copian de los
metadatos de los paquetes instalados, con la versión exacta que se empaqueta.

Uso:  python tools/notices.py DESTINO      (build.py lo llama solo)
"""

from __future__ import annotations

import importlib.metadata as md
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "licenses"

# paquete -> (nombre visible, licencia, código fuente, notas)
COMPONENTS = [
    ("PySide6_Essentials", "Qt for Python (PySide6) y Qt 6: QtCore, QtGui, QtWidgets, QtSvg",
     "GNU LGPL versión 3 (LGPL-3.0.txt, que incorpora la GNU GPL versión 3, GPL-3.0.txt)",
     "https://download.qt.io/official_releases/QtForPython/ y https://download.qt.io/official_releases/qt/",
     "Copyright (C) The Qt Company Ltd. y otros colaboradores. Se usan sin modificar."),
    ("shiboken6", "Shiboken6 (enlace entre Python y Qt)",
     "GNU LGPL versión 3 (LGPL-3.0.txt y GPL-3.0.txt)",
     "https://download.qt.io/official_releases/QtForPython/",
     "Copyright (C) The Qt Company Ltd. Se usa sin modificar."),
    ("cryptography", "cryptography (cifrado con contraseña; incluye OpenSSL)",
     "Apache License 2.0 o BSD de 3 cláusulas, a elección (ficheros cryptography-*); OpenSSL: Apache 2.0",
     "https://github.com/pyca/cryptography", ""),
    ("cffi", "cffi", "MIT-0 (cffi-LICENSE)", "https://github.com/python-cffi/cffi", ""),
    ("pycparser", "pycparser", "BSD de 3 cláusulas (pycparser-LICENSE)", "https://github.com/eliben/pycparser", ""),
    ("pyinstaller", "PyInstaller (cargador del ejecutable)",
     "GNU GPL 2.0 con una excepción que permite distribuir programas empaquetados con cualquier licencia "
     "(pyinstaller-COPYING.txt)", "https://github.com/pyinstaller/pyinstaller", ""),
]

HEADER = """KeyBio incluye componentes de terceros que tienen sus propias licencias. Para esos
componentes se aplican sus licencias, y la licencia de KeyBio no limita los derechos que
te conceden.

Qt for Python (PySide6, Shiboken6) y Qt se incluyen como bibliotecas dinámicas separadas,
sin modificar (en la carpeta _internal/PySide6 del programa; en macOS, dentro de
KeyBio.app/Contents/Frameworks). Puedes sustituirlas por otra versión compatible, y se
permite la ingeniería inversa necesaria para depurar las modificaciones que hagas en ellas.
Su código fuente está disponible en las direcciones indicadas; si lo prefieres, pídelo por
el formulario de contacto de la web de KeyBio y se te enviará.
"""


def _version(dist: str) -> str:
    try:
        return md.version(dist)
    except md.PackageNotFoundError:
        return ""


def write_notices(dest: Path) -> Path:
    """Escribe en ``dest`` el resumen LEEME.txt y copia todas las licencias. Devuelve ``dest``."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for f in STATIC.glob("*.txt"):
        shutil.copyfile(f, dest / f.name)
    # licencia de KeyBio, con BOM para que el instalador de Windows y el Bloc de notas lean las tildes
    (dest / "KeyBio-LICENCIA.txt").write_text((ROOT / "LICENSE").read_text(encoding="utf-8"), encoding="utf-8-sig")
    lines = [HEADER, f"Python {sys.version.split()[0]}", "  Licencia: Python Software Foundation License (Python.txt)", ""]
    for dist, title, lic, source, note in COMPONENTS:
        version = _version(dist)
        if not version:
            continue
        lines += [f"{title} (versión {version})", f"  Licencia: {lic}", f"  Código fuente: {source}"]
        if note:
            lines.append(f"  {note}")
        lines.append("")
        for f in md.distribution(dist).files or []:
            name = Path(str(f)).name
            if "licen" in str(f).lower() or "copying" in name.lower():
                shutil.copyfile(f.locate(), dest / f"{dist.split('_')[0].lower()}-{name}")
    (dest / "LEEME.txt").write_text("\n".join(lines), encoding="utf-8")
    return dest


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    print(write_notices(Path(sys.argv[1])))
