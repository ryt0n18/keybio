"""Detección de muestras sospechosas (suplantación).

No es infalible, pero detecta los ataques más simples:

* **Ritmo robótico**: un programa que teclea solo suele hacerlo con
  intervalos casi idénticos; una persona varía muchísimo más.
* **Tiempos repetidos exactos**: pulsaciones con la misma duración al
  milisegundo una y otra vez (típico de herramientas de automatización).
* **Pulsaciones instantáneas**: teclas que se sueltan casi a la vez que se
  pulsan (< 8 ms), algo físicamente muy raro al escribir.
* **Réplica**: la muestra reproduce, con los mismos tiempos, otra muestra
  guardada del mismo texto (alguien grabó una sesión y la vuelve a enviar).
"""

from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass

from .capture import CHAR, SPACE, TYPING_KINDS, Sample
from .i18n import _

ROBOTIC_CV = 0.12          # coeficiente de variación del intervalo por debajo del cual es sospechoso
REPEATED_SHARE = 0.35      # proporción máxima de pulsaciones con la misma duración exacta (ms)
INSTANT_DWELL_MS = 8.0
INSTANT_SHARE = 0.25
REPLAY_MS = 2.0            # diferencia mediana máxima con una muestra guardada para considerarla réplica


@dataclass
class Finding:
    level: str      # "bad" (bloquea la aceptación) | "warn" (solo avisa)
    code: str
    message: str


def _intervals(sample: Sample) -> list[float]:
    keys = [k for k in sample.keystrokes if k.kind in (CHAR, SPACE)]
    return [b.press - a.press for a, b in zip(keys, keys[1:]) if 0 < b.press - a.press < 1500]


def check(sample: Sample, stored: list[Sample] = ()) -> list[Finding]:
    out: list[Finding] = []
    dd = _intervals(sample)
    if len(dd) >= 40:
        cv = statistics.pstdev(dd) / statistics.fmean(dd)
        if cv < ROBOTIC_CV:
            out.append(Finding("bad", "robotic",
                               _("Ritmo demasiado regular para una persona (variación {cv} %): "
                                 "posible escritura automática.", cv=f"{cv * 100:.0f}")))
    dwell = [k.dwell for k in sample.keystrokes if k.kind in TYPING_KINDS and k.dwell is not None]
    if len(dwell) >= 40:
        top = Counter(round(d) for d in dwell).most_common(1)[0][1]
        if top / len(dwell) > REPEATED_SHARE:
            out.append(Finding("bad", "repeated",
                               _("Muchas pulsaciones duran exactamente lo mismo: posible escritura automática.")))
        instant = sum(d < INSTANT_DWELL_MS for d in dwell)
        if instant / len(dwell) > INSTANT_SHARE:
            out.append(Finding("bad", "instant", _("Teclas que se sueltan instantáneamente: posible teclado virtual "
                                                   "o programa.")))
    for other in stored:
        if other.id == sample.id or other.text_id != sample.text_id or not sample.text_id:
            continue
        a = [k for k in sample.keystrokes if k.kind in TYPING_KINDS]
        b = [k for k in other.keystrokes if k.kind in TYPING_KINDS]
        if len(a) < 40 or abs(len(a) - len(b)) > 3:
            continue
        n = min(len(a), len(b))
        dpress = [abs((a[i].press - a[0].press) - (b[i].press - b[0].press)) for i in range(n)]
        if statistics.median(dpress) < REPLAY_MS * 5 and statistics.median(
                abs((a[i].dwell or 0) - (b[i].dwell or 0)) for i in range(n)) < REPLAY_MS:
            out.append(Finding("bad", "replay", _("La muestra reproduce con los mismos tiempos otra muestra "
                                                  "guardada: posible réplica.")))
            break
    if sample.blocked_keys >= 3:
        out.append(Finding("warn", "blocked", _("Se intentó pegar texto o editar fuera de orden {n} veces.",
                                                n=sample.blocked_keys)))
    return out


def is_blocking(findings: list[Finding]) -> bool:
    return any(f.level == "bad" for f in findings)
