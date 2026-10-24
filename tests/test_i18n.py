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
