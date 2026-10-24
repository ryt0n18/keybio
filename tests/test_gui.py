"""Prueba de extremo a extremo de la interfaz, enviando eventos de teclado reales a Qt."""

import os
import random
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from ksb.gui import theme  # noqa: E402
from ksb.gui.app import MainWindow  # noqa: E402
from ksb.service import BiometricService  # noqa: E402
from ksb.storage import Storage  # noqa: E402


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    theme.apply(a, "light", 1.0)
    return a


def _key_for(ch: str) -> int:
    if ch == " ":
        return Qt.Key.Key_Space.value
    base = ch.upper()
    return ord(base) if base.isascii() else 0


def type_text(app, widget, text, rng, speed=1.0, dwell=0.07):
    """Teclea `text` en `widget` con pulsación/liberación y tiempos reales."""
    for i, ch in enumerate(text):
        key = _key_for(ch)
        # como un teclado real: scancode (Linux/Windows) y tecla virtual (macOS, 56 = shift izquierdo)
        scancode = 100 + (ord(ch.lower()) % 120)
        shift = ch.isupper()
        if shift:
            widget.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Shift.value,
                                           Qt.KeyboardModifier.ShiftModifier, 50, 56, 0, "", False, 1))
            time.sleep(0.03)
        mods = Qt.KeyboardModifier.ShiftModifier if shift else Qt.KeyboardModifier.NoModifier
        widget.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, key, mods, scancode, scancode, 0, ch, False, 1))
        app.processEvents()
        time.sleep(dwell * speed * rng.uniform(0.55, 1.6))
        widget.keyReleaseEvent(QKeyEvent(QEvent.Type.KeyRelease, key, mods, scancode, scancode, 0, ch, False, 1))
        if shift:
            widget.keyReleaseEvent(QKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_Shift.value,
                                             Qt.KeyboardModifier.NoModifier, 50, 56, 0, "", False, 1))
        time.sleep(0.03 * speed * rng.uniform(0.3, 2.8))
        app.processEvents()


def wait(app, seconds):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def test_enroll_and_identify(app, tmp_path, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warnings.append(a))
    import ksb.gui.pages.enroll as enroll_mod
    import ksb.gui.pages.identify as identify_mod
    from ksb import texts
    # textos recortados para que la prueba sea rápida
    monkeypatch.setattr(enroll_mod, "pick_enroll_texts",
                        lambda n, ex=None, lang="es": [(k, t[:120]) for k, t in texts.pick_enroll_texts(n, ex, lang)])
    monkeypatch.setattr(identify_mod, "pick_verify_text",
                        lambda avoid=None, lang="es": (lambda kt: (kt[0], kt[1][:120]))(texts.pick_verify_text(avoid, lang)))
    svc = BiometricService(Storage(tmp_path))
    svc.settings["enroll_samples"] = 2
    win = MainWindow(svc)
    win.show()
    rng = random.Random(0)

    page = win.enroll
    page.name_edit.setText("Prueba")
    infos = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: infos.append(a))
    page._start_new()
    assert page.stack.currentIndex() == 0 and infos   # sin el permiso de la persona no se empieza
    page.consent.setChecked(True)
    page._start_new()
    assert page.stack.currentIndex() == 1
    for i in range(2):
        type_text(app, page.panel.input, page.panel.target, rng)
        wait(app, 0.6)
        assert not warnings, warnings
        assert page.stack.currentIndex() == 2
        page.next_btn.click()
    assert page.stack.currentIndex() == 3, "el registro debería haber terminado"
    user = svc.storage.find_by_name("Prueba")
    assert user and len(user.samples) == 2
    s = user.samples[0]
    assert s.accuracy == 1.0
    assert sum(k.label == "shift_l" for k in s.keystrokes) >= 1
    dwell = [k.dwell for k in s.keystrokes if k.kind == "char"]
    assert all(d and 30 < d < 300 for d in dwell)

    # identificación
    win.nav.setCurrentRow(2)
    ident = win.identify
    ident.start()
    type_text(app, ident.panel.input, ident.panel.target, rng)
    wait(app, 0.6)
    assert ident.stack.currentIndex() == 2
    assert ident.result is not None and ident.result.candidates
    assert ident.ranking.rowCount() == 1
    win.nav.setCurrentRow(3)
    assert win.users.table.rowCount() == 1
    win.nav.setCurrentRow(4)
    assert win.history.table.rowCount() == 1

    # verificación 1:1 con el mismo usuario
    ident.reset()
    ident.mode_sel.group.button(1).click()
    ident.refresh()
    assert ident.claim_combo.currentText() == "Prueba"
    ident.start()
    type_text(app, ident.panel.input, ident.panel.target, rng)
    wait(app, 0.6)
    assert ident.stack.currentIndex() == 2 and ident.claimed is not None
    assert svc.history()[0]["mode"] == "verify"

    # panel de control con la evaluación en segundo plano
    from PySide6.QtCore import QThreadPool
    win.nav.setCurrentRow(0)
    QThreadPool.globalInstance().waitForDone(10000)
    wait(app, 0.3)
    assert win.dashboard.k_users.value.text() == "1"
    assert win.dashboard.k_checks.value.text() == "2"

    # cambio de tema en caliente
    from ksb.gui import theme as th
    before = th.MODE
    win.toggle_theme()
    assert th.MODE != before
    win.toggle_theme()
    win.nav.setCurrentRow(6)
    win.close()


