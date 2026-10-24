"""KeyBio: biometría del comportamiento basada en la dinámica de tecleo."""

import sys
from pathlib import Path

APP_NAME = "KeyBio"
APP_VERSION = "2.2.0"
APP_AUTHOR = "Álvaro Ruiz (ryt0n18)"
COPYRIGHT = f"© 2026 {APP_AUTHOR}. Todos los derechos reservados."


def licenses_dir() -> Path:
    """Licencias de terceros: dentro del ejecutable empaquetado (PyInstaller) o en el proyecto."""
    bundle = getattr(sys, "_MEIPASS", None)
    return Path(bundle) / "licenses" if bundle else Path(__file__).resolve().parent.parent / "licenses"
