"""Pruebas de las funciones añadidas en la versión 2: sesiones, adaptación, cifrado,
detección de suplantaciones, calibración, texto libre e identificación en directo."""

import copy
import json
import random
from datetime import datetime, timedelta

import pytest

from ksb import crypto, matcher
from ksb.capture import CHAR, KeystrokeRecorder
from ksb.evaluation import calibrate
from ksb.features import extract
from ksb.liveness import check, is_blocking
from ksb.service import BiometricService, sessions_of
from ksb.storage import LockedError, Storage
from ksb.texts import ENROLL_TEXTS, VERIFY_TEXTS, pick_enroll_texts, pick_verify_text
from tests.simulate import SyntheticTypist


@pytest.fixture(autouse=True)
def _reset_matcher():
    yield
    matcher.set_fusion(0.55, 2.0)


def _samples(typist, n, rng, start=None, gap_minutes=5):
    out = []
    t0 = start or datetime(2026, 1, 1, 10, 0)
    for i, (k, x) in enumerate(list(ENROLL_TEXTS.items())[:n]):
        s = typist.type_text(x, rng, text_id=k).build_sample()
        s.created = (t0 + timedelta(minutes=gap_minutes * i)).isoformat(timespec="seconds")
        out.append(s)
    return out


def test_sessions_and_profile_composition(tmp_path):
    rng = random.Random(1)
    t = SyntheticTypist(10)
    day1 = _samples(t, 3, rng)
    day2 = _samples(t, 2, rng, start=datetime(2026, 1, 3, 18, 0))
    assert sessions_of(day1 + day2) == ["s0", "s0", "s0", "s1", "s1"]
    svc = BiometricService(Storage(tmp_path))
    user = svc.create_user("Ana", day1 + day2)
    prof = svc.profile(user)
    assert prof.multi_session and len(prof.loo_parts) == 5
    assert prof.slack() == matcher.SLACK_MULTI
    assert svc.quality(user)[0] == "good"
    # el perfil conserva siempre las muestras de registro aunque haya muchas adaptadas
    extra = [t.type_text(VERIFY_TEXTS["V1"], rng, "adapt", "V1").build_sample() for _ in range(10)]
    for s in extra:
        s.kind = "adapt"
    user = svc.add_samples(user.id, extra)
    chosen = svc.profile_samples(user)
    assert len(chosen) == 12 and sum(s.kind == "enroll" for s in chosen) == 5


def test_single_sample_from_another_session_barely_reduces_margin():
    # Caso real: varias muestras de un día y 1 de otro. Solo esa muestra se calibra
    # apartando otra sesión; el resto no, así que el margen apenas debe bajar.
    rng = random.Random(2)
    t = SyntheticTypist(11)
    samples = _samples(t, 4, rng) + _samples(t, 1, rng, start=datetime(2026, 1, 3, 18, 0))
    feats = [extract(s) for s in samples]
    prof = matcher.Profile.build("a", "Ana", feats, sessions=sessions_of(samples))
    assert prof.multi_session and prof.cross_frac == pytest.approx(1 / 5)
    assert prof.slack() == pytest.approx(matcher.SLACK + (matcher.SLACK_MULTI - matcher.SLACK) / 5)


def test_small_profiles_take_the_spread_of_the_team():
    rng = random.Random(3)
    team = []
    for u in range(3):
        feats = [extract(s) for s in _samples(SyntheticTypist(700 + u), 4, rng)]
        team.append(matcher.Profile.build(str(u), f"u{u}", feats))
    small = matcher.Profile.build("x", "Eva", [extract(s) for s in _samples(SyntheticTypist(799), 2, rng)])
    assert small.s == matcher.S_FALLBACK             # sin equipo: valor fijo prudente
    matcher.share_spread(team + [small])
    pooled = matcher.pooled_spread(team, matcher.W_RA)
    assert pooled is not None and small.s == pytest.approx(pooled)
    assert matcher.pooled_spread(team[:1], matcher.W_RA) is None   # un solo perfil de 4 muestras: poco


def test_auto_adapt_and_rollback(tmp_path, monkeypatch):
    import ksb.service as service_mod
    monkeypatch.setattr(service_mod, "ADAPT_MIN_CONFIDENCE", 0.0)   # la confianza aquí ronda el 70 %
    rng = random.Random(2)
    t = SyntheticTypist(20)
    svc = BiometricService(Storage(tmp_path))
    user = svc.create_user("Bea", _samples(t, 4, rng))
    sample = t.type_text(VERIFY_TEXTS["V2"], rng, "verify", "V2").build_sample()
    result, _ = svc.identify(sample)
    assert result.best and result.best.name == "Bea"
    adapted = svc.maybe_adapt(sample, result.best, result, [])
    assert adapted is not None and len(adapted.samples) == 5 and adapted.samples[-1].kind == "adapt"
    entry = svc.log_identification(sample, result, adapted=adapted)
    undone = svc.set_feedback(entry["id"], "incorrect", None)
    assert undone == "Bea"
    assert len(svc.storage.get_user(user.id).samples) == 4
    # con sospechas de suplantación nunca se adapta
    from ksb.liveness import Finding
    assert svc.maybe_adapt(sample, result.best, result, [Finding("bad", "robotic", "")]) is None
    svc.settings["auto_adapt"] = False
    assert svc.maybe_adapt(sample, result.best, result, []) is None