def test_paste_and_navigation_blocked(app, tmp_path):
    svc = BiometricService(Storage(tmp_path))
    win = MainWindow(svc)
    win.nav.setCurrentRow(1)
    page = win.enroll
    page.name_edit.setText("X")
    page.consent.setChecked(True)
    page._start_new()
    inp = page.panel.input
    from PySide6.QtCore import QMimeData
    md = QMimeData()
    md.setText("texto pegado")
    inp.insertFromMimeData(md)
    inp.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Left.value,
                                Qt.KeyboardModifier.NoModifier, 113, 0, 0, "", False, 1))
    inp.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_V.value,
                                Qt.KeyboardModifier.ControlModifier, 55, 0, 0, "\x16", False, 1))
    assert inp.toPlainText() == ""
    assert page.panel.recorder.blocked_keys == 3
    # tecla muerta + vocal = vocal acentuada
    inp.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Dead_Acute.value,
                                Qt.KeyboardModifier.NoModifier, 34, 0, 0, "", False, 1))
    inp.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A.value,
                                Qt.KeyboardModifier.NoModifier, 38, 0, 0, "a", False, 1))
    assert inp.toPlainText() == "á"
    win.close()


def _seed_users(svc, n=3, samples=3):
    from ksb.texts import ENROLL_TEXTS
    from tests.simulate import SyntheticTypist
    rng = random.Random(9)
    typists = []
    for u in range(n):
        t = SyntheticTypist(900 + u)
        svc.create_user(f"u{u}", [t.type_text(x, rng, text_id=k).build_sample()
                                  for k, x in list(ENROLL_TEXTS.items())[u:u + samples]])
        typists.append(t)
    return typists


def test_free_text_live_identification_and_reports(app, tmp_path, monkeypatch):
    from PySide6.QtCore import QThreadPool
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    svc = BiometricService(Storage(tmp_path))
    _seed_users(svc, 2)
    win = MainWindow(svc)
    win.show()
    win.nav.setCurrentRow(2)
    ident = win.identify
    ident.free_check.setChecked(True)
    ident.start()
    assert ident.panel.free and ident.panel.finish_btn.isVisible()
    rng = random.Random(3)
    text = "hoy he salido a pasear por el parque y luego he comido con unos amigos en casa " * 4
    type_text(app, ident.panel.input, text[:300], rng, speed=0.6)
    for _ in range(30):                       # deja que llegue alguna estimación en directo
        wait(app, 0.1)
        ident._live_tick()
        QThreadPool.globalInstance().waitForDone(3000)
    wait(app, 0.2)
    assert "pulsaciones" in ident.live_text.text()
    ident.panel.finish_btn.click()
    wait(app, 0.6)
    assert ident.stack.currentIndex() == 2 and ident.sample.free
    entry = svc.history()[0]
    assert entry["free"] is True
    # informes PDF
    from ksb.gui.report import result_report, user_report
    result_report(svc, ident.features, ident.result, ident.shown, "prueba", "detalle", tmp_path / "r.pdf")
    user_report(svc, svc.users()[0], tmp_path / "u.pdf")
    assert (tmp_path / "r.pdf").stat().st_size > 10_000 and (tmp_path / "u.pdf").stat().st_size > 10_000
    win.close()


