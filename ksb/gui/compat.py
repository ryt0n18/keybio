"""Parches de compatibilidad con versiones concretas de Python y PySide6."""

from __future__ import annotations

import ctypes
import sys


def immortalize_singletons() -> bool:
    """Protege a ``None``, ``True`` y ``False`` de un fallo de PySide6 6.12 con Python ≤ 3.11.

    En esa combinación, cada llamada a un método de Qt que no devuelve nada (``setPen``,
    ``drawText``, ``update``…) libera una referencia de ``None`` de más; tras unos miles de
    repintados Python se cierra con «deallocating None». Desde Python 3.12 estos objetos son
    inmortales y el fallo no existe. Aquí se imita esa inmortalidad sumando 2**40 a su contador
    (nunca se liberan: son objetos estáticos del intérprete). Devuelve True si se ha aplicado.
    """
    if sys.version_info >= (3, 12) or sys.implementation.name != "cpython":
        return False
    for obj in (None, True, False):
        ctypes.c_ssize_t.from_address(id(obj)).value += 1 << 40
    return True
