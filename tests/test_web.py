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


def test_analytics_only_on_the_published_site():
    """El recuento de visitas solo se activa en la dirección de la web (SITE_URL en build.py)."""
    config = (ROOT / "web" / "public" / "assets" / "js" / "config.js").read_text(encoding="utf-8")
    host = re.search(r'analytics: \{[^}]*host: "([^"]+)"', config).group(1)
    assert f"https://{host}" == build.SITE_URL


def _guide_folders():
    guides = build.load_guides()
    return [build.guides_folder(code, guides) for code in guides]


def test_sitemap_lists_every_indexed_page():
    """Cada página con dirección canónica está en sitemap.xml, y robots.txt apunta a él."""
    public = ROOT / "web" / "public"
    sitemap = (public / "sitemap.xml").read_text(encoding="utf-8")
    listed = set(re.findall(r"<loc>(.*?)</loc>", sitemap))
    canonical = set()
    for page in public.rglob("*.html"):
        m = re.search(r'<link rel="canonical" href="([^"]+)">', page.read_text(encoding="utf-8"))
        if m:
            canonical.add(m.group(1))
    assert canonical and canonical == listed
    assert f"Sitemap: {build.SITE_URL}/sitemap.xml" in (public / "robots.txt").read_text(encoding="utf-8")


def test_guides_are_linked_to_their_translations():
    """Una guía enlaza (hreflang) con sus traducciones, y solo con las que existen."""
    public = ROOT / "web" / "public"
    for folder in _guide_folders():
        for page in (public / folder).glob("*.html"):
            text = page.read_text(encoding="utf-8")
            for href in re.findall(r'hreflang="\w+" href="([^"]+)"', text):
                path = href.removeprefix(build.SITE_URL)
                target = public / (path.lstrip("/") + ("index.html" if path.endswith("/") else ".html"))
                assert target.exists(), f"{page.relative_to(public)} enlaza con {href}, que no existe"


def test_ads_only_in_the_guides():
    """Los anuncios solo pueden cargarse en las guías: la portada (con la demo) y la privacidad
    mantienen la política de seguridad estricta, y cada carpeta de guías tiene su regla propia."""
    public = ROOT / "web" / "public"
    folders = _guide_folders()
    for page in public.rglob("*.html"):
        rel = page.relative_to(public).as_posix()
        if not any(rel.startswith(f) for f in folders):
            assert "data-ads-client" not in page.read_text(encoding="utf-8"), rel
    headers = (public / "_headers").read_text(encoding="utf-8")
    strict = re.search(r"^/\*\n  Content-Security-Policy: (.*)$", headers, re.M).group(1)
    assert "unsafe-inline" not in strict and "https:;" not in strict
    for folder in folders:
        rule = re.search(rf"^/{re.escape(folder)}\*\n((?:  .*\n)+)", headers, re.M)
        assert rule, f"falta la regla /{folder}* en _headers"
        assert "! Content-Security-Policy" in rule.group(1)


def test_social_images_exist():
    """La imagen para redes sociales de cada idioma (web/i18n/social.py)."""
    for code, _, _ in build.LANGUAGES:
        assert (ROOT / "web" / "public" / "assets" / "img" / "social" / f"{code}.png").exists()
