"""Textos traducibles del programa: extracción y comprobación de los catálogos (ksb/locale).

Uso:  python tools/i18n.py check     problemas de cada catálogo (código de salida 1 si hay)
      python tools/i18n.py sync      añade a los catálogos los textos nuevos (con valor null)
                                     y quita los que ya no están en el código
      python tools/i18n.py stats     cuántos textos tiene traducidos cada idioma

Un texto traducible es el primer argumento de _() o N_(), o los dos primeros de _n(), siempre
un literal (no un f-string: las variables van como {nombre} y se pasan a _()). _(variable) solo
traduce un texto que ya se marcó con N_() donde se definió.
"""

from __future__ import annotations

import ast
import json
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ksb.i18n import LANGUAGES, SOURCE, locale_dir  # noqa: E402

CALLS = {"_": 1, "N_": 1, "_n": 2}


class ExtractError(Exception):
    pass


def extract(root: Path = ROOT / "ksb") -> dict[str, str | None]:
    """{texto: plural o None} en el orden en que aparecen en el código."""
    found: dict[str, str | None] = {}
    errors = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in CALLS):
                continue
            n = CALLS[node.func.id]
            args = node.args[:n]
            where = f"{path.relative_to(ROOT)}:{node.lineno}"
            if len(args) < n or not all(isinstance(a, ast.Constant) and isinstance(a.value, str) for a in args):
                if node.func.id == "_":   # _(variable): traduce un texto marcado antes con N_()
                    continue
                errors.append(f"{where}: {node.func.id}() necesita {'un literal' if n == 1 else 'dos literales'}")
                continue
            text = args[0].value
            plural = args[1].value if n == 2 else None
            if text in found and found[text] != plural:
                errors.append(f"{where}: «{text[:40]}» se usa con y sin plural")
            found.setdefault(text, plural)
    if errors:
        raise ExtractError("\n".join(errors))
    return found


def fields(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def load(code: str) -> dict:
    path = locale_dir() / f"{code}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def check_catalog(code: str, texts: dict[str, str | None], catalog: dict) -> list[str]:
    problems = []
    for text, plural in texts.items():
        value = catalog.get(text)
        short = text if len(text) <= 60 else text[:57] + "…"
        if value is None:
            problems.append(f"{code}: falta «{short}»")
            continue
        wanted = fields(text) | (fields(plural) if plural else set())
        if plural is None:
            if not isinstance(value, str) or not value.strip():
                problems.append(f"{code}: «{short}» debería ser un texto")
            elif fields(value) - wanted or (fields(text) - fields(value)):
                problems.append(f"{code}: «{short}» no tiene las mismas variables")
        else:
            if not isinstance(value, dict) or set(value) != {"one", "other"}:
                problems.append(f"{code}: «{short}» debería ser {{\"one\": …, \"other\": …}}")
            elif any(fields(v) - wanted - {"n"} for v in value.values()):
                problems.append(f"{code}: «{short}» usa variables que no existen")
    for text in catalog:
        if text not in texts:
            problems.append(f"{code}: sobra «{text[:60]}» (ya no está en el código)")
    return problems


def check() -> list[str]:
    texts = extract()
    out = []
    for code in LANGUAGES:
        if code != SOURCE:
            out += check_catalog(code, texts, load(code))
    return out


def sync() -> None:
    texts = extract()
    for code in LANGUAGES:
        if code == SOURCE:
            continue
        old = load(code)
        new = {t: old.get(t) for t in texts}
        path = locale_dir() / f"{code}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(new, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        missing = sum(v is None for v in new.values())
        print(f"{code}: {len(new)} textos, {missing} sin traducir, {len(set(old) - set(new))} quitados")


def stats() -> None:
    texts = extract()
    print(f"{len(texts)} textos en el código")
    for code in LANGUAGES:
        if code != SOURCE:
            cat = load(code)
            done = sum(cat.get(t) is not None for t in texts)
            print(f"  {code}: {done}/{len(texts)}")


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "check"
    try:
        if cmd == "sync":
            sync()
        elif cmd == "stats":
            stats()
        else:
            problems = check()
            print("\n".join(problems[:200]) or "Catálogos completos")
            if len(problems) > 200:
                print(f"… y {len(problems) - 200} más")
            return 1 if problems else 0
    except ExtractError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

