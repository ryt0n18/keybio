"""Genera las páginas de la web en cada idioma a partir de las plantillas y los catálogos.

    web/i18n/templates/*.html   páginas con marcas {{clave}} en lugar de los textos
    web/i18n/<idioma>.json      catálogo de un idioma: textos de las páginas («page»), del
                                JavaScript («js») y frases para teclear en la demo («texts»)
    web/i18n/guides/            guías (artículos) de los idiomas que las tienen: <idioma>.json con
                                los textos de alrededor y <idioma>/<dirección>.html con cada guía
    web/public/                 resultado: el español en la raíz y el resto en /<idioma>/, más
                                robots.txt, sitemap.xml y, con anuncios, ads.txt

Marcas de las plantillas:

    {{clave}}         texto del catálogo tal cual (puede llevar HTML: lo escribimos nosotros)
    {{clave|attr}}    texto del catálogo escapado para ir dentro de un atributo
    {{@nombre}}       valor calculado (ruta a la raíz, menú de idiomas, enlaces hreflang...)

En las plantillas de las guías, {{guide.clave}} es un texto de guides/<idioma>.json.

Uso:  python web/i18n/build.py           escribe las páginas
      python web/i18n/build.py --check   solo comprueba que están al día (lo usan las pruebas)

Las páginas generadas se guardan en el repositorio: Cloudflare Pages publica public/ tal cual.
"""

from __future__ import annotations

import datetime
import html
import json
import math
import re
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parents[1]
I18N = WEB / "i18n"
GUIDES = I18N / "guides"
PUBLIC = WEB / "public"
sys.path.insert(0, str(WEB.parent))
from ksb import flags  # noqa: E402 (banderas compartidas con el programa)

# Dirección definitiva de la web: enlaces canónicos y hreflang, mapa del sitio y robots.txt.
SITE_URL = "https://keybio.pages.dev"
# Google Search Console: el valor de «content» de la etiqueta HTML de verificación. Vacío: no se pone.
GOOGLE_SITE_VERIFICATION = "lL4GGpe9A3IzhxJicUZHmfnYnKR1zXxR4ecwjxcmyhY"
# Google AdSense: el identificador de editor («ca-pub-…»). Vacío: sin anuncios. Con él, las guías
# cargan los anuncios, se genera ads.txt y la política de privacidad lo explica (docs/promocion.md).
# La portada nunca los lleva: ahí está la demo, donde se teclea.
ADSENSE_CLIENT = ""
AUTHOR = "Álvaro Ruiz"
AUTHOR_URL = "https://github.com/ryt0n18"
REPO_URL = "https://github.com/ryt0n18/keybio"
DEFAULT = "es"
# (código, nombre en su propio idioma, configuración regional para fechas y números)
LANGUAGES = [
    ("es", "Español", "es-ES"),
    ("en", "English", "en-GB"),
    ("ca", "Català", "ca-ES"),
    ("gl", "Galego", "gl-ES"),
    ("eu", "Euskara", "eu-ES"),
    ("fr", "Français", "fr-FR"),
    ("pt", "Português", "pt-PT"),
    ("de", "Deutsch", "de-DE"),
    ("it", "Italiano", "it-IT"),
]
# (plantilla, fichero publicado, ¿se indexa?)
PAGES = [("index.html", "index.html", True), ("privacidad.html", "privacidad.html", True),
         ("404.html", "404.html", False)]
# Textos de página que no aparecen en una plantilla porque los pone el propio build.py
COMPUTED_KEYS = {"common.language", "privacy.data.noTracking", "privacy.data.noTrackingAds", "privacy.ads.title",
                 "privacy.ads.text", "privacy.providers.google"}

MARK = re.compile(r"\{\{\s*(@?[\w.-]+)(\|attr)?\s*\}\}")
FRONT = re.compile(r"\A<!--\n(.*?)\n-->\n", re.S)
GUIDE_FIELDS = ("id", "slug", "title", "heading", "description", "published", "updated")
GUIDE_UI = ("folder", "nav", "title", "description", "heading", "lead", "updated",
            "minutes", "toc", "ctaTitle", "ctaText", "ctaButton", "more", "date", "breadcrumb", "by")
H2 = re.compile(r'<h2 id="([\w-]+)">(.*?)</h2>')
TAG = re.compile(r"<[^>]+>")


def flag(code: str) -> str:
    """Bandera del idioma (ksb/flags.py, las mismas que en el programa)."""
    return flags.svg(code, 'class="flag" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false"')


