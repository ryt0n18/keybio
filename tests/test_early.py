"""Decisión progresiva: terminar la comprobación en cuanto el resultado está claro."""

import copy
import random

from ksb import matcher
from ksb.capture import TYPING_KINDS
from ksb.matcher import Candidate, Identification, early_decision
from ksb.service import ADAPT_MIN_KEYS, BiometricService
from ksb.storage import Storage
from ksb.texts import ENROLL_TEXTS, VERIFY_TEXTS
from tests.simulate import SyntheticTypist


def _result(*ratios):
    cands = [Candidate(f"u{i}", f"U{i}", r, 1.0, 0.5, None, None) for i, r in enumerate(ratios)]
    return Identification(sorted(cands, key=lambda c: c.ratio), None)


def test_rule():
    n = matcher.EARLY_MIN_KEYS
    assert early_decision(_result(0.5, 2.0), n - 1) is None          # todavía muy poco texto
    assert early_decision(_result(0.8, 1.2), n) == "accept"
    assert early_decision(_result(0.8, 0.95), n) is None             # el segundo está demasiado cerca
    assert early_decision(_result(0.9, 2.0), n) is None              # parecido, pero no lo bastante
    assert early_decision(_result(0.8), n) == "accept"               # una sola persona registrada
    assert early_decision(_result(1.5, 1.8), n) == "reject"          # no se parece a nadie
    assert early_decision(_result(), n) is None
    # verificación: solo se acepta si el perfil indicado es claramente el más parecido
    assert early_decision(_result(0.7, 1.3), n, claimed_id="u0") == "accept"
    assert early_decision(_result(0.7, 1.3), n, claimed_id="u1") is None
    assert early_decision(_result(0.7, 1.5), n, claimed_id="u1") == "reject"


def _cut(sample, n):
    """Lo escrito hasta la pulsación n, como lo deja TypingPanel.snapshot()."""
    s = copy.deepcopy(sample)
    count = 0
    for i, k in enumerate(s.keystrokes):
        count += k.kind in TYPING_KINDS
        if count >= n:
            s.keystrokes = s.keystrokes[:i + 1]
            break
    s.typed = s.typed[:count]
    s.target = s.target[:count]
    return s


def test_short_text_decides_early_and_stays_out_of_profiles(tmp_path):
    rng = random.Random(9)
    texts = list(ENROLL_TEXTS.items())
    svc = BiometricService(Storage(tmp_path))
    typists = [SyntheticTypist(800 + i) for i in range(3)]
    for i, t in enumerate(typists):
        svc.create_user(f"P{i}", [t.type_text(x, rng, text_id=k).build_sample() for k, x in texts[i:i + 3]])
    profiles = svc.profiles()

    accepted = 0
    for i, t in enumerate(typists):
        for key, text in list(VERIFY_TEXTS.items())[:2]:
            full = t.type_text(text, rng, "verify", key).build_sample()
            decision = None
            for n in range(60, 200, 15):
                partial = _cut(full, n)
                res = svc.identify_partial(partial, profiles)
                decision = early_decision(res, n)
                if decision:
                    break
            assert decision != "reject"
            if decision == "accept":
                assert res.candidates[0].name == f"P{i}"     # nunca se acepta a otra persona
                accepted += 1
                assert svc.adapt_problem(partial) is not None  # una muestra corta no entra al perfil
                assert svc.maybe_adapt(partial, res.candidates[0], res, []) is None
    assert accepted >= 4, accepted                            # la mayoría termina antes

    stranger = SyntheticTypist(899).type_text(VERIFY_TEXTS["V3"], rng, "verify", "V3").build_sample()
    for n in range(60, 200, 15):
        assert early_decision(svc.identify_partial(_cut(stranger, n), profiles), n) != "accept"
    full = typists[0].type_text(VERIFY_TEXTS["V4"], rng, "verify", "V4").build_sample()
    assert sum(k.kind in TYPING_KINDS for k in full.keystrokes) >= ADAPT_MIN_KEYS
    assert svc.adapt_problem(full) is None


def test_history_records_early_decisions(tmp_path):
    rng = random.Random(3)
    svc = BiometricService(Storage(tmp_path))
    t = SyntheticTypist(820)
    svc.create_user("Ana", [t.type_text(x, rng, text_id=k).build_sample() for k, x in list(ENROLL_TEXTS.items())[:3]])
    sample = _cut(t.type_text(VERIFY_TEXTS["V1"], rng, "verify", "V1").build_sample(), 90)
    res, _ = svc.identify(sample)
    entry = svc.log_identification(sample, res, early=True)
    assert entry["early"] is True and entry["keys"] == 90