def test_settings_calibration_and_protection(app, tmp_path, monkeypatch):
    from PySide6.QtCore import QThreadPool
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    svc = BiometricService(Storage(tmp_path))
    _seed_users(svc, 3, 3)
    win = MainWindow(svc)
    win.nav.setCurrentRow(6)
    page = win.settings
    page._calibrate()
    QThreadPool.globalInstance().waitForDone(30000)
    wait(app, 0.3)
    assert page._cal is not None and page._cal.enough and page.cal_apply.isEnabled()
    page._apply_calibration()
    assert svc.settings["sensitivity"] == "auto" and svc.sensitivity_label.startswith("automática")
    # protección: se cifra y otra instancia necesita la contraseña
    from ksb import crypto
    if crypto.AVAILABLE:
        import ksb.gui.pages.settings as settings_mod

        class FakeDialog:
            def __init__(self, *a, **k):
                self.password = "contraseña-segura"

            def exec(self):
                return True

            def setWindowIcon(self, _icon):
                pass
        monkeypatch.setattr(settings_mod, "PasswordDialog", FakeDialog)
        page._enable_protection()
        assert svc.storage.protected and Storage(tmp_path).locked
        from ksb.gui.app import unlock
        import ksb.gui.app as app_mod
        monkeypatch.setattr(app_mod, "PasswordDialog", FakeDialog)
        other = BiometricService(Storage(tmp_path))
        assert unlock(other) and len(other.users()) == 3
        page._disable_protection()
        assert not svc.storage.protected
    win.nav.setCurrentRow(0)
    QThreadPool.globalInstance().waitForDone(30000)
    wait(app, 0.3)
    assert win.dashboard.tips_card.isVisibleTo(win.dashboard)
    win.close()


def test_physical_keys_on_each_system(app):
    from ksb.gui.typing_widget import classify_key

    def ev(key, text="", sc=0, vk=0, mods=Qt.KeyboardModifier.NoModifier):
        return QKeyEvent(QEvent.Type.KeyPress, key, mods, sc, vk, 0, text)

    # Linux/Windows: identificación por scancode
    assert classify_key(ev(Qt.Key.Key_Shift, sc=50), mac=False)[1:] == ("shift_l", "mod")
    assert classify_key(ev(Qt.Key.Key_Shift, sc=62), mac=False)[1:] == ("shift_r", "mod")
    # macOS: Qt da el scancode 1 a todas las teclas; se usa la tecla virtual
    a = classify_key(ev(Qt.Key.Key_A, "a", sc=1, vk=0), mac=True)
    s = classify_key(ev(Qt.Key.Key_S, "s", sc=1, vk=1), mac=True)
    assert a[0] != s[0] and a[1:] == ("a", "char")
    assert classify_key(ev(Qt.Key.Key_Shift, sc=1, vk=56), mac=True)[1] == "shift_l"
    assert classify_key(ev(Qt.Key.Key_Shift, sc=1, vk=60), mac=True)[1] == "shift_r"
    # tecla muerta sin texto (tilde) en macOS; una flecha sigue siendo una tecla bloqueada
    assert classify_key(ev(Qt.Key.Key_Apostrophe, "", sc=1, vk=39), mac=True)[2] == "dead"
    assert classify_key(ev(Qt.Key.Key_Left, "", sc=1, vk=123), mac=True)[2] == "other"