class BuildError(Exception):
    pass


def load_catalogs() -> dict[str, dict]:
    catalogs = {}
    for code, _, _ in LANGUAGES:
        path = I18N / f"{code}.json"
        try:
            catalogs[code] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise BuildError(f"{path.name}: {exc}") from exc
    return catalogs


def placeholders(text: str) -> set[str]:
    """Variables {nombre} de un texto del JavaScript (tienen que ser las mismas en cada idioma)."""
    return set(re.findall(r"\{(\w+)\}", text))


def check_catalogs(catalogs: dict[str, dict]) -> list[str]:
    """Problemas de los catálogos: claves que faltan o sobran, variables distintas, frases vacías."""
    problems = []
    ref = catalogs[DEFAULT]
    for code, cat in catalogs.items():
        for section in ("page", "js"):
            a, b = set(ref.get(section, {})), set(cat.get(section, {}))
            problems += [f"{code}: falta {section}.{k}" for k in sorted(a - b)]
            problems += [f"{code}: sobra {section}.{k}" for k in sorted(b - a)]
            for k in sorted(a & b):
                value = cat[section][k]
                if not isinstance(value, str) or not value.strip():
                    problems.append(f"{code}: {section}.{k} está vacío")
                elif section == "js" and placeholders(value) != placeholders(ref[section][k]):
                    problems.append(f"{code}: js.{k} no tiene las mismas variables que en {DEFAULT}")
        for kind, n in (("enroll", 6), ("verify", 4)):
            texts = cat.get("texts", {}).get(kind, [])
            if len(texts) != n or any(not 100 <= len(t) <= 170 for t in texts):
                problems.append(f"{code}: texts.{kind} debe tener {n} frases de 100 a 170 caracteres")
    return problems


# --- guías -----------------------------------------------------------------------------------------

