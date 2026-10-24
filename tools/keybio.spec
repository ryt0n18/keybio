# Especificación de PyInstaller para KeyBio. La usa tools/build.py, que antes de llamar a
# PyInstaller fija KEYBIO_ICON, KEYBIO_LICENSES, KEYBIO_VERSION, KEYBIO_COPYRIGHT y KEYBIO_ONEFILE.
# -*- mode: python -*-

import os
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent  # noqa: F821 (SPECPATH lo define PyInstaller)
ICON = os.environ["KEYBIO_ICON"]
LICENSES = os.environ["KEYBIO_LICENSES"]
VERSION = os.environ["KEYBIO_VERSION"]
COPYRIGHT = os.environ["KEYBIO_COPYRIGHT"]
ONEFILE = os.environ.get("KEYBIO_ONEFILE") == "1"
BUNDLE_ID = "es.keybio.app"
sys.path.insert(0, str(ROOT))
from ksb.i18n import LANGUAGES  # noqa: E402 (idiomas del programa, para macOS)

# Partes de Qt que PyInstaller recoge pero KeyBio no usa. Qt Virtual Keyboard, además, es
# GPL-3.0 (no LGPL): no puede ir en un programa con todos los derechos reservados. Qml y Quick
# solo los pide ese teclado, y Qt PDF solo un complemento para abrir PDF como imágenes.
EXCLUDE = ("virtualkeyboard", "qt6qml", "qtqml", "qt6quick", "qtquick", "qt6pdf", "qtpdf", "qpdf")


def wanted(entry) -> bool:
    name = entry[0].replace("\\", "/").lower()
    return not any(x in name for x in EXCLUDE)


a = Analysis(  # noqa: F821
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    datas=[(LICENSES, "licenses"), (str(ROOT / "ksb" / "locale"), "ksb/locale")],
    excludes=["PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtPdf", "tkinter"],
)
a.binaries = [b for b in a.binaries if wanted(b)]
a.datas = [d for d in a.datas if wanted(d)]
pyz = PYZ(a.pure)  # noqa: F821

common = dict(name="KeyBio", console=False, icon=ICON, upx=False)
if ONEFILE:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], **common)  # noqa: F821
    target = exe
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **common)  # noqa: F821
    target = COLLECT(exe, a.binaries, a.datas, name="KeyBio", upx=False)  # noqa: F821

if sys.platform == "darwin":
    BUNDLE(  # noqa: F821
        target,
        name="KeyBio.app",
        icon=ICON,
        bundle_identifier=BUNDLE_ID,
        version=VERSION,
        info_plist={
            "CFBundleDisplayName": "KeyBio",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "NSHumanReadableCopyright": COPYRIGHT,
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.utilities",
            "LSMinimumSystemVersion": "11.0",
            "CFBundleDevelopmentRegion": "es",
            "CFBundleLocalizations": list(LANGUAGES),
        },
    )