def test_identify_stops_early_when_clear(app, tmp_path, monkeypatch):
    import ksb.gui.pages.identify as identify_mod
    from ksb import matcher
    from ksb.texts import ENROLL_TEXTS
    from tests.simulate import SyntheticTypist
    rng = random.Random(2)
    svc = BiometricService(Storage(tmp_path))
    t = SyntheticTypist(40)
    svc.create_user("Ana", [t.type_text(x, rng, text_id=k).build_sample() for k, x in list(ENROLL_TEXTS.items())[:3]])
    # la regla siempre acepta (respetando el mínimo de pulsaciones): se prueba el recorrido de la interfaz
    monkeypatch.setattr(identify_mod, "early_decision",
                        lambda res, n, claimed=None: "accept" if n >= matcher.EARLY_MIN_KEYS else None)
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warnings.append(a))
    win = MainWindow(svc)
    win.show()
    win.nav.setCurrentRow(2)
    ident = win.identify
    ident.start()
    target = ident.panel.target
    typed = 0
    while ident.stack.currentIndex() != 2 and typed < len(target):
        type_text(app, ident.panel.input, target[typed:typed + 5], rng, speed=0.3)
        typed += 5
        wait(app, 0.05)
    wait(app, 1.2)
    assert not warnings, warnings
    assert ident.stack.currentIndex() == 2 and ident._early
    assert typed < len(target) and len(ident.sample.typed) < len(target)
    entry = svc.history()[0]
    assert entry["early"] is True and 60 <= entry["keys"] < len(target)


def test_challenge_mode(app, tmp_path, monkeypatch):
    import ksb.gui.pages.identify as identify_mod
    from ksb import texts
    from ksb.texts import ENROLL_TEXTS
    from tests.simulate import SyntheticTypist
    rng = random.Random(8)
    svc = BiometricService(Storage(tmp_path))
    t = SyntheticTypist(42)
    ana = svc.create_user("Ana", [t.type_text(x, rng, text_id=k).build_sample() for k, x in list(ENROLL_TEXTS.items())[:3]])
    monkeypatch.setattr(identify_mod, "pick_verify_text",
                        lambda avoid=None, lang="es": (lambda kt: (kt[0], kt[1][:110]))(texts.pick_verify_text(avoid, lang)))
    monkeypatch.setattr(identify_mod, "early_decision", lambda *a, **k: "accept")   # en el desafío no se usa
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warnings.append(a))
    win = MainWindow(svc)
    win.show()
    win.nav.setCurrentRow(2)
    ident = win.identify
    ident.mode_sel.group.button(2).click()
    ident.refresh()
    assert ident.mode == "challenge" and ident.challenger_combo.isVisibleTo(ident)
    assert "Pista" in ident.mode_help.text() and "Ana" in ident.mode_help.text()
    assert ident.claim_combo.currentData() == ana.id and ident.challenger_combo.currentData() is None
    ident.start()
    target = ident.panel.target
    type_text(app, ident.panel.input, target, rng, speed=0.3)
    wait(app, 0.8)
    assert not warnings, warnings
    assert ident.stack.currentIndex() == 2 and not ident._early
    assert "engañ" in ident.verdict_title.text() and not ident.feedback_row.isVisibleTo(ident)
    assert "Marcador de desafíos: 1 intento" in ident.feedback_done.text()
    entry = svc.history()[0]
    assert entry["mode"] == "challenge" and entry["feedback"] in ("correct", "incorrect") and entry["keys"] >= len(target) - 5
    assert len(svc.storage.get_user(ana.id).samples) == 3
    win.nav.setCurrentRow(4)
    assert "Desafío" in win.history.table.item(0, 1).text()


