"""Registro de errores en un fichero rotativo dentro de la carpeta de datos."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

log = logging.getLogger("keybio")


def setup(data_dir: Path) -> Path:
    folder = Path(data_dir) / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "keybio.log"
    if not log.handlers:
        handler = RotatingFileHandler(path, maxBytes=512_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
    log.info("Inicio (%s, Python %s)", sys.platform, sys.version.split()[0])
    return path
