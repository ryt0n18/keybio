"""Traducción de la interfaz.

El texto original, en español, es la clave: ``_("Volver")`` devuelve "Back" con el inglés
activado. Los catálogos están en ``ksb/locale/<idioma>.json``::

    {"Volver": "Back", "{n} muestra": {"one": "{n} sample", "other": "{n} samples"}}

- ``_(texto, **valores)`` traduce y sustituye las variables ``{nombre}``.
- ``_n(singular, plural, n, **valores)`` elige la forma según el número (``{n}`` es el número).
- ``N_(texto)`` solo marca un texto que se define al importar un módulo (antes de saber el
  idioma); se traduce después, al mostrarlo, con ``_()``.

``tools/i18n.py`` extrae los textos marcados del código y comprueba que cada catálogo los tiene
todos, con las mismas variables.
"""

from __future__ import annotations

import json
import locale
import os
import sys
from pathlib import Path

SOURCE = "es"
# código -> nombre en su propio idioma
LANGUAGES = {
    "es": "Español",
    "en": "English",
    "ca": "Català",
    "gl": "Galego",
    "eu": "Euskara",
    "fr": "Français",
    "pt": "Português",
    "de": "Deutsch",
    "it": "Italiano",
}
FALLBACK = "en"   # idioma si el del sistema no está disponible
# teclado en pantalla habitual de cada idioma (ksb/gui/keyboard.py)
KEYBOARDS = {"es": "es", "ca": "es", "gl": "es", "eu": "es", "en": "us", "fr": "fr", "pt": "pt", "de": "de",
             "it": "it"}
ENV = "KEYBIO_LANGUAGE"   # fuerza un idioma (lo usan las pruebas)

_language = SOURCE
_catalog: dict[str, object] = {}


def locale_dir() -> Path:
    """Catálogos: dentro del ejecutable empaquetado (PyInstaller) o junto a este módulo."""
    bundle = getattr(sys, "_MEIPASS", None)
    return Path(bundle) / "ksb" / "locale" if bundle else Path(__file__).resolve().parent / "locale"


def load_catalog(code: str) -> dict[str, object]:
    if code == SOURCE:
        return {}
    path = locale_dir() / f"{code}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def system_language(qt_name: str | None = None) -> str:
    """Idioma del sistema si KeyBio lo tiene; si no, inglés. ``qt_name`` es QLocale.system().name()."""
    names = [qt_name, os.environ.get("LANGUAGE", "").split(":")[0], os.environ.get("LC_ALL"),
             os.environ.get("LANG")]
    try:
        names.append(locale.getlocale()[0])
    except ValueError:
        pass
    for name in names:
        code = (name or "").replace("-", "_").split("_")[0].lower()
        if code in LANGUAGES:
            return code
    return FALLBACK


def resolve(setting: str | None, qt_name: str | None = None) -> str:
    """Idioma a usar: la variable KEYBIO_LANGUAGE, el de Ajustes o el del sistema ("auto")."""
    forced = os.environ.get(ENV)
    if forced in LANGUAGES:
        return forced
    if setting in LANGUAGES:
        return setting
    return system_language(qt_name)


def set_language(code: str) -> None:
    global _language, _catalog
    _language = code if code in LANGUAGES else SOURCE
    _catalog = load_catalog(_language)


def language() -> str:
    return _language


def plural_form(n: float, code: str | None = None) -> str:
    """"one" u "other". En francés el 0 también va en singular."""
    code = code or _language
    if code == "fr":
        return "one" if abs(n) < 2 else "other"
    return "one" if n == 1 else "other"


def _(text: str, **values) -> str:
    out = _catalog.get(text) if _catalog else None
    out = out if isinstance(out, str) and out else text
    return out.format(**values) if values else out


def _n(singular: str, plural: str, n: float, **values) -> str:
    entry = _catalog.get(singular) if _catalog else None
    form = plural_form(n)
    if isinstance(entry, dict) and entry.get(form):
        text = entry[form]
    else:
        text = singular if plural_form(n, SOURCE) == "one" else plural
    return text.format(n=n, **values)


def N_(text: str) -> str:
    return text
