"""Utilidades de texto: normalización, comparación y distancia de edición."""

from __future__ import annotations

import unicodedata

# Caracteres "sueltos" que puede dejar una tecla muerta mal compuesta.
_SPACING_DIACRITICS = set("´`¨^~˜")


def fold(text: str) -> str:
    """Quita tildes y diacríticos ('canción' -> 'cancion', 'ñ' -> 'n').

    La comparación con el texto objetivo se hace sobre la versión plegada,
    de modo que escribir sin tildes (o con un sistema donde las teclas
    muertas no funcionan) no penaliza la precisión.
    """
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def normalize_typed(typed: str, target: str) -> str:
    """Normaliza lo escrito para compararlo con el objetivo."""
    allowed = set(target)
    cleaned = "".join(c for c in typed if c not in _SPACING_DIACRITICS or c in allowed)
    return fold(cleaned)


def levenshtein(a: str, b: str) -> int:
    """Distancia de edición clásica (inserción, borrado, sustitución)."""
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(
                previous[j] + 1,
                current[j - 1] + 1,
                previous[j - 1] + (ca != cb),
            ))
        previous = current
    return previous[-1]


def char_status(typed_norm: str, target_norm: str) -> list[bool]:
    """Para cada carácter escrito, indica si coincide con el objetivo en esa posición."""
    return [i < len(target_norm) and c == target_norm[i] for i, c in enumerate(typed_norm)]
