"""Verificación de acceso con una frase corta: la muestra se descarta y solo queda la puntuación."""

import random
import zipfile
from datetime import datetime, timedelta

import pytest

from ksb import crypto, matcher
from ksb.capture import CHAR, KeystrokeRecorder
from ksb.service import BiometricService
from ksb.storage import Storage
from ksb.texts import ACCESS_PHRASES, ACCESS_PHRASES_EN, ENROLL_TEXTS, pick_access_phrase
from tests.simulate import SyntheticTypist

MATCH_FIELDS = {"id", "date", "user_id", "score", "match"}
NOTICE_FIELDS = MATCH_FIELDS | {"system", "extra"}


@pytest.fixture(autouse=True)
def _reset_matcher():
    yield
    matcher.set_fusion(0.55, 2.0)


def _team(tmp_path, n=3):
    rng = random.Random(5)
    svc = BiometricService(Storage(tmp_path))
    typists = [SyntheticTypist(700 + i) for i in range(n)]
    users = [svc.create_user(f"P{i}", [t.type_text(x, rng, text_id=k).build_sample()
                                       for k, x in list(ENROLL_TEXTS.items())[i:i + 3]])
             for i, t in enumerate(typists)]
    return svc, typists, users, rng


def test_phrases_are_short_but_long_enough():
    # con menos de ~90 pulsaciones se rechaza a bastantes usuarios legítimos (ver texts.ACCESS_PHRASES)
    for pool in (ACCESS_PHRASES, ACCESS_PHRASES_EN):
        assert all(90 <= len(p) <= 105 for p in pool.values())
    assert pick_access_phrase(language="en")[0].startswith("EN-")
    assert not pick_access_phrase(language="es")[0].startswith("EN-")


def test_access_check_discards_the_sample(tmp_path):
    svc, typists, users, rng = _team(tmp_path)
    before = {u.id: [s.id for s in u.samples] for u in svc.users()}
    tid, phrase = pick_access_phrase()
    genuine = typists[0].type_text(phrase, rng, "verify", tid).build_sample()
    impostor = typists[1].type_text(phrase, rng, "verify", tid).build_sample()
    assert svc.check_quality(genuine) is None
    score, match = svc.access_check(genuine, users[0].id)
    other, other_match = svc.access_check(impostor, users[0].id)
    assert match and not other_match and score > other
    assert isinstance(score, int) and 0 <= other < 50 <= score <= 100
    # nada de la muestra se queda: ni en los perfiles, ni en el historial, ni en la caché
    assert {u.id: [s.id for s in u.samples] for u in svc.users()} == before
    assert svc.history() == [] and genuine.id not in svc._feat_cache
    assert not (tmp_path / "access.jsonl").exists()

    ok = svc.log_access(users[0].id, score, True, "Nóminas")
    notice = svc.log_access(users[0].id, other, False, "Nóminas <script>")
    assert set(ok) == MATCH_FIELDS and len(ok["date"]) == 10          # solo el día
    assert set(notice) == NOTICE_FIELDS and "T" in notice["date"]      # el aviso, con hora y sistema
    assert notice["system"] == "Nóminas script" and notice["extra"] == "pending"
    raw = (tmp_path / "access.jsonl").read_text(encoding="utf-8")
    assert phrase[:15] not in raw and "keystrokes" not in raw
    svc.finish_access(notice["id"], "passed")
    assert svc.access_log()[0]["extra"] == "passed"
    with pytest.raises(ValueError):
        svc.finish_access(notice["id"], "otra cosa")


def test_suspicious_typing_never_matches(tmp_path):
    svc, _, users, _ = _team(tmp_path, 1)
    rec = KeystrokeRecorder("a" * 100, "A1", "verify")
    t = 0.0
    for i in range(100):    # un programa que teclea con un ritmo perfecto
        rec.press(i, "a", CHAR, int(t * 1e6))
        rec.release(i, int((t + 50) * 1e6))
        t += 120
    assert svc.access_check(rec.build_sample(), users[0].id) == (0, False)


def test_notices_reach_the_dashboard_and_expire(tmp_path):
    svc, _, users, _ = _team(tmp_path, 2)
    old = (datetime.now() - timedelta(days=40)).isoformat(timespec="minutes")
    svc.storage.append_access({"id": "viejo", "date": old, "user_id": users[0].id, "score": 20, "match": False,
                               "system": "", "extra": "failed"})
    svc.log_access(users[0].id, 80, True)
    notice = svc.log_access(users[1].id, 30, False, "ERP")
    assert [e["user_id"] for e in svc.access_log()] == [users[1].id, users[0].id]   # el de hace 40 días, fuera
    assert all(e["id"] != "viejo" for e in svc.storage.read_access())
    tip = next(t for t in svc.tips() if t[2] == "access")
    assert tip[0] == "warn" and "semana: 1 (1 sin superar" in tip[1]
    svc.finish_access(notice["id"], "passed")
    assert "(verificación adicional superada)" in next(t for t in svc.tips() if t[2] == "access")[1]
    # al borrar a una persona se borran también sus registros
    svc.delete_user(users[1].id)
    assert [e["user_id"] for e in svc.access_log()] == [users[0].id]
    assert not any(t[2] == "access" for t in svc.tips())


def test_access_log_is_encrypted_and_left_out_of_backups(tmp_path):
    if not crypto.AVAILABLE:
        pytest.skip("cryptography no instalado")
    svc, _, users, _ = _team(tmp_path, 1)
    svc.log_access(users[0].id, 30, False, "Banca#1")
    svc.storage.enable_protection("secreto 123")
    assert "Banca#1" not in (tmp_path / "access.jsonl").read_text(encoding="utf-8")
    fresh = Storage(tmp_path)
    fresh.unlock("secreto 123")
    assert fresh.read_access()[0]["system"] == "Banca#1"
    fresh.export_backup(tmp_path / "copia.zip")
    with zipfile.ZipFile(tmp_path / "copia.zip") as zf:
        assert "access.jsonl" not in zf.namelist() and "history.jsonl" in zf.namelist()
    fresh.disable_protection()
    assert "Banca#1" in (tmp_path / "access.jsonl").read_text(encoding="utf-8")
