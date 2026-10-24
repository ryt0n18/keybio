"""Genera fixture.json: pulsaciones sintéticas y lo que calcula Python con ellas.

Las pruebas de JavaScript (tests.js) recalculan lo mismo con keybio.js y comparan.
Se usan mecanógrafos simulados (tests/simulate.py), nunca muestras de personas reales.

Uso (desde la raíz del repositorio):  .venv/bin/python web/tests/make_fixture.py
"""

from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ksb.features import extract  # noqa: E402
from ksb.matcher import Profile, identify, share_spread  # noqa: E402
from ksb.service import sessions_of  # noqa: E402
from ksb.texts import ENROLL_TEXTS, VERIFY_TEXTS  # noqa: E402
from tests.simulate import SyntheticTypist  # noqa: E402

OUT = Path(__file__).with_name("fixture.json")


def sample_json(s) -> dict:
    return {
        "created": s.created, "textId": s.text_id, "free": s.free,
        "typedLength": len(s.typed_norm), "errorsCommitted": s.errors_committed, "accuracy": s.accuracy,
        "keys": [{"label": k.label, "kind": k.kind, "press": k.press, "release": k.release, "code": None}
                 for k in s.keystrokes],
    }


def main() -> None:
    rng = random.Random(42)
    enroll = list(ENROLL_TEXTS.items())
    start = datetime(2026, 1, 10, 9, 0)

    def typed(t: SyntheticTypist, key: str, text: str, when: datetime):
        s = t.type_text(text, rng, text_id=key).build_sample()
        s.created = when.isoformat(timespec="seconds")
        return s

    people = []
    # 0: dos sesiones (3 muestras un día y 1 otro), 1-2: 3 muestras, 3: solo 2 muestras
    for idx, n in enumerate((4, 3, 3, 2)):
        t = SyntheticTypist(900 + idx)
        samples = []
        for j in range(n):
            when = start + timedelta(minutes=5 * j) + (timedelta(days=2) if idx == 0 and j == 3 else timedelta())
            samples.append(typed(t, enroll[(idx + j) % len(enroll)][0], enroll[(idx + j) % len(enroll)][1], when))
        people.append((f"p{idx}", f"Persona {idx}", t, samples))

    profiles = []
    for uid, name, _, samples in people:
        feats = [extract(s) for s in samples]
        profiles.append(Profile.build(uid, name, feats, sessions=sessions_of(samples)))
    share_spread(profiles)

    verify = list(VERIFY_TEXTS.items())
    tests = [typed(people[0][2].drifted(0.04, seed=1), *verify[0], start + timedelta(days=3)),
             typed(people[2][2], *verify[1], start + timedelta(days=3)),
             typed(SyntheticTypist(990), *verify[2], start + timedelta(days=3))]
    free = typed(people[1][2], *verify[3], start + timedelta(days=3))
    free.target, free.free = free.typed, True
    tests.append(free)

    data = {
        "people": [{"id": uid, "name": name, "samples": [sample_json(s) for s in samples]}
                   for uid, name, _, samples in people],
        "tests": [sample_json(s) for s in tests],
        "expected": {
            "globals": [[extract(s).globals for s in samples] for *_, samples in people]
                       + [[extract(s).globals for s in tests]],
            "profiles": [{"id": p.user_id, "m": p.m, "s": p.s, "slack": p.slack(), "crossFrac": p.cross_frac,
                          "threshold": p.threshold("normal")} for p in profiles],
            "identify": [],
        },
    }
    for s in tests:
        res = identify(extract(s), profiles, "normal")
        data["expected"]["identify"].append({
            "best": res.best.user_id if res.best else None,
            "candidates": [{"id": c.user_id, "distance": c.distance, "ra": c.ra, "z": c.z,
                            "threshold": c.threshold} for c in res.candidates],
        })
    OUT.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {sum(len(p[3]) for p in people)} muestras de registro, {len(tests)} de prueba")


if __name__ == "__main__":
    main()