def test_encryption_roundtrip(tmp_path):
    if not crypto.AVAILABLE:
        pytest.skip("cryptography no instalado")
    rng = random.Random(3)
    st = Storage(tmp_path)
    svc = BiometricService(st)
    svc.create_user("Carla", _samples(SyntheticTypist(30), 2, rng))
    # "#" no existe en base64: el id no puede aparecer por azar en el texto cifrado
    svc.storage.append_history({"id": "h#1", "date": "2026-01-01T10:00:00"})
    st.enable_protection("secreto 123")
    raw = next((tmp_path / "users").glob("*.json")).read_text(encoding="utf-8")
    assert "Carla" not in raw and json.loads(raw)["keybio_encrypted"] == 1
    assert "h#1" not in (tmp_path / "history.jsonl").read_text(encoding="utf-8")

    fresh = Storage(tmp_path)
    assert fresh.protected and fresh.locked
    with pytest.raises(LockedError):
        fresh.list_users()
    with pytest.raises(crypto.WrongPassword):
        fresh.unlock("mala")
    fresh.unlock("secreto 123")
    assert [u.name for u in fresh.list_users()] == ["Carla"]
    assert fresh.read_history()[0]["id"] == "h#1"
    fresh.export_backup(tmp_path / "copia.zip")          # la copia sale legible
    fresh.disable_protection()
    assert "Carla" in next((tmp_path / "users").glob("*.json")).read_text(encoding="utf-8")
    assert not Storage(tmp_path).protected
    other = Storage(tmp_path / "otra")
    assert other.import_users(tmp_path / "copia.zip") == [("Carla", 2)]


def test_liveness_detects_bots_and_replays():
    rng = random.Random(4)
    human = SyntheticTypist(40).type_text(ENROLL_TEXTS["R1"], rng, text_id="R1").build_sample()
    assert check(human) == []
    rec = KeystrokeRecorder("a" * 100, "R1")
    t = 0.0
    for i in range(100):
        rec.press(i, "a", CHAR, int(t * 1e6))
        rec.release(i, int((t + 50) * 1e6))
        t += 120
    bot = rec.build_sample()
    assert is_blocking(check(bot))
    replay = copy.deepcopy(human)
    replay.id = "otra"
    assert "replay" in [f.code for f in check(replay, [human])]


def test_calibration_needs_data_and_finds_parameters():
    rng = random.Random(5)
    users = []
    for u in range(4):
        t = SyntheticTypist(500 + u, 0.6)
        feats = [extract(s) for s in _samples(t, 4, rng)]
        users.append((str(u), f"u{u}", feats))
    small = calibrate(users[:2])
    assert not small.enough
    cal = calibrate(users)
    assert cal.enough and 0.3 <= cal.weight <= 0.9 and cal.k >= 1.0
    assert set(cal.levels) == {"estricto", "normal", "permisivo"}


def test_free_text_and_light_extraction():
    rec = KeystrokeRecorder("", "libre", "verify", free=True)
    t = 0.0
    text = ""
    for i, ch in enumerate("hola que tal estas hoy " * 6):
        rec.press(i, ch if ch != " " else "space", CHAR, int(t * 1e6))
        rec.release(i, int((t + 70 + (i % 5) * 9) * 1e6))
        text += ch
        rec.text_changed(text)
        t += 140 + (i % 7) * 23
    s = rec.build_sample()
    assert s.free and s.target == s.typed and s.accuracy == 1.0 and s.errors_committed == 0
    f = extract(s)
    assert "err_rate" not in f.globals and f.metrics["wpm"] > 0
    partial = SyntheticTypist(50).type_text(ENROLL_TEXTS["R2"], random.Random(6)).build_sample()
    partial.typed = partial.typed[:80]
    light = extract(partial, light=True)
    assert light.metrics["accuracy"] == 100.0


def test_text_languages():
    assert all(k.startswith("EN-") for k, _ in pick_enroll_texts(3, language="en"))
    assert pick_verify_text(language="en")[0].startswith("EN-V")
    assert len(pick_enroll_texts(20, language="mixed")) == len(ENROLL_TEXTS) + 5


def test_history_trials_from_feedback(tmp_path):
    rng = random.Random(7)
    svc = BiometricService(Storage(tmp_path))
    typists = [SyntheticTypist(700 + i) for i in range(2)]
    for i, t in enumerate(typists):
        svc.create_user(f"p{i}", _samples(t, 3, rng))
    sample = typists[0].type_text(VERIFY_TEXTS["V3"], rng, "verify", "V3").build_sample()
    result, _ = svc.identify(sample)
    entry = svc.log_identification(sample, result)
    svc.set_feedback(entry["id"], "correct" if result.best else "incorrect",
                     None if result.best else svc.users()[0].id)
    trials = svc.history_trials()
    assert len(trials) == 2 and sum(t.genuine for t in trials) == 1
    assert all(t.cross_session for t in trials)
