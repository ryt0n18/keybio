"""Mecanógrafos sintéticos para probar el sistema de extremo a extremo.

Cada persona simulada tiene una velocidad, tiempos de pulsación por tecla,
un factor propio por cada dígrafo, tendencia al solapamiento, lado del
shift preferido y tasa de errores. No sustituye a datos reales, pero
permite comprobar que la captura, la extracción y la comparación funcionan.
"""

from __future__ import annotations

import hashlib
import random
import unicodedata

from ksb.capture import BACKSPACE, CHAR, DEAD, MOD, SPACE, KeystrokeRecorder

_ACCENTS = {"́": "dead_acute", "̈": "dead_diaeresis"}


def _stable(seed: int, *key) -> random.Random:
    h = hashlib.sha256(repr((seed,) + key).encode()).digest()
    return random.Random(int.from_bytes(h[:8], "big"))


class SyntheticTypist:
    def __init__(self, seed: int, spread: float = 1.0):
        """``spread`` < 1 hace que las personas se parezcan más entre sí (prueba más difícil)."""
        r = random.Random(seed)

        def u(lo, hi):
            mid = (lo + hi) / 2
            return mid + (r.uniform(lo, hi) - mid) * spread

        self.seed = seed
        self.spread = spread
        self.base_dd = u(140, 340)
        self.dwell_base = u(65, 135)
        self.noise = u(0.12, 0.28)
        self.digraph_spread = u(0.18, 0.35)
        self.space_factor = u(0.8, 1.4)
        self.right_shift = u(0.0, 1.0)
        self.shift_lead = u(60, 220)
        self.error_p = u(0.005, 0.05)
        self.reaction = u(250, 700)
        self.pause_p = u(0.0, 0.03)

    def drifted(self, amount: float = 0.05, seed: int = 0) -> "SyntheticTypist":
        """La misma persona otro día: pequeñas variaciones de ritmo."""
        r = random.Random(seed)
        t = SyntheticTypist.__new__(SyntheticTypist)
        t.__dict__.update(self.__dict__)
        t.spread = getattr(self, "spread", 1.0)
        t.base_dd *= r.gauss(1, amount)
        t.dwell_base *= r.gauss(1, amount)
        t.shift_lead *= r.gauss(1, amount)
        return t

    def _key_dwell(self, label: str) -> float:
        # parte común a toda la población (unas teclas se pulsan más que otras) + parte individual
        shared = _stable(0, "dwell", label).lognormvariate(0, 0.12)
        return self.dwell_base * shared * _stable(self.seed, "dwell", label).lognormvariate(0, 0.15 * self.spread)

    def _digraph(self, a: str, b: str) -> float:
        shared = _stable(0, "dd", a, b).lognormvariate(0, 0.25)
        f = shared * _stable(self.seed, "dd", a, b).lognormvariate(0, self.digraph_spread * self.spread)
        if b == "space" or a == "space":
            f *= self.space_factor
        return self.base_dd * f

    def type_text(self, target: str, rng: random.Random, kind: str = "enroll",
                  text_id: str = "") -> KeystrokeRecorder:
        rec = KeystrokeRecorder(target, text_id, kind)
        events: list[tuple[float, int, str, str, str, int]] = []  # (t, orden, tipo, label, kind, key_id)
        order = 0
        t = 1000.0
        typed: list[str] = []
        snapshots: list[tuple[float, str]] = []
        prev = "space"

        last_release: dict[int, int] = {}

        def stroke(label, kind_, key_id, at, dwell):
            nonlocal order
            # una tecla física no puede volver a pulsarse sin haberse soltado
            if key_id in last_release and events[last_release[key_id]][0] >= at:
                old = events[last_release[key_id]]
                events[last_release[key_id]] = (at - 5.0,) + old[1:]
            events.append((at, order, "p", label, kind_, key_id)); order += 1
            last_release[key_id] = len(events)
            events.append((at + dwell, order, "r", label, kind_, key_id)); order += 1

        def noisy(x):
            return max(15.0, x * rng.lognormvariate(0, self.noise))

        for ch in target:
            base = ch if ch.lower() in "ñç" else unicodedata.normalize("NFD", ch)
            letter = base[0].lower()
            label = "space" if ch == " " else letter
            kind_ = SPACE if ch == " " else CHAR
            t += noisy(self._digraph(prev, label))
            if rng.random() < self.pause_p:
                t += rng.uniform(1600, 3000)
            if rng.random() < self.error_p and ch.isalpha():
                wrong = "x" if letter != "x" else "z"
                stroke(wrong, CHAR, ord(wrong), t, noisy(self._key_dwell(wrong)))
                typed.append(wrong); snapshots.append((t, "".join(typed)))
                t += noisy(self.reaction)
                stroke("backspace", BACKSPACE, 8, t, noisy(90))
                typed.pop(); snapshots.append((t, "".join(typed)))
                t += noisy(self.base_dd * 1.2)
            for mark in base[1:]:
                dead = _ACCENTS.get(mark, "dead")
                stroke(dead, DEAD, 1000, t, noisy(self._key_dwell(dead)))
                t += noisy(self._digraph(dead, label))
            if ch.isupper():
                right = rng.random() < self.right_shift
                shift_at = t - noisy(self.shift_lead)
                kd = noisy(self._key_dwell(label))
                stroke("shift_r" if right else "shift_l", MOD, 62 if right else 50,
                       shift_at, (t + kd + 20) - shift_at)
            stroke(label, kind_, ord(letter), t, noisy(self._key_dwell(label)))
            typed.append(ch); snapshots.append((t, "".join(typed)))
            prev = label

        events.sort()
        snap_i = 0
        for at, _, typ, label, kind_, key_id in events:
            while snap_i < len(snapshots) and snapshots[snap_i][0] < at:
                rec.text_changed(snapshots[snap_i][1]); snap_i += 1
            ns = int(at * 1e6)
            if typ == "p":
                rec.press(key_id, label, kind_, ns)
            else:
                rec.release(key_id, ns)
        for _, text in snapshots[snap_i:]:
            rec.text_changed(text)
        return rec
