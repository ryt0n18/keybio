"""Traducciones: catálogos completos, plurales, elección de idioma, textos para escribir en cada
idioma y la ventana principal funcionando en todos."""

import importlib.util
import os
from pathlib import Path

import pytest

from ksb import i18n, texts
from ksb.gui import keyboard
from ksb.service import BiometricService
from ksb.storage import Storage

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def language():
    """Cambia el idioma durante la prueba y vuelve al español al terminar."""
    yield i18n.set_language
    i18n.set_language("es")


def _tool():
    spec = importlib.util.spec_from_file_location("i18n_tool", ROOT / "tools" / "i18n.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_catalogs_complete():
    tool = _tool()
    assert tool.check() == []
    codes = {p.stem for p in (ROOT / "ksb" / "locale").glob("*.json")}
    assert codes == set(i18n.LANGUAGES) - {i18n.SOURCE}


def test_translate_and_plurals(language):
    language("de")
    assert i18n._("Volver") == "Zurück"
    assert i18n._n("{n} muestra", "{n} muestras", 1) == "1 Probe"
    assert i18n._n("{n} muestra", "{n} muestras", 3) == "3 Proben"
    language("fr")
    assert i18n._n("{n} muestra", "{n} muestras", 0) == "0 échantillon"   # en francés el 0 va en singular
    language("es")
    assert i18n._n("{n} muestra", "{n} muestras", 0) == "0 muestras"
    assert i18n._("Texto que no está en ningún catálogo") == "Texto que no está en ningún catálogo"


def test_resolve_language(monkeypatch):
    for var in (i18n.ENV, "LANGUAGE", "LC_ALL", "LANG"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(i18n.locale, "getlocale", lambda: (None, None))
    assert i18n.resolve("fr") == "fr"
    assert i18n.resolve("auto", "de_DE") == "de"
    assert i18n.resolve("auto", "pt-BR") == "pt"
    assert i18n.resolve("auto", "ja_JP") == i18n.FALLBACK
    monkeypatch.setenv(i18n.ENV, "eu")
    assert i18n.resolve("fr", "de_DE") == "eu"


def test_texts_in_every_language():
    assert set(texts.POOLS) == set(i18n.LANGUAGES)
    ids = [k for kinds in texts.POOLS.values() for pool in kinds.values() for k in pool]
    assert len(ids) == len(set(ids))
    for code, kinds in texts.POOLS.items():
        assert len(kinds["enroll"]) >= 5 and len(kinds["verify"]) >= 3 and len(kinds["access"]) >= 6, code
        assert not set(kinds["enroll"]) & set(kinds["verify"])
        # con menos de ~90 pulsaciones se rechaza a bastantes usuarios legítimos (ver texts.ACCESS_PHRASES)
        assert all(len(t) >= 90 for t in kinds["access"].values()), code
        assert all(len(t) >= 230 for t in kinds["enroll"].values()), code
        # todo carácter tiene su tecla en el teclado en pantalla de ese idioma
        layout = keyboard.LAYOUTS[i18n.KEYBOARDS[code]]
        for pool in kinds.values():
            for t in pool.values():
                assert all(keyboard.key_for(ch, i18n.KEYBOARDS[code]) in layout["keys"] | {"space"} for ch in t)


def test_auto_settings_follow_language(tmp_path, language):
    language("fr")
    svc = BiometricService(Storage(tmp_path))
    assert svc.text_language == "fr" and svc.keyboard_layout == "fr"
    assert texts.pick_access_phrase(language=svc.text_language)[0].startswith("FR-A")
    svc.settings.update(text_language="de", keyboard_layout="it")
    assert svc.text_language == "de" and svc.keyboard_layout == "it"


@pytest.mark.parametrize("code", list(i18n.LANGUAGES))
def test_window_in_every_language(code, tmp_path, language):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtWidgets import QApplication

    from ksb.gui.app import NAV, MainWindow

    QApplication.instance() or QApplication([])
    language(code)
    win = MainWindow(BiometricService(Storage(tmp_path)))
    try:
        for row in range(win.nav.count()):
            win.nav.setCurrentRow(row)
            assert win.pages.currentIndex() == row
        labels = [win.nav.item(i).text() for i in range(win.nav.count())]
        assert labels == [i18n._(title) for title, _icon in NAV]
        if code != i18n.SOURCE:
            assert labels != [title for title, _icon in NAV]
    finally:
        win.close()


def _own_scope_names(fn):
    """Nombres asignados en el ámbito propio de una función (sin comprensiones ni funciones anidadas)."""
    import ast
    names = {a.arg for a in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs}
    names |= {a.arg for a in (fn.args.vararg, fn.args.kwarg) if a}
    stack = list(ast.iter_child_nodes(fn))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef,
                             ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            continue
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        stack.extend(ast.iter_child_nodes(node))
    return names


def test_translation_function_never_shadowed():
    """Si una función asigna algo a «_» (p. ej. ``w, _, _ = ...``), su _() deja de traducir y falla
    («'int' object is not callable» al pasar el ratón por el ritmo de escritura, en la 2.1.1)."""
    import ast
    bad = []
    for path in (ROOT / "ksb").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            calls = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "_"
                        for n in ast.walk(fn))
            if calls and "_" in _own_scope_names(fn):
                bad.append(f"{path.relative_to(ROOT)}:{fn.lineno} {fn.name}")
    assert not bad, bad


def test_rhythm_chart_hover(language):
    """Pasar el ratón por el gráfico de ritmo muestra el intervalo sin errores, en cualquier idioma."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication

    from ksb.gui.charts import RhythmChart

    QApplication.instance() or QApplication([])
    for code in ("es", "de"):
        language(code)
        chart = RhythmChart()
        chart.resize(600, 200)
        chart.set_data([120, 180, 90, 2400, 150, 130])
        chart.show()
        pos = QPointF(300, 100)
        event = QMouseEvent(QEvent.Type.MouseMove, pos, chart.mapToGlobal(pos), Qt.MouseButton.NoButton,
                            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        chart.mouseMoveEvent(event)
        assert chart._hover is not None
        chart.close()
