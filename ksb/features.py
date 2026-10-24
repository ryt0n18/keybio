"""Extracción de características de dinámica de tecleo.

Todas las características son *independientes del texto*: se calculan sobre
teclas, dígrafos y trígrafos, de modo que una muestra de un texto puede
compararse con otra de un texto distinto.

Terminología (tiempos en milisegundos):

* dwell / tiempo de pulsación: liberación - pulsación de una misma tecla.
* DD (down-down): pulsación de la tecla 2 - pulsación de la tecla 1.
* UD (up-down) / tiempo de vuelo: pulsación de la tecla 2 - liberación de la
  tecla 1. Es negativo cuando se solapan (se pulsa antes de soltar la anterior).
"""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .capture import BACKSPACE, CHAR, MOD, SPACE, TYPING_KINDS, Sample

PAUSE_MS = 1500.0   # intervalos mayores se consideran pausas y no se usan en dígrafos

Ngram = tuple[str, ...]


def median(values) -> float | None:
    values = list(values)
    return statistics.median(values) if values else None


def iqr(values) -> float | None:
    values = sorted(values)
    if len(values) < 4:
        return None
    q = statistics.quantiles(values, n=4)
    return q[2] - q[0]


@dataclass
class SampleFeatures:
    dwell: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    di: dict[Ngram, list[float]] = field(default_factory=lambda: defaultdict(list))
    di_ud: dict[Ngram, list[float]] = field(default_factory=lambda: defaultdict(list))
    tri: dict[Ngram, list[float]] = field(default_factory=lambda: defaultdict(list))
    globals: dict[str, float] = field(default_factory=dict)
    metrics: dict[str, object] = field(default_factory=dict)
    rhythm: list[float] = field(default_factory=list)   # DD a lo largo del texto
    cache: dict = field(default_factory=dict, repr=False, compare=False)


def _typing_chains(sample: Sample) -> list[list]:
    """Divide la secuencia en cadenas de teclas de escritura sin correcciones.

    Los modificadores (shift...) no rompen la cadena; un retroceso u otra
    tecla especial sí, porque el ritmo alrededor de una corrección no es el
    ritmo natural de la persona.
    """
    chains: list[list] = [[]]
    for ks in sample.keystrokes:
        if ks.kind in TYPING_KINDS:
            chains[-1].append(ks)
        elif ks.kind == MOD:
            continue
        elif chains[-1]:
            chains.append([])
    return [c for c in chains if len(c) >= 2]


