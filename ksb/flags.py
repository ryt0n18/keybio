"""Banderas de los idiomas, en SVG, para los selectores de idioma del programa (ksb/gui/icons.py)
y de la web (web/i18n/build.py). Se dibujan en lugar de usar emojis porque Windows no muestra los
emojis de bandera. Inglés: Reino Unido, como el inglés del programa y de la web (en-GB);
portugués: Portugal (pt-PT). Todas en 30 × 20 (3:2).
"""

from __future__ import annotations

BODIES = {
    "es": '<rect width="30" height="20" fill="#AA151B"/><rect y="5" width="30" height="10" fill="#F1BF00"/>',
    "en": ('<rect width="30" height="20" fill="#012169"/>'
           '<path d="M0 0L30 20M30 0L0 20" stroke="#fff" stroke-width="4"/>'
           '<path d="M0 0L30 20M30 0L0 20" stroke="#C8102E" stroke-width="1.6"/>'
           '<path d="M15 0V20M0 10H30" stroke="#fff" stroke-width="6"/>'
           '<path d="M15 0V20M0 10H30" stroke="#C8102E" stroke-width="3.4"/>'),
    "ca": ('<rect width="30" height="20" fill="#FCDD09"/>'
           '<path d="M0 3.3H30M0 7.8H30M0 12.2H30M0 16.7H30" stroke="#DA121A" stroke-width="2.2"/>'),
    "gl": '<rect width="30" height="20" fill="#fff"/><path d="M0 0L30 20" stroke="#0099CC" stroke-width="5"/>',
    "eu": ('<rect width="30" height="20" fill="#D52B1E"/>'
           '<path d="M0 0L30 20M30 0L0 20" stroke="#009B48" stroke-width="3"/>'
           '<path d="M15 0V20M0 10H30" stroke="#fff" stroke-width="3"/>'),
    "fr": ('<rect width="30" height="20" fill="#EF4135"/><rect width="20" height="20" fill="#fff"/>'
           '<rect width="10" height="20" fill="#0055A4"/>'),
    "pt": ('<rect width="30" height="20" fill="#FF0000"/><rect width="12" height="20" fill="#006600"/>'
           '<circle cx="12" cy="10" r="4" fill="#FFE000"/>'
           '<path d="M10.4 8h3.2v3.2a1.6 1.6 0 0 1-3.2 0z" fill="#fff" stroke="#FF0000" stroke-width=".7"/>'),
    "de": ('<rect width="30" height="20" fill="#FFCE00"/><rect width="30" height="13.4" fill="#DD0000"/>'
           '<rect width="30" height="6.7" fill="#000"/>'),
    "it": ('<rect width="30" height="20" fill="#CE2B37"/><rect width="20" height="20" fill="#fff"/>'
           '<rect width="10" height="20" fill="#009246"/>'),
}


def svg(code: str, attrs: str = "") -> str:
    """La bandera de un idioma como SVG completo; ``attrs`` añade atributos (clase, accesibilidad…)."""
    extra = f" {attrs}" if attrs else ""
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 30 20"{extra}>{BODIES[code]}</svg>'
