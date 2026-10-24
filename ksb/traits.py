"""Rasgos de estilo normalizados (0-1) para comparar perfiles de un vistazo."""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Callable

from .i18n import N_


@dataclass(frozen=True)
class Trait:
    """``name``, ``unit`` y ``help`` están en español: se traducen con _() al mostrarlos."""
    key: str
    name: str
    unit: str
    low: float
    high: float
    get: Callable[[dict], float]
    help: str

    def normalize(self, value: float) -> float:
        return max(0.0, min(1.0, (value - self.low) / (self.high - self.low)))


TRAITS: list[Trait] = [
    Trait("speed", N_("Velocidad"), N_("puls./min"), 100, 600, lambda m: m["cpm"],
          N_("Pulsaciones por minuto descontando pausas largas.")),
    Trait("dwell", N_("Pulsación"), "ms", 50, 180, lambda m: m["dwell_mean"],
          N_("Tiempo medio que se mantiene pulsada una tecla.")),
    Trait("flight", N_("Vuelo"), "ms", -30, 250, lambda m: m["flight_mean"],
          N_("Tiempo medio entre soltar una tecla y pulsar la siguiente.")),
    Trait("overlap", N_("Solapamiento"), "%", 0, 50, lambda m: m["rollover_pct"],
          N_("Veces que se pulsa la siguiente tecla antes de soltar la anterior.")),
    Trait("regular", N_("Regularidad"), "%", 0, 100, lambda m: max(m["consistency"], 0.0),
          N_("Lo constante que es el ritmo (100 % = metrónomo).")),
    Trait("errors", N_("Errores"), N_("/100 car."), 0, 12,
          lambda m: 100.0 * m["errors_committed"] / max(m["chars"], 1),
          N_("Caracteres erróneos tecleados por cada 100 caracteres.")),
]


def trait_values(metrics: list[dict]) -> list[tuple[Trait, float, float]]:
    """Media de cada rasgo sobre varias muestras: (rasgo, valor real, valor 0-1)."""
    out = []
    for t in TRAITS:
        raw = statistics.fmean(t.get(m) for m in metrics) if metrics else 0.0
        out.append((t, raw, t.normalize(raw)))
    return out
