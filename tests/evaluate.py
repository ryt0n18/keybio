"""Evalúa el identificador con mecanógrafos sintéticos.

Uso:  python -m tests.evaluate [n_registrados] [n_desconocidos]
"""

from __future__ import annotations

import random
import sys

from ksb.features import extract
from ksb.matcher import SENSITIVITY, Profile, identify, share_spread
from ksb.texts import ENROLL_TEXTS, VERIFY_TEXTS
from tests.simulate import SyntheticTypist


def run(n_users: int = 8, n_unknown: int = 8, tests_per_user: int = 4, seed: int = 7):
    rng = random.Random(seed)
    profiles = []
    typists = []
    for u in range(n_users):
        typist = SyntheticTypist(1000 + u)
        texts = rng.sample(list(ENROLL_TEXTS.items()), 3)
        feats = [extract(typist.type_text(t, rng, text_id=k).build_sample()) for k, t in texts]
        profiles.append(Profile.build(f"{u:02x}", f"user{u}", feats))
        typists.append(typist)
    share_spread(profiles)   # como en la aplicación

    trials = []
    for u, typist in enumerate(typists):
        for i in range(tests_per_user):
            k, t = rng.choice(list(VERIFY_TEXTS.items()))
            day = typist.drifted(0.05, seed=u * 100 + i)
            trials.append((f"user{u}", extract(day.type_text(t, rng, "verify", k).build_sample())))
    for j in range(n_unknown):
        k, t = rng.choice(list(VERIFY_TEXTS.items()))
        trials.append((None, extract(SyntheticTypist(5000 + j).type_text(t, rng, "verify", k).build_sample())))

    print("Calibración (m, s) por usuario:")
    for p in profiles:
        print(f"  {p.name}: m={p.m:.3f} s={p.s:.3f} loo={[round(x, 3) for x in p.loo]}")

    for sens in SENSITIVITY:
        ok_known = wrong_user = false_reject = ok_unknown = false_accept = 0
        for truth, f in trials:
            res = identify(f, profiles, sens)
            got = res.best.name if res.best else None
            if truth is None:
                ok_unknown += got is None
                false_accept += got is not None
            else:
                ok_known += got == truth
                wrong_user += got is not None and got != truth
                false_reject += got is None
        nk = n_users * tests_per_user
        print(f"[{sens:9}] registrados: aciertos {ok_known}/{nk}, usuario erróneo {wrong_user}, "
              f"rechazos {false_reject} | desconocidos: rechazados {ok_unknown}/{n_unknown}, "
              f"aceptados {false_accept}")
    return profiles, trials


if __name__ == "__main__":
    args = [int(a) for a in sys.argv[1:]]
    run(*args)