def load_guides() -> dict[str, dict]:
    """Guías de los idiomas que las tienen: {idioma: {"ui": textos, "items": [guía, ...]}}.

    Cada guía empieza con una cabecera en un comentario HTML (id, slug, title, heading,
    description, published, updated). El «id» es el mismo en todas las traducciones de una guía y
    las enlaza entre sí (hreflang y menú de idiomas); «slug» es su dirección y el nombre del fichero.
    """
    guides = {}
    for code, _, _ in LANGUAGES:
        ui_path = GUIDES / f"{code}.json"
        if not ui_path.exists():
            continue
        try:
            ui = json.loads(ui_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise BuildError(f"guides/{ui_path.name}: {exc}") from exc
        missing = [k for k in GUIDE_UI if not str(ui.get(k, "")).strip()]
        if missing or len(ui.get("months", [])) != 12 or not ui.get("order"):
            raise BuildError(f"guides/{ui_path.name}: faltan {missing or ['months/order']}")
        items = {}
        for path in sorted((GUIDES / code).glob("*.html")):
            text = path.read_text(encoding="utf-8")
            m = FRONT.match(text)
            if not m:
                raise BuildError(f"guides/{code}/{path.name}: falta la cabecera <!-- … --> al principio")
            meta = dict(line.split(": ", 1) for line in m.group(1).splitlines() if line.strip())
            missing = [k for k in GUIDE_FIELDS if not meta.get(k, "").strip()]
            if missing:
                raise BuildError(f"guides/{code}/{path.name}: faltan {', '.join(missing)} en la cabecera")
            if meta["slug"] != path.stem:
                raise BuildError(f"guides/{code}/{path.name}: el slug tiene que ser el nombre del fichero")
            for k in ("published", "updated"):
                try:
                    datetime.date.fromisoformat(meta[k])
                except ValueError as exc:
                    raise BuildError(f"guides/{code}/{path.name}: {k} no es una fecha AAAA-MM-DD") from exc
            if meta["id"] in items:
                raise BuildError(f"guides/{code}: dos guías con el id {meta['id']}")
            meta["body"] = text[m.end():]
            items[meta["id"]] = meta
        if sorted(ui["order"]) != sorted(items):
            raise BuildError(f"guides/{code}.json: «order» tiene que listar todas las guías de {code}/")
        guides[code] = {"ui": ui, "items": [items[i] for i in ui["order"]]}
    return guides


def guides_folder(code: str, guides: dict) -> str:
    """Carpeta de las guías de un idioma, desde la raíz de la web ("guias/", "en/guides/")."""
    return ("" if code == DEFAULT else f"{code}/") + guides[code]["ui"]["folder"] + "/"


def guide_url(code: str, guides: dict, slug: str = "") -> str:
    """Dirección pública de una guía o, sin slug, del índice de guías ("/guias/", "/en/guides/x")."""
    return "/" + guides_folder(code, guides) + slug


def reading_minutes(body: str) -> int:
    return max(1, math.ceil(len(TAG.sub(" ", body).split()) / 220))


def nice_date(iso: str, ui: dict) -> str:
    d = datetime.date.fromisoformat(iso)
    return ui["date"].format(d=d.day, month=ui["months"][d.month - 1], y=d.year)


# --- piezas comunes --------------------------------------------------------------------------------

def url(code: str, page: str) -> str:
    """Dirección pública de una página en un idioma ("/", "/en/", "/en/privacidad"...): sin «.html»,
    como la sirve Cloudflare Pages (redirige «privacidad.html» a «privacidad»)."""
    folder = "/" if code == DEFAULT else f"/{code}/"
    return folder if page == "index.html" else folder + page.removesuffix(".html")


def relative(from_code: str, to_code: str, page: str) -> str:
    """Enlace relativo desde una página en ``from_code`` a ``page`` en ``to_code``."""
    up = "" if from_code == DEFAULT else "../"
    folder = "" if to_code == DEFAULT else f"{to_code}/"
    target = "" if page == "index.html" else page
    return (up + folder + target) or "./"


def lang_menu(code: str, cat: dict, targets: list[tuple[str, str]]) -> str:
    """Menú de idiomas con un enlace (relativo) a cada idioma de ``targets``: [(idioma, enlace)]."""
    names = {c: n for c, n, _ in LANGUAGES}
    items = []
    for other, href in targets:
        current = ' aria-current="page"' if other == code else ""
        items.append(f'<li><a href="{href}" hreflang="{other}" lang="{other}"'
                     f' data-lang="{other}"{current}>{flag(other)}{names[other]}</a></li>')
    label = html.escape(cat["page"]["common.language"], quote=True)
    return (f'<details class="lang-menu"><summary aria-label="{label}" title="{label}">{flag(code)}'
            f'<span>{code.upper()}</span></summary><ul>{"".join(items)}</ul></details>')


def alternates(urls: list[tuple[str, str]]) -> str:
    """Enlaces hreflang a cada traducción ([(idioma, dirección)]); x-default es la española o la primera."""
    links = [f'<link rel="alternate" hreflang="{c}" href="{SITE_URL}{u}">' for c, u in urls]
    default = dict(urls).get(DEFAULT, urls[0][1])
    links.append(f'<link rel="alternate" hreflang="x-default" href="{SITE_URL}{default}">')
    return "\n  ".join(links)


def social_image(code: str) -> str:
    return f"{SITE_URL}/assets/img/social/{code}.png"


def seo_tags(code: str, path: str) -> str:
    """Dirección canónica, imagen para redes sociales y verificaciones de Google."""
    tags = [f'<link rel="canonical" href="{SITE_URL}{path}">',
            f'<meta property="og:url" content="{SITE_URL}{path}">',
            '<meta property="og:site_name" content="KeyBio">',
            f'<meta property="og:image" content="{social_image(code)}">',
            '<meta property="og:image:width" content="1200">',
            '<meta property="og:image:height" content="630">',
            '<meta name="twitter:card" content="summary_large_image">']
    if GOOGLE_SITE_VERIFICATION:
        tags.append(f'<meta name="google-site-verification" content="{html.escape(GOOGLE_SITE_VERIFICATION, quote=True)}">')
    if ADSENSE_CLIENT:
        tags.append(f'<meta name="google-adsense-account" content="{html.escape(ADSENSE_CLIENT, quote=True)}">')
    return "\n  ".join(tags)


def json_ld(data: dict) -> str:
    """Datos estructurados para los buscadores (schema.org). Como el bloque de textos, no se
    ejecuta, así que la política de seguridad lo permite."""
    text = json.dumps({"@context": "https://schema.org", **data}, ensure_ascii=False,
                      separators=(",", ":")).replace("<", "\\u003c")
    return f'<script type="application/ld+json">{text}</script>'


def author() -> dict:
    return {"@type": "Person", "name": AUTHOR, "url": AUTHOR_URL}


def i18n_script(code: str, catalogs: dict[str, dict]) -> str:
    """Textos del JavaScript de este idioma (y la sugerencia de cambio en cada idioma), como JSON
    dentro de la página: no es un script ejecutable, así que la política de seguridad lo permite."""
    cat = catalogs[code]
    data = {
        "lang": code,
        "locale": next(loc for c, _, loc in LANGUAGES if c == code),
        "js": cat["js"],
        "texts": cat["texts"],
        "languages": [{"code": c, "name": n, "suggest": catalogs[c]["js"]["lang.suggest"],
                       "switch": catalogs[c]["js"]["lang.switch"], "dismiss": catalogs[c]["js"]["lang.dismiss"]}
                      for c, n, _ in LANGUAGES],
    }
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return f'<script type="application/json" id="i18n">{text}</script>'


def substitute(template: str, name: str, computed: dict[str, str], texts: dict[str, str]) -> str:
    def sub(m: re.Match) -> str:
        key, attr = m.group(1), m.group(2)
        if key.startswith("@"):
            if key not in computed:
                raise BuildError(f"{name}: valor calculado desconocido {key}")
            return computed[key]
        if key not in texts:
            raise BuildError(f"{name}: falta el texto {key}")
        value = texts[key]
        return html.escape(value, quote=True) if attr else value

    return MARK.sub(sub, template)


def common_values(code: str, catalogs: dict[str, dict]) -> dict[str, str]:
    return {
        "@lang": code,
        "@locale": next(loc for c, _, loc in LANGUAGES if c == code).replace("-", "_"),
        "@i18n": i18n_script(code, catalogs),
    }


# --- páginas fijas (portada, privacidad, 404) ------------------------------------------------------

def guides_nav(code: str, guides: dict) -> str:
    """Enlace a las guías en el menú de la portada y la privacidad (solo en idiomas con guías)."""
    if code not in guides:
        return ""
    return f'<a href="{guides[code]["ui"]["folder"]}/">{html.escape(guides[code]["ui"]["nav"])}</a>'


def guides_section(code: str, guides: dict) -> str:
    """Sección de la portada con las guías del idioma: enlaces internos para lectores y buscadores."""
    if code not in guides:
        return ""
    ui, folder = guides[code]["ui"], guides[code]["ui"]["folder"]
    cards = "".join(
        f'\n          <li class="card"><h3><a href="{folder}/{g["slug"]}.html">{g["heading"]}</a></h3>'
        f'<p>{g["description"]}</p></li>' for g in guides[code]["items"])
    return f"""
    <section id="guias" class="section alt">
      <div class="container">
        <div class="section-head">
          <p class="eyebrow">{ui["nav"]}</p>
          <h2>{ui["heading"]}</h2>
          <p class="lead">{ui["lead"]}</p>
        </div>
        <ul class="guide-cards">{cards}
        </ul>
      </div>
    </section>
"""


def privacy_values(cat: dict) -> dict[str, str]:
    """Con anuncios, la política de privacidad lo cuenta (textos privacy.ads.* del catálogo)."""
    page = cat["page"]
    if not ADSENSE_CLIENT:
        return {"@noTracking": page["privacy.data.noTracking"], "@adsSection": "", "@adsProvider": ""}
    return {
        "@noTracking": page["privacy.data.noTrackingAds"],
        "@adsSection": f'\n    <h2 id="anuncios">{page["privacy.ads.title"]}</h2>\n    <p>{page["privacy.ads.text"]}</p>\n',
        "@adsProvider": f'\n      <li>{page["privacy.providers.google"]}</li>',
    }


def render(template: str, code: str, page: str, indexed: bool, catalogs: dict[str, dict],
           guides: dict) -> str:
    cat = catalogs[code]
    targets = [(c, relative(code, c, page)) for c, _, _ in LANGUAGES]
    computed = {
        **common_values(code, catalogs),
        "@root": "" if code == DEFAULT else "../",
        "@home": url(code, "index.html"),
        "@langmenu": lang_menu(code, cat, targets),
        "@alternates": alternates([(c, url(c, page)) for c, _, _ in LANGUAGES]) if indexed else "",
        "@seo": seo_tags(code, url(code, page)) if indexed else "",
        "@guidesnav": guides_nav(code, guides),
        "@guides": guides_section(code, guides),
        "@jsonld": "",
        **privacy_values(cat),
    }
    if page == "index.html":
        computed["@jsonld"] = json_ld({
            "@type": "SoftwareApplication",
            "name": "KeyBio",
            "url": SITE_URL + url(code, page),
            "description": cat["page"]["index.meta.description"],
            "applicationCategory": "SecurityApplication",
            "operatingSystem": "Windows 10, Windows 11, macOS 11+, Linux",
            "inLanguage": code,
            "image": social_image(code),
            "downloadUrl": REPO_URL + "/releases/latest",
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"},
            "author": author(),
            "sameAs": [REPO_URL],
        })
    return substitute(template, page, computed, cat["page"])


# --- guías: índice y artículos ---------------------------------------------------------------------

def toc(body: str, ui: dict) -> str:
    entries = H2.findall(body)
    if len(entries) < 3:
        return ""
    items = "".join(f'<li><a href="#{anchor}">{TAG.sub("", text)}</a></li>' for anchor, text in entries)
    return f'<nav class="toc" aria-label="{html.escape(ui["toc"], quote=True)}"><p>{ui["toc"]}</p><ol>{items}</ol></nav>'


def guide_values(code: str, catalogs: dict[str, dict], guides: dict, guide: dict | None) -> dict[str, str]:
    """Valores calculados de una página de guías: el índice (guide=None) o una guía."""
    ui, cat = guides[code]["ui"], catalogs[code]
    if guide is None:
        langs = [c for c, _, _ in LANGUAGES if c in guides]
        hrefs = {c: guide_url(c, guides) for c in langs}
    else:
        langs = [c for c, _, _ in LANGUAGES if c in guides and any(g["id"] == guide["id"] for g in guides[c]["items"])]
        hrefs = {c: guide_url(c, guides, next(g["slug"] for g in guides[c]["items"] if g["id"] == guide["id"]))
                 for c in langs}
    depth = guides_folder(code, guides).count("/")
    root = "../" * depth
    # El menú de idiomas enlaza desde esta carpeta a la misma página en cada idioma que la tenga
    targets = [(c, root + hrefs[c].lstrip("/") + ("" if hrefs[c].endswith("/") else ".html")) for c in langs]
    home = SITE_URL + url(code, "index.html")
    index_url = guide_url(code, guides)
    others = [g for g in guides[code]["items"] if guide is None or g["id"] != guide["id"]]
    cards = "".join(
        f'<li class="card"><h3><a href="{g["slug"]}.html">{g["heading"]}</a></h3><p>{g["description"]}</p>'
        f'<p class="small muted">{ui["minutes"].format(n=reading_minutes(g["body"]))}</p></li>' for g in others)
    values = {
        **common_values(code, catalogs),
        "@root": root,
        "@langmenu": lang_menu(code, cat, targets),
        "@alternates": alternates([(c, hrefs[c]) for c in langs]),
        "@cards": f'<ul class="guide-list">{cards}</ul>' if cards else "",
        "@ads": f' data-ads-client="{html.escape(ADSENSE_CLIENT, quote=True)}"' if ADSENSE_CLIENT else "",
    }
    crumbs = [{"@type": "ListItem", "position": 1, "name": "KeyBio", "item": home},
              {"@type": "ListItem", "position": 2, "name": ui["nav"], "item": SITE_URL + index_url}]
    if guide is None:
        values.update({
            "@title": html.escape(ui["title"], quote=True),
            "@description": html.escape(ui["description"], quote=True),
            "@seo": seo_tags(code, index_url),
            "@jsonld": json_ld({"@type": "CollectionPage", "name": ui["title"], "url": SITE_URL + index_url,
                                "inLanguage": code, "description": ui["description"],
                                "breadcrumb": {"@type": "BreadcrumbList", "itemListElement": crumbs}}),
        })
        return values
    path = guide_url(code, guides, guide["slug"])
    crumbs.append({"@type": "ListItem", "position": 3, "name": guide["heading"], "item": SITE_URL + path})
    values.update({
        "@title": html.escape(guide["title"], quote=True),
        "@description": html.escape(guide["description"], quote=True),
        "@heading": guide["heading"],
        "@seo": seo_tags(code, path),
        "@published": guide["published"],
        "@updated": guide["updated"],
        "@updatedText": nice_date(guide["updated"], ui),
        "@minutes": ui["minutes"].format(n=reading_minutes(guide["body"])),
        # El índice va después de la entradilla (el primer párrafo)
        "@article": guide["body"].strip().replace("</p>", "</p>\n" + toc(guide["body"], ui), 1),
        "@jsonld": json_ld({"@graph": [
            {"@type": "TechArticle", "headline": guide["heading"], "description": guide["description"],
             "inLanguage": code, "datePublished": guide["published"], "dateModified": guide["updated"],
             "author": author(), "publisher": author(), "image": social_image(code),
             "mainEntityOfPage": SITE_URL + path, "about": {"@type": "SoftwareApplication", "name": "KeyBio", "url": home}},
            {"@type": "BreadcrumbList", "itemListElement": crumbs},
        ]}),
    })
    return values


def render_guides(catalogs: dict[str, dict], guides: dict) -> dict[Path, str]:
    out = {}
    index_tpl = (I18N / "templates" / "guides.html").read_text(encoding="utf-8")
    guide_tpl = (I18N / "templates" / "guide.html").read_text(encoding="utf-8")
    for code, data in guides.items():
        texts = {**catalogs[code]["page"], **{f"guide.{k}": v for k, v in data["ui"].items() if isinstance(v, str)}}
        folder = PUBLIC / guides_folder(code, guides)
        out[folder / "index.html"] = substitute(index_tpl, f"guides.html ({code})",
                                                guide_values(code, catalogs, guides, None), texts)
        for g in data["items"]:
            out[folder / f"{g['slug']}.html"] = substitute(guide_tpl, f"guide.html ({code}/{g['slug']})",
                                                           guide_values(code, catalogs, guides, g), texts)
    return out


# --- robots.txt, sitemap.xml y ads.txt -------------------------------------------------------------

def sitemap(guides: dict) -> str:
    entries = [(url(c, p), None) for _, p, indexed in PAGES if indexed for c, _, _ in LANGUAGES]
    for code, data in guides.items():
        entries.append((guide_url(code, guides), max(g["updated"] for g in data["items"])))
        entries += [(guide_url(code, guides, g["slug"]), g["updated"]) for g in data["items"]]
    rows = "".join(f"  <url><loc>{SITE_URL}{u}</loc>" + (f"<lastmod>{d}</lastmod>" if d else "") + "</url>\n"
                   for u, d in entries)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + rows + "</urlset>\n")


