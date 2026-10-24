"""Mide lo bien que el sistema separa a cada persona de las demás (datos sintéticos).

AUC = probabilidad de que una muestra legítima quede más cerca (en distancia ÷ umbral)
que una de otra persona. 1.0 = separación perfecta.

Uso:  python -m tests.separation [spread] [drift]
"""

from __future__ import annotations

import random
import sys

from ksb.features import extract
from ksb.matcher import Profile, share_spread
from ksb.texts import ENROLL_TEXTS, VERIFY_TEXTS
from tests.simulate import SyntheticTypist


def auc(genuine: list[float], impostor: list[float]) -> float:
    wins = sum((g < i) + 0.5 * (g == i) for g in genuine for i in impostor)
    return wins / (len(genuine) * len(impostor))


def run(spread: float = 0.5, drift: float = 0.08, n_users: int = 12, seed: int = 11):
    rng = random.Random(seed)
    typists = [SyntheticTypist(2000 + u, spread) for u in range(n_users)]
    profiles = []
    for t in typists:
        texts = rng.sample(list(ENROLL_TEXTS.items()), 3)
        feats = [extract(t.type_text(x, rng, text_id=k).build_sample()) for k, x in texts]
        profiles.append(Profile.build(str(t.seed), str(t.seed), feats))
    share_spread(profiles)   # como en la aplicación
    gen, imp = [], []
    errors = 0
    for i, t in enumerate(typists):
        for j in range(3):
            k, x = rng.choice(list(VERIFY_TEXTS.items()))
            f = extract(t.drifted(drift, seed=i * 10 + j).type_text(x, rng, "verify", k).build_sample())
            ratios = [p.distance(f).total / p.threshold("normal") for p in profiles]
            gen.append(ratios[i])
            imp.extend(r for q, r in enumerate(ratios) if q != i)
            errors += min(range(len(ratios)), key=ratios.__getitem__) != i
    far = sum(r <= 1 for r in imp) / len(imp)
    frr = sum(r > 1 for r in gen) / len(gen)
    return auc(gen, imp), far, frr, errors / len(gen)


if __name__ == "__main__":
    import ksb.matcher as m
    spread = float(sys.argv[1]) if len(sys.argv) > 1 else 0.5
    drift = float(sys.argv[2]) if len(sys.argv) > 2 else 0.08
    for use_ud in (False, True):
        m.USE_UD = use_ud
        a, far, frr, rank_err = run(spread, drift)
        print(f"UD={use_ud!s:5}  AUC={a:.4f}  FAR={far:.3f}  FRR={frr:.3f}  error de ranking={rank_err:.3f}")
