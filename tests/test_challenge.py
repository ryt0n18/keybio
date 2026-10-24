"""Modo desafío: imitar a otra persona; el intento se guarda como impostor real."""

import random

from ksb.service import BiometricService
from ksb.storage import Storage
from ksb.texts import ENROLL_TEXTS, VERIFY_TEXTS
from tests.simulate import SyntheticTypist


def test_challenge_is_logged_as_an_impostor_trial(tmp_path):
    rng = random.Random(12)
    svc = BiometricService(Storage(tmp_path))
    texts = list(ENROLL_TEXTS.items())
    ana_t, beto_t = SyntheticTypist(850), SyntheticTypist(851)
    ana = svc.create_user("Ana", [ana_t.type_text(x, rng, text_id=k).build_sample() for k, x in texts[:3]])
    beto = svc.create_user("Beto", [beto_t.type_text(x, rng, text_id=k).build_sample() for k, x in texts[3:6]])

    attempt = beto_t.type_text(VERIFY_TEXTS["V2"], rng, "verify", "V2").build_sample()   # Beto imita a Ana
    result, target, _ = svc.verify(attempt, ana.id)
    entry = svc.log_challenge(attempt, result, target, beto.id)
    stored = svc.history()[0]
    assert stored["mode"] == "challenge" and stored["claimed_id"] == ana.id and stored["true_user"] == beto.id
    assert stored["feedback"] == ("incorrect" if entry["accepted"] else "correct")

    trials = svc.history_trials()
    assert len(trials) == 1                                # solo frente al perfil imitado
    assert trials[0].profile.user_id == ana.id and not trials[0].genuine and trials[0].cross_session
    assert svc.challenge_stats() == (1, int(entry["accepted"]))
    assert len(svc.storage.get_user(ana.id).samples) == 3   # el intento no toca ningún perfil