def robots() -> str:
    return ("# Generado por web/i18n/build.py\nUser-agent: *\nDisallow: /api/\nAllow: /\n\n"
            f"Sitemap: {SITE_URL}/sitemap.xml\n")


def ads_txt() -> str:
    """Vendedores autorizados de los anuncios (lo comprueba AdSense en la raíz del dominio)."""
    return f"google.com, {ADSENSE_CLIENT.removeprefix('ca-')}, DIRECT, f08c47fec0942fa0\n"


def build() -> dict[Path, str]:
    """Todas las páginas: {ruta de salida: contenido}."""
    catalogs = load_catalogs()
    problems = check_catalogs(catalogs)
    if problems:
        raise BuildError("\n".join(problems))
    guides = load_guides()
    used = set(COMPUTED_KEYS)
    out = {}
    for template_name, published, indexed in PAGES:
        template = (I18N / "templates" / template_name).read_text(encoding="utf-8")
        used |= {m.group(1) for m in MARK.finditer(template) if not m.group(1).startswith("@")}
        for code, _, _ in LANGUAGES:
            folder = PUBLIC if code == DEFAULT else PUBLIC / code
            out[folder / published] = render(template, code, published, indexed, catalogs, guides)
    for name in ("guides.html", "guide.html"):
        used |= {m.group(1) for m in MARK.finditer((I18N / "templates" / name).read_text(encoding="utf-8"))}
    unused = set(catalogs[DEFAULT]["page"]) - used
    if unused:
        raise BuildError("Textos de página que no usa ninguna plantilla: " + ", ".join(sorted(unused)))
    out.update(render_guides(catalogs, guides))
    out[PUBLIC / "sitemap.xml"] = sitemap(guides)
    out[PUBLIC / "robots.txt"] = robots()
    if ADSENSE_CLIENT:
        out[PUBLIC / "ads.txt"] = ads_txt()
    return out


def stale(pages: dict[Path, str]) -> list[Path]:
    return [p for p, text in pages.items() if not p.exists() or p.read_text(encoding="utf-8") != text]


def main(argv: list[str]) -> int:
    try:
        pages = build()
    except BuildError as exc:
        print(exc, file=sys.stderr)
        return 1
    changed = stale(pages)
    if "--check" in argv:
        for p in changed:
            print(f"Desactualizada: {p.relative_to(WEB)} (ejecuta python web/i18n/build.py)", file=sys.stderr)
        return 1 if changed else 0
    for p in changed:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(pages[p], encoding="utf-8")
    print(f"{len(pages)} páginas, {len(changed)} actualizadas")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