def test_access_dialog(app, tmp_path, monkeypatch):
    """Verificación de acceso: la comparación es la real, pero se fuerza si coincide o no para recorrer
    los dos caminos (coincide a la primera; no coincide → aviso → verificación adicional)."""
    import ksb.gui.access as access_mod
    from ksb import texts
    from ksb.gui.app import parse_args
    from ksb.texts import ENROLL_TEXTS
    from tests.simulate import SyntheticTypist
    rng = random.Random(11)
    svc = BiometricService(Storage(tmp_path))
    t = SyntheticTypist(44)
    ana = svc.create_user("Ana", [t.type_text(x, rng, text_id=k).build_sample() for k, x in list(ENROLL_TEXTS.items())[:3]])
    monkeypatch.setattr(access_mod, "pick_verify_text",
                        lambda avoid=None, language="es": (lambda kt: (kt[0], kt[1][:110]))(texts.pick_verify_text()))
    real, forced = svc.access_check, []
    monkeypatch.setattr(svc, "access_check", lambda s, uid: (real(s, uid)[0], forced.pop(0)))
    monkeypatch.setattr(access_mod, "AUTO_CLOSE_MS", 200)
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warnings.append(a))

    def type_target(dlg):
        type_text(app, dlg.panel.input, dlg.panel.target, rng, speed=0.3)
        wait(app, 0.7)
        assert not warnings, warnings

    # coincide a la primera: se cierra sola y queda solo el día, la persona y la puntuación
    forced[:] = [True]
    dlg = access_mod.AccessDialog(svc, ana, "Nóminas")
    dlg.show()
    assert "Nóminas" in dlg.intro.text() and dlg.panel.target in texts.ACCESS_PHRASES.values()
    type_target(dlg)
    assert dlg.code == access_mod.EXIT_OK and "confirmada" in dlg.result_title.text()
    wait(app, 0.4)
    assert not dlg.isVisible()
    assert set(svc.access_log()[0]) == {"id", "date", "user_id", "score", "match"}

    # no coincide: aviso y verificación adicional con un texto más largo
    forced[:] = [False, True]
    dlg = access_mod.AccessDialog(svc, ana, "Nóminas")
    dlg.show()
    type_target(dlg)
    assert dlg.code == access_mod.EXIT_DENIED and "adicional" in dlg.result_title.text()
    assert svc.access_log()[0]["extra"] == "pending" and svc.access_log()[0]["system"] == "Nóminas"
    dlg.next_btn.click()
    assert dlg.step == "extra" and dlg.panel.target not in texts.ACCESS_PHRASES.values()
    type_target(dlg)
    assert dlg.code == access_mod.EXIT_OK and svc.access_log()[0]["extra"] == "passed"
    dlg.close()

    # no coincide y se cierra la ventana: el aviso queda como abandonado
    forced[:] = [False]
    dlg = access_mod.AccessDialog(svc, ana, "ERP")
    dlg.show()
    type_target(dlg)
    dlg.reject()
    assert dlg.code == access_mod.EXIT_DENIED and svc.access_log()[0]["extra"] == "abandoned"
    # cancelar antes de escribir: no se ha comprobado nada y no se guarda nada
    dlg = access_mod.AccessDialog(svc, ana)
    dlg.show()
    dlg.reject()
    assert dlg.code == access_mod.EXIT_UNCHECKED and len(svc.access_log()) == 3
    assert len(svc.storage.get_user(ana.id).samples) == 3 and svc.history() == []

    errors = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: errors.append(a))
    assert access_mod.run_access(svc, "Nadie") == access_mod.EXIT_UNCHECKED and errors
    args = parse_args(["keybio", "--acceso", "Ana", "--sistema", "Nóminas", "-platform", "offscreen"])
    assert (args.acceso, args.sistema) == ("Ana", "Nóminas") and parse_args(["keybio"]).acceso is None

    # la página «Accesos» del administrador
    win = MainWindow(svc)
    win.nav.setCurrentRow(5)
    page = win.access
    assert page.table.rowCount() == 3 and page.t_notices.value.text() == "2"
    page.only_notices.setChecked(True)
    assert page.table.rowCount() == 2 and "abandonada" in page.table.item(0, 5).text()
    win.close()
