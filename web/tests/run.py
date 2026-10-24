"""Ejecuta las pruebas de la web en Chrome sin ventana.

Sirve la carpeta web/ en un puerto local, abre con Chrome headless las páginas de prueba
(tests.html: algoritmo y valoraciones; e2e.html: la demo de principio a fin) y lee el
resultado del DOM. No necesita Node ni instalar nada más.

Uso:  python web/tests/run.py        (código de salida 1 si alguna prueba falla)
"""

from __future__ import annotations

import functools
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

WEB = Path(__file__).resolve().parents[1]
CANDIDATES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome")


class _Quiet(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".js": "text/javascript"}

    def log_message(self, *args):
        pass


def find_chrome() -> str:
    if env := os.environ.get("CHROME"):
        return env
    for name in CANDIDATES:
        if path := shutil.which(name):
            return path
    sys.exit("No se encuentra Chrome/Chromium (se puede indicar con la variable CHROME).")


PAGES = [("tests/test.html", 60_000), ("tests/e2e.html", 1_800_000)]   # (página, tiempo virtual en ms)


def run_page(chrome: str, port: int, page: str, budget: int) -> list[dict]:
    with tempfile.TemporaryDirectory() as profile:
        cmd = [chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
               f"--user-data-dir={profile}", f"--virtual-time-budget={budget}", "--dump-dom",
               f"http://127.0.0.1:{port}/{page}"]
        if os.environ.get("CI"):
            cmd.insert(1, "--no-sandbox")
        dom = subprocess.run(cmd, capture_output=True, text=True, timeout=600).stdout
    match = re.search(r'<pre id="results"[^>]*data-done="1"[^>]*>(.*?)</pre>', dom, re.S)
    if not match:
        return [{"name": f"{page}: no ha terminado", "ok": False, "error": dom[:2000]}]
    return json.loads(html.unescape(match.group(1)))


def main() -> int:
    chrome = find_chrome()
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=str(WEB)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    results = []
    for page, budget in PAGES:
        print(f"— {page}")
        for r in run_page(chrome, server.server_port, page, budget):
            results.append(r)
            print(("✔ " if r["ok"] else "✘ ") + r["name"])
            if not r["ok"]:
                print("    " + r["error"].replace("\n", "\n    "))
    server.shutdown()
    failed = sum(not r["ok"] for r in results)
    print(f"\n{len(results) - failed} correctas, {failed} fallidas")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
