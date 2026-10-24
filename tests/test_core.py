import random

from ksb.capture import CHAR, MOD, KeystrokeRecorder
from ksb.features import extract
from ksb.matcher import Profile, a_measure, identify, r_measure
from ksb.service import BiometricService
from ksb.storage import Storage
from ksb.textutil import fold, levenshtein, normalize_typed
from ksb.texts import ENROLL_TEXTS, VERIFY_TEXTS
from tests.simulate import SyntheticTypist

MS = 1_000_000


def test_text_utils():
    assert fold("Canción ñandú") == "Cancion nandu"
    assert normalize_typed("cancio´n", "canción") == "cancion"
    assert levenshtein("kitten", "sitting") == 3
    assert levenshtein("", "abc") == 3


def test_recorder_pairs_press_release_and_ignores_autorepeat():
    rec = KeystrokeRecorder("ab")
    rec.press(30, "a", CHAR, 0)
    rec.press(30, "a", CHAR, 30 * MS, autorepeat=True)   # repetición
    rec.press(30, "a", CHAR, 40 * MS)                    # pulsación sin soltar (Windows)
    rec.release(30, 95 * MS)
    rec.press(50, "shift_l", MOD, 100 * MS)
    rec.press(48, "b", CHAR, 180 * MS)
    rec.release(48, 260 * MS)
    rec.release(50, 270 * MS)
    rec.text_changed("a")
    rec.text_changed("ax")
    assert [k.label for k in rec.keystrokes] == ["a", "shift_l", "b"]
    assert rec.keystrokes[0].dwell == 95
    assert rec.keystrokes[2].dwell == 80
    assert rec.autorepeats == 2
    assert rec.errors_committed == 1 and rec.error_positions == [1]


def test_r_and_a_measures():
    a = {str(i): float(i + 1) for i in range(20)}
    assert r_measure(a, a) == 0
    assert a_measure(a, a) == 0
    rev = {k: -v for k, v in a.items()}
    assert r_measure(a, rev) == 1.0
    assert r_measure({"x": 1}, {"x": 1}) is None   # pocos n-gramas compartidos


def test_features_and_identification():
    rng = random.Random(3)
    profiles, typists = [], []
    for u in range(4):
        t = SyntheticTypist(200 + u)
        feats = [extract(t.type_text(txt, rng).build_sample())
                 for txt in list(ENROLL_TEXTS.values())[u:u + 3]]
        assert feats[0].metrics["wpm"] > 5
        assert feats[0].di and feats[0].tri and feats[0].globals
        profiles.append(Profile.build(f"{u:x}", f"u{u}", feats))
        typists.append(t)
    for u, t in enumerate(typists):
        f = extract(t.drifted(0.04, u).type_text(VERIFY_TEXTS["V2"], rng, "verify").build_sample())
        res = identify(f, profiles)
        assert res.best is not None and res.best.name == f"u{u}"
    stranger = extract(SyntheticTypist(999).type_text(VERIFY_TEXTS["V3"], rng, "verify").build_sample())
    assert identify(stranger, profiles).is_unknown


def test_service_roundtrip(tmp_path):
    svc = BiometricService(Storage(tmp_path))
    rng = random.Random(1)
    t = SyntheticTypist(42)
    samples = [t.type_text(txt, rng, text_id=k).build_sample()
               for k, txt in list(ENROLL_TEXTS.items())[:3]]
    assert all(svc.check_quality(s) is None for s in samples)
    user = svc.create_user("Ana", samples)
    loaded = svc.storage.get_user(user.id)
    assert loaded.name == "Ana" and len(loaded.samples) == 3
    assert abs(loaded.samples[0].keystrokes[5].press - samples[0].keystrokes[5].press) < 1e-3
    sample = t.type_text(VERIFY_TEXTS["V1"], rng, "verify", "V1").build_sample()
    res, _ = svc.identify(sample)
    assert res.best and res.best.name == "Ana"
    entry = svc.log_identification(sample, res)
    svc.set_feedback(entry["id"], "correct", user.id)
    assert svc.history()[0]["feedback"] == "correct"
    svc.delete_user(user.id)
    assert svc.users() == []


def test_label_and_keyboard_mapping():
    from ksb.gui.keyboard import key_for
    assert key_for("!", "es") == "1" and key_for("?", "es") == "'" and key_for("@", "es") == "2"
    assert key_for("á", "es") == "a" and key_for("ñ", "es") == "ñ" and key_for("Ñ", "es") == "ñ"
    assert key_for("dead_acute", "es") == "´" and key_for("shift", "es") == "shift_l"
    assert key_for("?", "us") == "/" and key_for(" ", "us") == "space"


def test_evaluation_and_verify(tmp_path):
    from ksb.evaluation import evaluate
    svc = BiometricService(Storage(tmp_path))
    rng = random.Random(4)
    typists = [SyntheticTypist(600 + i) for i in range(3)]
    texts = list(ENROLL_TEXTS.items())
    for i, t in enumerate(typists):
        svc.create_user(f"u{i}", [t.type_text(x, rng, text_id=k).build_sample() for k, x in texts[i:i + 4]])
    res = evaluate(svc.evaluation_input(), "normal")
    assert res.users == 3 and res.genuine_total == 12 and res.impostor_total == 12
    assert res.identification_rate >= 0.75 and res.false_accept_rate <= 0.25
    sample = typists[1].type_text(VERIFY_TEXTS["V5"], rng, "verify", "V5").build_sample()
    users = {u.name: u for u in svc.users()}
    _, claimed, _ = svc.verify(sample, users["u1"].id)
    assert claimed.accepted
    _, other, _ = svc.verify(sample, users["u0"].id)
    assert not other.accepted
    entry = svc.log_identification(sample, svc.identify(sample)[0], "verify", other)
    assert entry["accepted"] is False and entry["claimed"] == "u0"
    stats = svc.dashboard_stats()
    assert stats["users"] == 3 and stats["checks"] == 1 and len(stats["days"]) == 14


def test_export_import_and_backup(tmp_path):
    src = Storage(tmp_path / "a")
    rng = random.Random(2)
    t = SyntheticTypist(77)
    svc = BiometricService(src)
    user = svc.create_user("Eva", [t.type_text(x, rng, text_id=k).build_sample()
                                   for k, x in list(ENROLL_TEXTS.items())[:3]])
    src.export_users([user], tmp_path / "eva.json")
    src.export_backup(tmp_path / "copia.zip")
    dst = Storage(tmp_path / "b")
    assert dst.import_users(tmp_path / "eva.json") == [("Eva", 3)]
    assert dst.import_users(tmp_path / "copia.zip") == [("Eva", 0)]      # mismo id: nada nuevo
    other = Storage(tmp_path / "c")
    other.save_user(type(user)("Eva"))                                    # otro "Eva" distinto
    assert other.import_users(tmp_path / "eva.json") == [("Eva (2)", 3)]
    svc_b = BiometricService(dst)
    u = svc_b.users()[0]
    svc_b.add_samples(u.id, [t.type_text(VERIFY_TEXTS["V1"], rng, "verify").build_sample()])
    u = svc_b.delete_sample(u.id, svc_b.users()[0].samples[0].id)
    assert len(u.samples) == 3
