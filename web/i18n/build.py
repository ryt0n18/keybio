"""Genera las páginas de la web en cada idioma a partir de las plantillas y los catálogos.

    web/i18n/templates/*.html   páginas con marcas {{clave}} en lugar de los textos
    web/i18n/<idioma>.json      catálogo de un idioma: textos de las páginas («page»), del
                                JavaScript («js») y frases para teclear en la demo («texts»)
    web/public/                 resultado: el español en la raíz y el resto en /<idioma>/

Marcas de las plantillas:

    {{clave}}         texto del catálogo tal cual (puede llevar HTML: lo escribimos nosotros)
    {{clave|attr}}    texto del catálogo escapado para ir dentro de un atributo
    {{@nombre}}       valor calculado (ruta a la raíz, menú de idiomas, enlaces hreflang...)

Uso:  python web/i18n/build.py           escribe las páginas
      python web/i18n/build.py --check   solo comprueba que están al día (lo usan las pruebas)

Las páginas generadas se guardan en el repositorio: Cloudflare Pages publica public/ tal cual.
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parents[1]
I18N = WEB / "i18n"
PUBLIC = WEB / "public"
sys.path.insert(0, str(WEB.parent))
from ksb import flags  # noqa: E402 (banderas compartidas con el programa)

# Dirección definitiva de la web: solo se usa en los enlaces hreflang para los buscadores.
SITE_URL = "https://keybio.pages.dev"
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

MARK = re.compile(r"\{\{\s*(@?[\w.-]+)(\|attr)?\s*\}\}")
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


def lang_menu(code: str, page: str, cat: dict) -> str:
    items = []
    for other, name, _ in LANGUAGES:
        current = ' aria-current="page"' if other == code else ""
        items.append(f'<li><a href="{relative(code, other, page)}" hreflang="{other}" lang="{other}"'
                     f' data-lang="{other}"{current}>{flag(other)}{name}</a></li>')
    label = html.escape(cat["page"]["common.language"], quote=True)
    return (f'<details class="lang-menu"><summary aria-label="{label}" title="{label}">{flag(code)}'
            f'<span>{code.upper()}</span></summary><ul>{"".join(items)}</ul></details>')


def alternates(page: str) -> str:
    links = [f'<link rel="alternate" hreflang="{c}" href="{SITE_URL}{url(c, page)}">' for c, _, _ in LANGUAGES]
    links.append(f'<link rel="alternate" hreflang="x-default" href="{SITE_URL}{url(DEFAULT, page)}">')
    return "\n  ".join(links)


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


def render(template: str, code: str, page: str, indexed: bool, catalogs: dict[str, dict]) -> str:
    cat = catalogs[code]
    computed = {
        "@lang": code,
        "@locale": next(loc for c, _, loc in LANGUAGES if c == code).replace("-", "_"),
        "@root": "" if code == DEFAULT else "../",
        "@home": url(code, "index.html"),
        "@langmenu": lang_menu(code, page, cat),
        "@alternates": alternates(page) if indexed else "",
        "@i18n": i18n_script(code, catalogs),
    }

    def sub(m: re.Match) -> str:
        key, attr = m.group(1), m.group(2)
        if key.startswith("@"):
            if key not in computed:
                raise BuildError(f"{page}: valor calculado desconocido {key}")
            return computed[key]
        if key not in cat["page"]:
            raise BuildError(f"{page}: falta page.{key} en {code}.json")
        value = cat["page"][key]
        return html.escape(value, quote=True) if attr else value

    return MARK.sub(sub, template)


def build() -> dict[Path, str]:
    """Todas las páginas: {ruta de salida: contenido}."""
    catalogs = load_catalogs()
    problems = check_catalogs(catalogs)
    if problems:
        raise BuildError("\n".join(problems))
    used = {"common.language"}   # lo usa el menú de idiomas (lang_menu), no una plantilla
    out = {}
    for template_name, published, indexed in PAGES:
        template = (I18N / "templates" / template_name).read_text(encoding="utf-8")
        used |= {m.group(1) for m in MARK.finditer(template) if not m.group(1).startswith("@")}
        for code, _, _ in LANGUAGES:
            folder = PUBLIC if code == DEFAULT else PUBLIC / code
            out[folder / published] = render(template, code, published, indexed, catalogs)
    unused = set(catalogs[DEFAULT]["page"]) - used
    if unused:
        raise BuildError("Textos de página que no usa ninguna plantilla: " + ", ".join(sorted(unused)))
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
