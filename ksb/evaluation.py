"""Evaluación y calibración del sistema con las muestras guardadas.

* **Usuarios legítimos**: cada muestra de un usuario se aparta de su perfil
  (deja-uno-fuera) y se intenta identificar contra todos los perfiles. Se
  cuenta si se identifica bien, se rechaza o se confunde con otro usuario.
* **Impostores**: cada muestra de un usuario se presenta a los perfiles de
  los demás *sin el suyo*, como si fuera un desconocido. Lo correcto es que
  se responda "no registrado"; si algún perfil la acepta es una falsa
  aceptación.

Las distancias se expresan como proporción del umbral de cada perfil
(``distancia / umbral``): por debajo de 1 se acepta.

``calibrate`` reutiliza esos mismos ensayos para buscar el peso de fusión
(R/A frente a estadística) y la K del umbral que minimizan los errores con
los datos de *este* equipo, en lugar de los valores por defecto.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import matcher
from .features import SampleFeatures
from .i18n import _
from .matcher import Profile, identify

# (id, nombre, características[, sesiones])
UserData = tuple


def _unpack(u) -> tuple[str, str, list[SampleFeatures], list[str] | None]:
    return (u[0], u[1], u[2], u[3] if len(u) > 3 else None)


@dataclass
class EvalResult:
    users: int = 0
    genuine_total: int = 0
    genuine_correct: int = 0
    genuine_rejected: int = 0
    genuine_confused: int = 0
    impostor_total: int = 0
    impostor_accepted: int = 0
    genuine_ratios: list[float] = field(default_factory=list)
    impostor_ratios: list[float] = field(default_factory=list)

    @property
    def identification_rate(self) -> float | None:
        return self.genuine_correct / self.genuine_total if self.genuine_total else None

    @property
    def false_reject_rate(self) -> float | None:
        return self.genuine_rejected / self.genuine_total if self.genuine_total else None

    @property
    def false_accept_rate(self) -> float | None:
        return self.impostor_accepted / self.impostor_total if self.impostor_total else None


def _usable(users):
    out = []
    for u in users:
        uid, name, feats, sessions = _unpack(u)
        if len(feats) >= 2:
            out.append((uid, name, feats, sessions))
    return out


def _team(usable) -> dict[str, Profile]:
    full = {uid: Profile.build(uid, name, feats, sessions=sess) for uid, name, feats, sess in usable}
    matcher.share_spread(list(full.values()))
    return full


def _leave_one_out(uid, name, feats, sessions, i, team: dict[str, Profile]) -> Profile:
    rest = feats[:i] + feats[i + 1:]
    rest_s = (sessions[:i] + sessions[i + 1:]) if sessions else None
    own = Profile.build(uid, name, rest, sessions=rest_s)
    matcher.share_spread(list(team.values()), [own])
    return own


def evaluate(users: list[UserData], sensitivity="normal") -> EvalResult:
    res = EvalResult()
    usable = _usable(users)
    full = _team(usable)
    res.users = len(full)

    for uid, name, feats, sess in usable:
        if len(feats) < 3:          # hacen falta 2 muestras para el perfil + 1 de prueba
            continue
        others = [p for k, p in full.items() if k != uid]
        for i, f in enumerate(feats):
            own = _leave_one_out(uid, name, feats, sess, i, full)
            result = identify(f, [own] + others, sensitivity)
            mine = next((c for c in result.candidates if c.user_id == uid), None)
            if mine is None:
                continue
            res.genuine_total += 1
            res.genuine_ratios.append(mine.ratio)
            if result.best is None:
                res.genuine_rejected += 1
            elif result.best.user_id == uid:
                res.genuine_correct += 1
            else:
                res.genuine_confused += 1

    for uid, _name, feats, _sessions in usable:
        others = [p for k, p in full.items() if k != uid]
        if not others:
            continue
        for f in feats:
            result = identify(f, others, sensitivity)
            if not result.candidates:
                continue
            res.impostor_total += 1
            res.impostor_accepted += result.best is not None
            res.impostor_ratios.extend(c.ratio for c in result.candidates)
    return res


# --- calibración automática ---------------------------------------------------

@dataclass
class Trial:
    genuine: bool
    ra: float | None
    z: float | None
    profile: Profile        # su calibración (loo_parts) depende del peso de fusión
    cross_session: bool = False   # ensayo real de otro día (historial verificado)


@dataclass
class Calibration:
    weight: float                       # peso de R/A recomendado
    k: float                            # K recomendada
    far: float                          # falsas aceptaciones con la recomendación
    frr: float                          # falsos rechazos con la recomendación
    genuine: int
    impostor: int
    levels: dict[str, tuple[float, float]] = field(default_factory=dict)  # nivel -> (FAR, FRR) con el peso actual
    enough: bool = True
    message: str = ""


MIN_USERS = 3
MIN_GENUINE = 9
K_MIN = 1.0          # no bajar de "estricto": con pocos datos el mínimo exacto sobreajusta
SESSION_DRIFT = 0.06  # empeoramiento esperado de un día a otro si el perfil es de una sola sesión


def collect_trials(users: list[UserData]) -> list[Trial]:
    usable = _usable(users)
    full = _team(usable)
    trials: list[Trial] = []
    for uid, name, feats, sess in usable:
        others = [p for k, p in full.items() if k != uid]
        for i, f in enumerate(feats):
            if len(feats) >= 3:
                own = _leave_one_out(uid, name, feats, sess, i, full)
                d = own.distance(f)
                if d.total is not None:
                    trials.append(Trial(True, d.ra, d.z, own))
            for q in others:
                d = q.distance(f)
                if d.total is not None:
                    trials.append(Trial(False, d.ra, d.z, q))
    return trials


def _rates(trials: list[Trial], w: float, k: float, cache: dict) -> tuple[float, float]:
    fa = fr = ng = ni = 0
    for t in trials:
        key = (id(t.profile), w)
        if key not in cache:
            cache[key] = t.profile.stats_for(w)
        m, s, _ = cache[key]
        thr = m + k * max(s, matcher.S_MIN) + t.profile.slack()
        d = matcher.fuse(t.ra, t.z, w)
        if t.genuine and not t.cross_session:
            # los ensayos legítimos de una misma sesión son optimistas: se simula otro día
            # en la parte de la calibración del perfil que no se hizo entre sesiones
            d += SESSION_DRIFT * (1 - t.profile.cross_frac)
        if t.genuine:
            ng += 1
            fr += d > thr
        else:
            ni += 1
            fa += d <= thr
    return (fa / ni if ni else 0.0), (fr / ng if ng else 0.0)


def calibrate(users: list[UserData], trials: list[Trial] | None = None,
              extra: list[Trial] | None = None) -> Calibration:
    """Busca peso de fusión y K que minimizan FAR + FRR (a igualdad, menos FAR).

    ``extra``: ensayos reales del historial verificado por el usuario (otros días)."""
    trials = (collect_trials(users) if trials is None else trials) + list(extra or [])
    n_users = len(_usable(users))
    ng = sum(t.genuine for t in trials)
    ni = len(trials) - ng
    cache: dict = {}
    levels = {name: _rates(trials, matcher.W_RA, k, cache) for name, k in matcher.SENSITIVITY.items()}
    if n_users < MIN_USERS or ng < MIN_GENUINE or ni == 0:
        return Calibration(matcher.W_RA, matcher.AUTO_K, *levels.get("normal", (0.0, 0.0)), ng, ni, levels,
                           enough=False,
                           message=_("Hacen falta al menos {min} usuarios con 3 o más muestras "
                                     "(ahora: {users} usuarios, {genuine} ensayos legítimos).",
                                     min=MIN_USERS, users=n_users, genuine=ng))
    best = None
    for w10 in range(3, 10):                 # peso de R/A de 0.3 a 0.9
        w = w10 / 10
        for k10 in range(int(K_MIN * 10), 61, 2):   # K de K_MIN a 6
            k = k10 / 10
            far, frr = _rates(trials, w, k, cache)
            score = (far + frr, far, abs(w - matcher.W_RA), abs(k - 2.0))
            if best is None or score < best[0]:
                best = (score, w, k, far, frr)
    _score, w, k, far, frr = best
    return Calibration(w, k, far, frr, ng, ni, levels,
                       message=_("Calculado con {genuine} ensayos legítimos y {impostors} de impostores "
                                 "entre {users} usuarios.", genuine=ng, impostors=ni, users=n_users))