def extract(sample: Sample, light: bool = False) -> SampleFeatures:
    """Características de una muestra. ``light`` omite la comparación con el texto
    objetivo (distancia de edición), útil para identificar en directo una muestra parcial."""
    f = SampleFeatures()
    keys = sample.keystrokes

    for ks in keys:
        d = ks.dwell
        if d is not None and 0 < d < 1000:
            f.dwell[ks.label].append(d)

    dd_char, ud_char, overlaps, pairs = [], [], 0, 0
    dd_to_space, dd_from_space = [], []
    pauses = 0
    for chain in _typing_chains(sample):
        for a, b in zip(chain, chain[1:]):
            dd = b.press - a.press
            if dd <= 0:
                continue
            f.rhythm.append(dd)
            if dd > PAUSE_MS:
                pauses += 1
                continue
            f.di[(a.label, b.label)].append(dd)
            if a.release is not None:
                ud = b.press - a.release
                f.di_ud[(a.label, b.label)].append(ud)
                pairs += 1
                overlaps += ud < 0
                if a.kind == CHAR and b.kind == CHAR:
                    ud_char.append(ud)
            if a.kind == CHAR and b.kind == CHAR:
                dd_char.append(dd)
            elif a.kind == CHAR and b.kind == SPACE:
                dd_to_space.append(dd)
            elif a.kind == SPACE and b.kind == CHAR:
                dd_from_space.append(dd)
        for a, b, c in zip(chain, chain[1:], chain[2:]):
            if 0 < b.press - a.press <= PAUSE_MS and 0 < c.press - b.press <= PAUSE_MS:
                f.tri[(a.label, b.label, c.label)].append(c.press - a.press)

    char_dwell = [d for ks in keys if ks.kind == CHAR and (d := ks.dwell) is not None and 0 < d < 1000]
    space_dwell = f.dwell.get("space", [])

    # Mayúsculas: lado del shift, adelanto y duración
    shifts = [ks for ks in keys if ks.label in ("shift_l", "shift_r")]
    shift_lead, shift_hold = [], []
    for i, ks in enumerate(keys):
        if ks.label not in ("shift_l", "shift_r"):
            continue
        if ks.dwell is not None and 0 < ks.dwell < 2000:
            shift_hold.append(ks.dwell)
        nxt = next((k for k in keys[i + 1:] if k.kind == CHAR), None)
        if nxt is not None and 0 < nxt.press - ks.press < 1000:
            shift_lead.append(nxt.press - ks.press)

    # Retrocesos: tiempo de reacción ante un error
    bs_latency = []
    for prev, ks in zip(keys, keys[1:]):
        if ks.kind == BACKSPACE and prev.kind != BACKSPACE and 0 < ks.press - prev.press < 3000:
            bs_latency.append(ks.press - prev.press)
    backspaces = sum(ks.kind == BACKSPACE for ks in keys)
    typing_keys = sum(ks.kind in TYPING_KINDS for ks in keys)

    # Tiempo activo: duración total sin el exceso de las pausas largas
    duration = sample.duration_ms
    excess = sum(dd - PAUSE_MS for dd in f.rhythm if dd > PAUSE_MS)
    active = max(duration - excess, 1.0)

    g = f.globals

    def put(name, value):
        if value is not None:
            g[name] = float(value)

    put("dwell_med", median(char_dwell))
    put("dwell_iqr", iqr(char_dwell))
    put("dd_med", median(dd_char))
    put("dd_iqr", iqr(dd_char))
    put("ud_med", median(ud_char))
    put("overlap", overlaps / pairs if pairs >= 10 else None)
    put("space_dwell", median(space_dwell))
    put("dd_to_space", median(dd_to_space))
    put("dd_from_space", median(dd_from_space))
    put("speed_cpm", 60000.0 * typing_keys / active if typing_keys >= 20 else None)
    if typing_keys >= 20:
        put("pause_rate", 100.0 * pauses / typing_keys)
        put("bs_rate", 100.0 * backspaces / typing_keys)
        if not sample.free:   # en texto libre no se sabe qué era un error
            put("err_rate", 100.0 * sample.errors_committed / max(len(sample.typed_norm), 1))
    if len(shifts) >= 2:
        put("shift_right", sum(s.label == "shift_r" for s in shifts) / len(shifts))
    put("shift_lead", median(shift_lead))
    put("shift_hold", median(shift_hold))
    put("bs_dwell", median(f.dwell.get("backspace", [])))
    put("bs_latency", median(bs_latency))

    # Métricas para mostrar al usuario
    minutes = max(duration / 60000.0, 1e-9)
    typed_len = len(sample.typed_norm)
    uncorrected = 0 if light else sample.uncorrected_errors
    all_dd = [dd for dd in f.rhythm if dd <= PAUSE_MS]
    di_medians = {k: median(v) for k, v in f.di.items() if len(v) >= 2 and all(len(x) == 1 for x in k)}
    error_chars = Counter(
        sample.target[p].lower() for p in sample.error_positions if p < len(sample.target)
    )
    f.metrics = {
        "duration_s": duration / 1000.0,
        "chars": typed_len,
        "keystrokes": len(keys),
        "wpm": (typed_len / 5.0) / minutes,
        "net_wpm": max(0.0, (typed_len / 5.0 - uncorrected) / minutes),
        "cpm": 60000.0 * typing_keys / active,
        "accuracy": 100.0 if light else sample.accuracy * 100.0,
        "errors_committed": sample.errors_committed,
        "errors_uncorrected": uncorrected,
        "errors_corrected": max(0, sample.errors_committed - uncorrected),
        "backspaces": backspaces,
        "pauses": pauses,
        "autorepeats": sample.autorepeats,
        "blocked": sample.blocked_keys,
        "dwell_mean": statistics.fmean(char_dwell) if char_dwell else 0.0,
        "dwell_med": g.get("dwell_med", 0.0),
        "flight_mean": statistics.fmean(ud_char) if ud_char else 0.0,
        "dd_mean": statistics.fmean(all_dd) if all_dd else 0.0,
        "rollover_pct": 100.0 * overlaps / pairs if pairs else 0.0,
        # regularidad robusta: 100 % = ritmo constante; 0 % = dispersión (IQR) de 1,5 veces la mediana o más
        "consistency": (100.0 * max(0.0, 1.0 - (iqr(all_dd) / statistics.median(all_dd)) / 1.5)
                        if len(all_dd) >= 4 else 0.0),
        "shift_left": sum(s.label == "shift_l" for s in shifts),
        "shift_right": sum(s.label == "shift_r" for s in shifts),
        "slowest_digraphs": sorted(di_medians.items(), key=lambda kv: -kv[1])[:5],
        "fastest_digraphs": sorted(di_medians.items(), key=lambda kv: kv[1])[:5],
        "error_chars": error_chars.most_common(5),
        "error_counts": dict(error_chars),
    }
    return f


def features_of(samples: list[Sample]) -> list[SampleFeatures]:
    return [extract(s) for s in samples]


def merge_dwell(features: list[SampleFeatures]) -> dict[str, list[float]]:
    merged: dict[str, list[float]] = defaultdict(list)
    for f in features:
        for k, v in f.dwell.items():
            merged[k].extend(v)
    return merged
