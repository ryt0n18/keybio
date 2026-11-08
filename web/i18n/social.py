"""Genera las imágenes para redes sociales (Open Graph, 1200×630) de cada idioma.

    web/public/assets/img/social/<idioma>.png

Es la imagen que aparece al compartir un enlace de la web (WhatsApp, LinkedIn, X, Telegram…).
Lleva el icono, el nombre y el título de la portada del idioma (index.hero.eyebrow e
index.hero.title de su catálogo). Se dibuja con Chrome sin ventana, el mismo que usan las pruebas.
Solo hace falta volver a generarlas si cambian esos textos.

Uso:  python web/i18n/social.py
"""

from __future__ import annotations

import html
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

I18N = Path(__file__).resolve().parent
WEB = I18N.parent
OUT = WEB / "public" / "assets" / "img" / "social"
sys.path.insert(0, str(WEB / "tests"))
sys.path.insert(0, str(I18N))
from build import LANGUAGES  # noqa: E402
from run import find_chrome  # noqa: E402

# Barras de tiempos de pulsación (como el dibujo de la portada): inicio y duración relativos
BARS = [(0, 9), (12, 8), (19, 11), (33, 7), (42, 10), (55, 8), (62, 12), (78, 9), (89, 8)]

CARD = """<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><style>
html, body {{ margin: 0; width: 1200px; height: 630px; }}
body {{ background: #f1f0ec; font-family: "Inter", "Segoe UI", "Ubuntu", "Noto Sans", system-ui, sans-serif;
        color: #0b0b0b; display: flex; flex-direction: column; justify-content: space-between;
        padding: 72px 80px 64px; box-sizing: border-box; }}
.brand {{ display: flex; align-items: center; gap: 22px; font-size: 44px; font-weight: 750; letter-spacing: -0.02em; }}
.brand svg {{ width: 76px; height: 76px; }}
.eyebrow {{ color: #2a78d6; font-weight: 700; font-size: 26px; letter-spacing: .08em; text-transform: uppercase; margin: 0 0 18px; }}
h1 {{ font-size: 76px; line-height: 1.05; letter-spacing: -0.035em; margin: 0; max-width: 1000px; }}
.bars {{ position: relative; height: 46px; }}
.bars span {{ position: absolute; top: 0; height: 46px; border-radius: 10px; background: #2a78d6; }}
.bars span:nth-child(3n+2) {{ background: #eb6834; }}
.bars span:nth-child(3n) {{ background: #cde2fb; }}
</style></head><body>
<div class="brand">{icon}<span>KeyBio</span></div>
<div><p class="eyebrow">{eyebrow}</p><h1>{title}</h1></div>
<div class="bars">{bars}</div>
</body></html>"""


def card(code: str) -> str:
    page = json.loads((I18N / f"{code}.json").read_text(encoding="utf-8"))["page"]
    icon = (WEB / "public" / "assets" / "img" / "icon.svg").read_text(encoding="utf-8")
    bars = "".join(f'<span style="left:{start}%;width:{width}%"></span>' for start, width in BARS)
    return CARD.format(lang=code, icon=icon, eyebrow=html.escape(page["index.hero.eyebrow"]),
                       title=page["index.hero.title"], bars=bars)


def main() -> int:
    chrome = find_chrome()
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for code, _, _ in LANGUAGES:
            src = Path(tmp) / f"{code}.html"
            src.write_text(card(code), encoding="utf-8")
            cmd = [chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
                   f"--user-data-dir={tmp}/profile", "--window-size=1200,630",
                   f"--screenshot={OUT / f'{code}.png'}", src.as_uri()]
            if os.environ.get("CI"):
                cmd.insert(1, "--no-sandbox")
            subprocess.run(cmd, capture_output=True, check=True, timeout=120)
            print(f"{code}: {(OUT / f'{code}.png').relative_to(WEB)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
