"""Las pruebas comprueban los textos en español, el idioma original: se fija aunque el sistema
(por ejemplo, la integración continua) esté en otro idioma."""

import os

os.environ["KEYBIO_LANGUAGE"] = "es"

from ksb import i18n  # noqa: E402

i18n.set_language("es")

try:   # fechas y números de Qt también en español
    from PySide6.QtCore import QLocale
    QLocale.setDefault(QLocale("es"))
except ImportError:
    pass
