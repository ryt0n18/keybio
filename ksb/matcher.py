"""Comparación de muestras, perfiles de usuario e identificación.

La distancia entre una muestra X y el perfil de un usuario combina dos
familias de medidas, ambas en el rango [0, 1]:

1. **Medidas R y A (Gunetti y Picardi, 2005)** para texto libre. Se calculan
   entre X y cada muestra de registro del usuario usando los dígrafos y
   trígrafos que tienen en común:

   * R (relativa): ordena los n-gramas compartidos por duración en cada
     muestra y mide el "desorden" entre ambas ordenaciones. Captura qué
     combinaciones de teclas son rápidas o lentas para la persona,
     independientemente de su velocidad global.
   * A (absoluta): proporción de n-gramas compartidos cuya duración difiere
     más de un factor ``t`` entre ambas muestras.

2. **Distancia estadística (Manhattan escalada)** sobre características
   globales (velocidad, tiempos de pulsación, solapamiento, uso de shift,
   forma de corregir...) y el tiempo de pulsación de cada tecla, frente a la
   media y dispersión del usuario.

Cada usuario se calibra con validación "deja-uno-fuera" sobre sus propias
muestras: se obtiene la distancia típica de la persona consigo misma (m) y
su variación (s). Una muestra se acepta como de ese usuario si su distancia
no supera ``m + K·s + margen``; si ningún usuario la acepta, la persona se
considera no registrada. Con pocas muestras, s se completa con la variación
típica del resto de perfiles del equipo (``share_spread``).
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field

from .features import SampleFeatures, median, merge_dwell
from .i18n import N_

# --- parámetros del modelo -------------------------------------------------

MIN_SHARED = 10        # n-gramas compartidos mínimos para calcular R/A
USE_UD = True          # incluir los tiempos de vuelo por dígrafo en R/A
UD_TOLERANCE_MS = 30.0
A_THRESHOLD = 1.25     # factor de tolerancia de la medida A
W_RA = 0.55            # peso de R/A en la distancia final
W_Z = 0.45             # peso de la distancia estadística
Z_CAP = 6.0            # límite por característica para que ninguna domine

S_MIN = 0.035          # dispersión mínima asumida en la calibración
S_FALLBACK = S_MIN * 2  # dispersión con menos de 3 distancias de calibración y sin datos del equipo
PRIOR_DOF = 2          # peso (grados de libertad) de la dispersión del equipo frente a la propia
PRIOR_MIN_DOF = 4      # grados de libertad mínimos para fiarse de la dispersión del equipo
SLACK = 0.06           # margen extra: la prueba se hace otro día y con otro texto
SLACK_MULTI = 0.03     # margen si toda la calibración se hizo apartando otra sesión (m ya es realista)

SENSITIVITY = {        # K del umbral m + K·s + margen
    "estricto": 1.0,
    "normal": 2.0,
    "permisivo": 3.0,
}
AUTO_K = 2.0           # K de la sensibilidad "auto" (la fija la calibración con datos reales)

# Decisión progresiva: mientras se escribe se compara cada pocas pulsaciones y se termina en
# cuanto el resultado está claro. Con poco texto la distancia de una persona a su propio perfil
# crece, pero la de las demás no baja, así que no basta con ampliar el umbral: se exige un
# parecido claramente mejor que el umbral y ventaja sobre el segundo. En las pruebas se escribe
# bastante menos texto sin ningún error más que con el texto completo.
EARLY_MIN_KEYS = 60    # pulsaciones mínimas (también las de una muestra válida)
EARLY_ACCEPT = 0.85    # ratio distancia/umbral máximo para aceptar antes de terminar
EARLY_MARGIN = 0.20    # ventaja mínima (en ratio) sobre el segundo más parecido
EARLY_REJECT = 1.40    # si todos quedan por encima, «no registrado» antes de terminar


def resolve_k(sensitivity) -> float:
    """Convierte una sensibilidad (nombre, "auto" o número) en el factor K del umbral."""
    if isinstance(sensitivity, (int, float)):
        return float(sensitivity)
    if sensitivity == "auto":
        return AUTO_K
    return SENSITIVITY.get(sensitivity, SENSITIVITY["normal"])


def set_fusion(w_ra: float, auto_k: float | None = None) -> None:
    """Cambia el peso de R/A frente a la distancia estadística (y la K automática)."""
    global W_RA, W_Z, AUTO_K
    W_RA = max(0.0, min(1.0, w_ra))
    W_Z = 1.0 - W_RA
    if auto_k is not None:
        AUTO_K = auto_k


def fuse(ra: float | None, z: float | None, w_ra: float | None = None) -> float | None:
    w = W_RA if w_ra is None else w_ra
    if ra is not None and z is not None:
        return w * ra + (1 - w) * z
    return ra if ra is not None else z

# nombre -> (suelo absoluto, suelo relativo, peso, descripción en español: se traduce al mostrarla)
GLOBAL_SPEC: dict[str, tuple[float, float, float, str]] = {
    "dwell_med":     (6.0, 0.08, 1.5, N_("Tiempo de pulsación (mediana)")),
    "dwell_iqr":     (6.0, 0.15, 0.7, N_("Variabilidad de pulsación")),
    "dd_med":        (10.0, 0.08, 1.2, N_("Intervalo entre teclas (mediana)")),
    "dd_iqr":        (15.0, 0.15, 0.7, N_("Variabilidad del intervalo")),
    "ud_med":        (12.0, 0.15, 1.2, N_("Tiempo de vuelo (mediana)")),
    "overlap":       (0.05, 0.0, 1.2, N_("Solapamiento de teclas")),
    "space_dwell":   (8.0, 0.10, 1.0, N_("Pulsación de la barra espaciadora")),
    "dd_to_space":   (12.0, 0.10, 0.8, N_("Letra → espacio")),
    "dd_from_space": (12.0, 0.10, 0.8, N_("Espacio → letra")),
    "speed_cpm":     (15.0, 0.06, 1.2, N_("Velocidad (pulsaciones/min)")),
    "pause_rate":    (1.0, 0.30, 0.4, N_("Frecuencia de pausas")),
    "bs_rate":       (1.5, 0.30, 0.4, N_("Frecuencia de retrocesos")),
    "err_rate":      (1.5, 0.30, 0.4, N_("Frecuencia de errores")),
    "shift_right":   (0.15, 0.0, 1.0, N_("Uso del shift derecho")),
    "shift_lead":    (15.0, 0.12, 0.8, N_("Shift → letra")),
    "shift_hold":    (15.0, 0.12, 0.6, N_("Duración del shift")),
    "bs_dwell":      (10.0, 0.12, 0.4, N_("Pulsación del retroceso")),
    "bs_latency":    (30.0, 0.15, 0.4, N_("Reacción ante un error")),
}

DWELL_MIN_TEST = 3
DWELL_MIN_PROFILE = 6
DWELL_SD_FLOOR = 10.0


# --- medidas R y A -----------------------------------------------------------

def _medians(d: dict, min_count: int = 1) -> dict:
    return {k: median(v) for k, v in d.items() if len(v) >= min_count}


def r_measure(a: dict, b: dict) -> float | None:
    """Desorden normalizado entre las ordenaciones de los n-gramas compartidos."""
    shared = a.keys() & b.keys()
    n = len(shared)
    if n < MIN_SHARED:
        return None
    rank_a = {k: i for i, k in enumerate(sorted(shared, key=lambda k: (a[k], k)))}
    rank_b = {k: i for i, k in enumerate(sorted(shared, key=lambda k: (b[k], k)))}
    disorder = sum(abs(rank_a[k] - rank_b[k]) for k in shared)
    max_disorder = (n * n) / 2 if n % 2 == 0 else (n * n - 1) / 2
    return disorder / max_disorder


def a_measure(a: dict, b: dict, t: float = A_THRESHOLD) -> float | None:
    """Proporción de n-gramas compartidos con duraciones no similares."""
    shared = a.keys() & b.keys()
    if len(shared) < MIN_SHARED:
        return None
    similar = 0
    for k in shared:
        x, y = a[k], b[k]
        if x > 0 and y > 0 and max(x, y) / min(x, y) <= t:
            similar += 1
    return 1.0 - similar / len(shared)


def a_abs_measure(a: dict, b: dict, tol_ms: float = UD_TOLERANCE_MS, rel: float = 0.25) -> float | None:
    """Como A, pero con tolerancia absoluta: sirve para tiempos de vuelo, que pueden ser negativos."""
    shared = a.keys() & b.keys()
    if len(shared) < MIN_SHARED:
        return None
    similar = sum(abs(a[k] - b[k]) <= max(tol_ms, rel * max(abs(a[k]), abs(b[k]))) for k in shared)
    return 1.0 - similar / len(shared)


@dataclass
class _Compact:
    """Medianas por n-grama de una muestra, precalculadas para comparar rápido."""
    di: dict
    tri: dict
    dwell: dict
    ud: dict

    @classmethod
    def of(cls, f: SampleFeatures) -> "_Compact":
        c = f.cache.get("compact")
        if c is None:
            c = f.cache["compact"] = cls(_medians(f.di), _medians(f.tri), _medians(f.dwell),
                                         _medians(f.di_ud))
        return c


def ra_distance(x: _Compact, y: _Compact) -> float | None:
    parts = [
        r_measure(x.di, y.di),
        r_measure(x.tri, y.tri),
        a_measure(x.di, y.di),
        a_measure(x.tri, y.tri),
        a_measure(x.dwell, y.dwell),
    ]
    if USE_UD:   # tiempo de vuelo por dígrafo (soltar → pulsar)
        parts += [r_measure(x.ud, y.ud), a_abs_measure(x.ud, y.ud)]
    parts = [p for p in parts if p is not None]
    return statistics.fmean(parts) if parts else None


# --- perfil estadístico -----------------------------------------------------

def _robust_sd(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    med = statistics.median(values)
    mad = statistics.median(abs(v - med) for v in values)
    sd = 1.4826 * mad
    return sd if sd > 0 else statistics.pstdev(values)


@dataclass
class Profile:
    user_id: str
    name: str
    features: list[SampleFeatures]
    compact: list[_Compact] = field(default_factory=list)
    global_stats: dict[str, tuple[float, float]] = field(default_factory=dict)
    dwell_stats: dict[str, tuple[float, float, int]] = field(default_factory=dict)
    sessions: list[str] = field(default_factory=list)
    m: float = 0.0               # distancia típica consigo mismo
    s: float = 0.0               # variación de esa distancia
    loo: list[float] = field(default_factory=list)
    loo_parts: list[tuple[float | None, float | None]] = field(default_factory=list)
    multi_session: bool = False
    cross_frac: float = 0.0      # parte de la calibración hecha apartando otra sesión
    population: list["Profile"] = field(default_factory=list, repr=False, compare=False)
    _w: float = -1.0             # peso con el que se calcularon m y s

    @classmethod
    def build(cls, user_id: str, name: str, features: list[SampleFeatures],
              calibrate: bool = True, sessions: list[str] | None = None) -> "Profile":
        p = cls(user_id, name, features, [_Compact.of(f) for f in features])
        if sessions and len(sessions) == len(features):
            p.sessions = list(sessions)
        for key in GLOBAL_SPEC:
            vals = [f.globals[key] for f in features if key in f.globals]
            if vals:
                mu = statistics.fmean(vals)
                sd = statistics.stdev(vals) if len(vals) >= 2 else 0.0
                p.global_stats[key] = (mu, sd)
        for label, vals in merge_dwell(features).items():
            if len(vals) >= DWELL_MIN_PROFILE:
                p.dwell_stats[label] = (statistics.median(vals), _robust_sd(vals), len(vals))
        if calibrate:
            p._calibrate()
        return p

    def _calibrate(self) -> None:
        """Deja-uno-fuera. Con varias sesiones se aparta la sesión entera de la muestra
        evaluada: así la distancia típica refleja cómo cambia la persona de un día a otro.
        Si las otras sesiones no llegan a 2 muestras se aparta solo esa muestra, y
        ``cross_frac`` recoge qué parte de la calibración fue realmente entre sesiones."""
        n = len(self.features)
        self.loo_parts = []
        self.multi_session = len(set(self.sessions)) >= 2
        cross = 0
        for i in range(n if n >= 2 else 0):
            rest = []
            if self.multi_session:
                rest = [f for j, f in enumerate(self.features) if self.sessions[j] != self.sessions[i]]
            crossed = len(rest) >= 2
            if not crossed:
                rest = self.features[:i] + self.features[i + 1:]
            sub = Profile.build(self.user_id, self.name, rest, calibrate=False)
            d = sub.distance(self.features[i])
            if d.total is not None:
                self.loo_parts.append((d.ra, d.z))
                cross += crossed
        self.cross_frac = cross / len(self.loo_parts) if self.loo_parts else 0.0
        self._update_stats()

    def stats_for(self, w_ra: float) -> tuple[float, float, list[float]]:
        """(m, s, distancias) de la calibración con un peso de fusión dado."""
        loo = [d for ra, z in self.loo_parts if (d := fuse(ra, z, w_ra)) is not None]
        if not loo:   # sin datos suficientes: valores conservadores
            return 0.30, 0.06, []
        return statistics.fmean(loo), self._spread(loo, w_ra), loo

    def _spread(self, loo: list[float], w_ra: float) -> float:
        """Variación de la distancia consigo mismo. Con 3-4 muestras la propia estimación es
        muy ruidosa y con 2 no existe: se combina con la del resto del equipo, si la hay,
        en lugar de suponer un valor fijo."""
        own = statistics.stdev(loo) if len(loo) >= 3 else None
        prior = pooled_spread(self.population, w_ra, exclude=self.user_id)
        if prior is None:
            return S_FALLBACK if own is None else own
        if own is None:
            return prior
        dof = len(loo) - 1
        return math.sqrt((dof * own ** 2 + PRIOR_DOF * prior ** 2) / (dof + PRIOR_DOF))

    def _update_stats(self) -> None:
        self.m, self.s, self.loo = self.stats_for(W_RA)
        self._w = W_RA

    def slack(self) -> float:
        """Margen por la deriva de un día a otro: se reduce en la medida en que m ya se
        midió apartando otra sesión."""
        return SLACK + (SLACK_MULTI - SLACK) * self.cross_frac

    def threshold(self, sensitivity="normal") -> float:
        if self._w != W_RA:          # el peso de fusión cambió (calibración automática)
            self._update_stats()
        return self.m + resolve_k(sensitivity) * max(self.s, S_MIN) + self.slack()

    # -- distancias ---------------------------------------------------------
    def z_scores(self, f: SampleFeatures) -> tuple[dict[str, float], dict[str, float]]:
        """Puntuaciones z por característica global y por tecla."""
        zg: dict[str, float] = {}
        for key, (mu, sd) in self.global_stats.items():
            if key not in f.globals:
                continue
            abs_floor, rel_floor, _, _ = GLOBAL_SPEC[key]
            sd_eff = math.sqrt(sd ** 2 + abs_floor ** 2 + (rel_floor * abs(mu)) ** 2)
            zg[key] = min(abs(f.globals[key] - mu) / sd_eff, Z_CAP)
        zd: dict[str, float] = {}
        for label, vals in f.dwell.items():
            if len(vals) < DWELL_MIN_TEST or label not in self.dwell_stats:
                continue
            med_p, sd_p, _ = self.dwell_stats[label]
            zd[label] = min(abs(statistics.median(vals) - med_p) / max(sd_p, DWELL_SD_FLOOR), Z_CAP)
        return zg, zd

    def z_distance(self, f: SampleFeatures) -> float | None:
        zg, zd = self.z_scores(f)
        parts, weights = [], []
        if zg:
            w = [GLOBAL_SPEC[k][2] for k in zg]
            parts.append(sum(z * wi for z, wi in zip(zg.values(), w)) / sum(w))
            weights.append(0.6)
        if zd:
            w = [min(len(f.dwell[k]), 10) for k in zd]
            parts.append(sum(z * wi for z, wi in zip(zd.values(), w)) / sum(w))
            weights.append(0.4)
        if not parts:
            return None
        z = sum(p * w for p, w in zip(parts, weights)) / sum(weights)
        return z / (1.0 + z)

    def distance(self, f: SampleFeatures) -> "Distance":
        cx = _Compact.of(f)
        ras = [d for c in self.compact if (d := ra_distance(cx, c)) is not None]
        ra = statistics.fmean(ras) if ras else None
        z = self.z_distance(f)
        return Distance(fuse(ra, z), ra, z)


def pooled_spread(profiles: list[Profile], w_ra: float, exclude: str | None = None) -> float | None:
    """Variación conjunta (ponderada por grados de libertad) de los perfiles con al menos
    3 distancias de calibración, sin contar al usuario ``exclude``."""
    num = dof = 0.0
    for p in profiles:
        if p.user_id == exclude:
            continue
        loo = [d for ra, z in p.loo_parts if (d := fuse(ra, z, w_ra)) is not None]
        if len(loo) >= 3:
            num += (len(loo) - 1) * statistics.variance(loo)
            dof += len(loo) - 1
    return math.sqrt(num / dof) if dof >= PRIOR_MIN_DOF else None


def share_spread(population: list[Profile], targets: list[Profile] | None = None) -> None:
    """Da a cada perfil (o solo a ``targets``) la variación típica del resto del equipo."""
    for p in population if targets is None else targets:
        p.population = population
        p._update_stats()


@dataclass
class Distance:
    total: float | None
    ra: float | None
    z: float | None


# --- identificación -------------------------------------------------------

@dataclass
class Candidate:
    user_id: str
    name: str
    distance: float
    threshold: float
    m: float
    ra: float | None
    z: float | None
    s: float = 0.0

    @property
    def ratio(self) -> float:
        return self.distance / self.threshold if self.threshold > 0 else math.inf

    @property
    def accepted(self) -> bool:
        return self.distance <= self.threshold

    @property
    def confidence(self) -> float:
        """0-100. 100 = tan parecido como sus propias muestras; 50 = en el umbral."""
        span = max(self.threshold - self.m, 1e-6)
        return max(0.0, min(1.0, 0.5 + (self.threshold - self.distance) / (2 * span))) * 100


@dataclass
class Identification:
    candidates: list[Candidate]
    best: Candidate | None
    ambiguous: bool = False
    sensitivity: str | float = "normal"

    @property
    def is_unknown(self) -> bool:
        return self.best is None


def identify(f: SampleFeatures, profiles: list[Profile], sensitivity="normal") -> Identification:
    cands = []
    for p in profiles:
        d = p.distance(f)
        if d.total is None:
            continue
        cands.append(Candidate(p.user_id, p.name, d.total, p.threshold(sensitivity), p.m, d.ra, d.z, p.s))
    cands.sort(key=lambda c: c.ratio)
    accepted = [c for c in cands if c.accepted]
    best = accepted[0] if accepted else None
    ambiguous = len(accepted) >= 2 and accepted[1].ratio - accepted[0].ratio < 0.08
    return Identification(cands, best, ambiguous, sensitivity)


def early_decision(result: Identification, typed_keys: int, claimed_id: str | None = None) -> str | None:
    """"accept", "reject" o None (hace falta seguir escribiendo) para una muestra a medio escribir.

    En verificación (``claimed_id``) se acepta solo si el perfil indicado es claramente el más
    parecido, y se rechaza en cuanto queda lejos de su umbral."""
    if typed_keys < EARLY_MIN_KEYS or not result.candidates:
        return None
    cands = result.candidates          # ordenados por ratio
    best = cands[0]
    second = cands[1].ratio if len(cands) > 1 else math.inf
    clear = best.ratio <= EARLY_ACCEPT and second - best.ratio >= EARLY_MARGIN
    if claimed_id is not None:
        claimed = next((c for c in cands if c.user_id == claimed_id), None)
        if claimed is None:
            return None
        if clear and best is claimed:
            return "accept"
        return "reject" if claimed.ratio >= EARLY_REJECT else None
    if clear:
        return "accept"
    return "reject" if best.ratio >= EARLY_REJECT else None
