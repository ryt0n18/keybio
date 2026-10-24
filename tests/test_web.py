"""La web en varios idiomas: catálogos completos y páginas generadas al día (web/i18n/build.py)."""

import importlib.util
import json
import re
from pathlib import Path

from ksb import i18n

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("web_i18n_build", ROOT / "web" / "i18n" / "build.py")
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)


def test_catalogs_are_complete():
    assert build.check_catalogs(build.load_catalogs()) == []


def test_generated_pages_are_up_to_date():
    stale = [str(p.relative_to(ROOT)) for p in build.stale(build.build())]
    assert not stale, f"Páginas desactualizadas (ejecuta python web/i18n/build.py): {stale}"


def test_each_page_carries_its_own_language():
    for code, _, _ in build.LANGUAGES:
        folder = ROOT / "web" / "public" / ("" if code == build.DEFAULT else code)
        page = (folder / "index.html").read_text(encoding="utf-8")
        assert f'<html lang="{code}">' in page
        raw = re.search(r'<script type="application/json" id="i18n">(.*?)</script>', page, re.S).group(1)
        assert "<" not in raw   # escapado: un texto con «</script>» no puede cerrar el bloque antes de tiempo
        data = json.loads(raw)
        assert data["lang"] == code and len(data["languages"]) == len(build.LANGUAGES)


def test_program_languages_shown_on_the_web_exist():
    config = (ROOT / "web" / "public" / "assets" / "js" / "config.js").read_text(encoding="utf-8")
    codes = re.findall(r'"(\w+)"', re.search(r"programLanguages: \[(.*?)\]", config).group(1))
    assert codes and set(codes) <= {c for c, _, _ in build.LANGUAGES}
    assert codes == list(i18n.LANGUAGES)   # los mismos que el programa, en el mismo orden
