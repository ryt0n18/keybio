"""Avisa a los buscadores de IndexNow (Bing, DuckDuckGo, Yandex, Seznam, Naver…) de las páginas
de la web, para que las visiten antes. No necesita cuenta: basta con que la clave esté publicada
en /<clave>.txt (la genera build.py con INDEXNOW_KEY).

Úsalo después de desplegar una guía nueva o un cambio importante. Sin argumentos avisa de todas las
páginas del sitemap; también se pueden pasar las direcciones concretas.

Uso:  python web/i18n/indexnow.py
      python web/i18n/indexnow.py https://keybio.pages.dev/guias/nueva-guia
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import INDEXNOW_KEY, PUBLIC, SITE_URL  # noqa: E402

ENDPOINT = "https://api.indexnow.org/indexnow"


def main(argv: list[str]) -> int:
    if not INDEXNOW_KEY:
        print("Falta INDEXNOW_KEY en web/i18n/build.py", file=sys.stderr)
        return 1
    urls = argv or re.findall(r"<loc>(.*?)</loc>", (PUBLIC / "sitemap.xml").read_text(encoding="utf-8"))
    body = json.dumps({"host": urlparse(SITE_URL).hostname, "key": INDEXNOW_KEY,
                       "keyLocation": f"{SITE_URL}/{INDEXNOW_KEY}.txt", "urlList": urls}).encode()
    request = urllib.request.Request(ENDPOINT, data=body, method="POST",
                                     headers={"Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(request, timeout=30) as response:
        # 200: recibido; 202: recibido, la clave se comprobará más tarde
        print(f"IndexNow: {response.status} ({len(urls)} direcciones)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
