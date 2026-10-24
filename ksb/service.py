"""Lógica de aplicación: une almacenamiento, características y comparación."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from . import matcher
from .capture import TYPING_KINDS, Sample
from .evaluation import Calibration, Trial, UserData, calibrate
from .features import SampleFeatures, extract
from . import i18n
from .i18n import N_, _, _n
from .liveness import Finding, check, is_blocking
from .matcher import Candidate, Identification, Profile, identify
from .storage import Storage, User, clean_name

MAX_PROFILE_SAMPLES = 12   # tamaño máximo del perfil
MAX_ENROLL_IN_PROFILE = 6  # muestras de registro que se conservan siempre (ancla contra la deriva)
MIN_TYPING_KEYS = 60
MIN_PROFILE_SAMPLES = 2
SESSION_GAP = timedelta(hours=2)
ADAPT_MIN_CONFIDENCE = 75.0
ADAPT_MIN_KEYS = 200       # una muestra más corta (decisión rápida) no entra al perfil
DEFAULT_WEIGHT = 0.55
SENSITIVITY_NAMES = {"estricto": N_("estricto"), "normal": N_("normal"), "permisivo": N_("permisivo")}
ACCESS_OUTCOMES = ("passed", "failed", "abandoned")   # cómo terminó la verificación adicional


def _when(iso: str) -> datetime | None:
    try:
        return datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None


def sessions_of(samples: list[Sample]) -> list[str]:
    """Agrupa las muestras en sesiones: una pausa de más de 2 horas abre una sesión nueva."""
    order = sorted(range(len(samples)), key=lambda i: samples[i].created or "")
    labels = [""] * len(samples)
    current, last = 0, None
    for i in order:
        t = _when(samples[i].created)
        if last is not None and (t is None or t - last > SESSION_GAP):
            current += 1
        labels[i] = f"s{current}"
        last = t or last
    return labels


class BiometricService:
    def __init__(self, storage: Storage | None = None):
        self.storage = storage or Storage()
        self.settings = self.storage.load_settings()
        self._cache: dict[str, tuple[tuple, Profile]] = {}
        self._team_key: tuple = ()
        self._feat_cache: dict[str, SampleFeatures] = {}
        self.apply_model_settings()

    # -- ajustes ------------------------------------------------------------
    def save_settings(self) -> None:
        self.storage.save_settings(self.settings)
        self.apply_model_settings()

    def apply_model_settings(self) -> None:
        if self.settings.get("sensitivity") == "auto":
            matcher.set_fusion(float(self.settings.get("auto_weight", DEFAULT_WEIGHT)),
                               float(self.settings.get("auto_k", 2.0)))
        else:
            matcher.set_fusion(DEFAULT_WEIGHT)

    @property
    def sensitivity(self) -> str:
        return self.settings.get("sensitivity", "normal")

    @property
    def keyboard_layout(self) -> str:
        """Teclado en pantalla: el de Ajustes o, en «automático», el habitual del idioma de la interfaz."""
        value = self.settings.get("keyboard_layout", "auto")
        return i18n.KEYBOARDS.get(i18n.language(), "us") if value == "auto" else value

    @property
    def text_language(self) -> str:
        """Idioma de los textos para escribir: el de Ajustes o, en «automático», el de la interfaz."""
        value = self.settings.get("text_language", "auto")
        return i18n.language() if value == "auto" else value

    @property
    def sensitivity_label(self) -> str:
        if self.sensitivity == "auto":
            return _("automática (K={k})", k=f"{matcher.AUTO_K:.1f}")
        return _(SENSITIVITY_NAMES.get(self.sensitivity, self.sensitivity))

    # -- usuarios y perfiles ------------------------------------------------
    def users(self) -> list[User]:
        return self.storage.list_users()

    def features(self, sample: Sample) -> SampleFeatures:
        f = self._feat_cache.get(sample.id)
        if f is None:
            f = self._feat_cache[sample.id] = extract(sample)
        return f

    @staticmethod
    def profile_samples(user: User) -> list[Sample]:
        """Muestras que forman el perfil: las de registro más recientes (ancla) y las más
        recientes de comprobaciones/adaptación, hasta el máximo."""
        enroll = [s for s in user.samples if s.kind == "enroll"][-MAX_ENROLL_IN_PROFILE:]
        others = [s for s in user.samples if s.kind != "enroll"]
        room = MAX_PROFILE_SAMPLES - len(enroll)
        chosen = {s.id for s in enroll} | {s.id for s in (others[-room:] if room > 0 else [])}
        return [s for s in user.samples if s.id in chosen]

    def _build_profile(self, user: User) -> Profile:
        samples = self.profile_samples(user)
        key = tuple(s.id for s in samples) + (user.name,)
        cached = self._cache.get(user.id)
        if cached and cached[0] == key:
            return cached[1]
        p = Profile.build(user.id, user.name, [self.features(s) for s in samples],
                          sessions=sessions_of(samples))
        self._cache[user.id] = (key, p)
        return p

    def profile(self, user: User) -> Profile:
        """Perfil de un usuario, con la variación del equipo ya compartida (el umbral que
        se muestra es el mismo que se usa al identificar)."""
        team = self.profiles()
        return next((p for p in team if p.user_id == user.id), None) or self._build_profile(user)

    def profiles(self, exclude: str | None = None) -> list[Profile]:
        team = [self._build_profile(u) for u in self.users() if len(u.samples) >= MIN_PROFILE_SAMPLES]
        key = tuple(self._cache[p.user_id][0] for p in team)
        if key != self._team_key:   # ha cambiado algún perfil: se recalcula la variación del equipo
            matcher.share_spread(team)
            self._team_key = key
        return [p for p in team if p.user_id != exclude]

    def create_user(self, name: str, samples: list[Sample]) -> User:
        if not clean_name(name):
            raise ValueError(_("Nombre de usuario no válido."))
        user = User(clean_name(name), samples=list(samples))
        self.storage.save_user(user)
        return user

    def add_samples(self, user_id: str, samples: list[Sample]) -> User:
        user = self.storage.get_user(user_id)
        if user is None:
            raise KeyError(user_id)
        user.samples.extend(samples)
        self.storage.save_user(user)
        return user

    def delete_sample(self, user_id: str, sample_id: str, force: bool = False) -> User:
        user = self.storage.get_user(user_id)
        if user is None:
            raise KeyError(user_id)
        if not force and len(user.samples) <= MIN_PROFILE_SAMPLES:
            raise ValueError(_("Un perfil necesita al menos {n} muestras.", n=MIN_PROFILE_SAMPLES))
        user.samples = [s for s in user.samples if s.id != sample_id]
        self.storage.save_user(user)
        return user

    def rename_user(self, user_id: str, name: str) -> None:
        user = self.storage.get_user(user_id)
        if user and clean_name(name):
            user.name = clean_name(name)
            self.storage.save_user(user)

    def delete_user(self, user_id: str) -> None:
        self.storage.delete_user(user_id)
        self._cache.pop(user_id, None)
        entries = self.storage.read_access()     # sus registros de acceso también son datos suyos
        if any(e.get("user_id") == user_id for e in entries):
            self.storage.rewrite_access([e for e in entries if e.get("user_id") != user_id])

    @staticmethod
    def session_count(user: User) -> int:
        return len(set(sessions_of(user.samples)))

    def quality(self, user: User, profile: Profile | None = None) -> tuple[str, str]:
        """Calidad del perfil: (nivel good|warn|bad, texto)."""
        n = len(user.samples)
        sessions = self.session_count(user)
        if n >= 5 and sessions >= 2:
            level, text = "good", _("Perfil sólido")
        elif n >= 3:
            level, text = "warn", _("Perfil aceptable") if sessions >= 2 else _("Una sola sesión")
        else:
            level, text = "bad", _("Perfil débil")
        if profile is not None and profile.s > 0.06 and level == "good":
            level, text = "warn", _("Perfil irregular")
        return level, text

    # -- calidad de las muestras --------------------------------------------
    def check_quality(self, sample: Sample) -> str | None:
        """Devuelve un motivo de rechazo o None si la muestra es válida."""
        min_acc = float(self.settings.get("min_accuracy", 80))
        if not sample.free and sample.accuracy * 100 < min_acc:
            return _("La precisión ha sido del {accuracy} % (mínimo {min} %).",
                     accuracy=f"{sample.accuracy * 100:.0f}", min=f"{min_acc:.0f}")
        typing = sum(k.kind in TYPING_KINDS for k in sample.keystrokes)
        if typing < MIN_TYPING_KEYS:
            return _("Se han registrado muy pocas pulsaciones.")
        released = sum(k.release is not None for k in sample.keystrokes)
        if released < 0.8 * len(sample.keystrokes):
            return _("No se han podido medir los tiempos de pulsación (¿se perdió el foco?).")
        return None

    def adapt_problem(self, sample: Sample) -> str | None:
        """Motivo para no añadir una muestra a un perfil, o None. Las muestras cortas (decisión
        rápida) tienen distancias mayores: en el perfil aflojarían el umbral."""
        reason = self.check_quality(sample)
        if reason:
            return reason
        if sum(k.kind in TYPING_KINDS for k in sample.keystrokes) < ADAPT_MIN_KEYS:
            return _("Es una muestra corta (se decidió antes de terminar el texto) y no sirve para el perfil.")
        return None

    def liveness(self, sample: Sample) -> list[Finding]:
        stored = [s for u in self.users() for s in u.samples]
        return check(sample, stored)

    # -- identificación y verificación --------------------------------------
    def identify(self, sample: Sample) -> tuple[Identification, SampleFeatures]:
        f = self.features(sample)
        return identify(f, self.profiles(), self.sensitivity), f

    def identify_partial(self, sample: Sample, profiles: list[Profile]) -> Identification:
        """Identificación de una muestra a medio escribir (para el modo en directo)."""
        return identify(extract(sample, light=True), profiles, self.sensitivity)

    def verify(self, sample: Sample, user_id: str) -> tuple[Identification, Candidate | None, SampleFeatures]:
        """Verificación 1:1: ¿la muestra es del usuario indicado?"""
        result, f = self.identify(sample)
        claimed = next((c for c in result.candidates if c.user_id == user_id), None)
        return result, claimed, f

    def similar_existing(self, samples: list[Sample], exclude: str | None = None) -> str | None:
        """Comprobación de registro duplicado: ¿estas muestras parecen de otro usuario?"""
        profiles = self.profiles(exclude=exclude)
        if not profiles:
            return None
        votes: dict[str, int] = {}
        for s in samples:
            res = identify(self.features(s), profiles, "estricto")
            if res.best:
                votes[res.best.name] = votes.get(res.best.name, 0) + 1
        if votes:
            name, n = max(votes.items(), key=lambda kv: kv[1])
            if n * 2 > len(samples):
                return name
        return None

    def maybe_adapt(self, sample: Sample, accepted: Candidate | None, result: Identification,
                    findings: list[Finding]) -> User | None:
        """Adaptación automática del perfil con comprobaciones muy seguras.

        Solo si: está activada, la muestra es válida, no hay sospechas, el resultado no es
        ambiguo y la confianza es alta. Si luego el usuario marca el resultado como
        incorrecto, la muestra se retira (``set_feedback``)."""
        if not self.settings.get("auto_adapt", True) or accepted is None or not accepted.accepted:
            return None
        if result.ambiguous or findings or accepted.confidence < ADAPT_MIN_CONFIDENCE:
            return None
        if self.adapt_problem(sample) is not None:
            return None
        sample.kind = "adapt"
        return self.add_samples(accepted.user_id, [sample])

    def evaluation_input(self) -> list[UserData]:
        """Datos para la evaluación cruzada (se calculan aquí, en el hilo principal)."""
        out = []
        for u in self.users():
            samples = self.profile_samples(u)
            out.append((u.id, u.name, [self.features(s) for s in samples], sessions_of(samples)))
        return out

    # -- calibración --------------------------------------------------------
    def history_trials(self) -> list[Trial]:
        """Ensayos reales a partir de las comprobaciones verificadas por el usuario."""
        profiles = {p.user_id: p for p in self.profiles()}
        trials = []
        for e in self.history():
            fb = e.get("feedback")
            if not fb:
                continue
            if e.get("mode") == "challenge":
                # imitación deliberada: solo vale como impostor frente al perfil imitado (el perfil
                # propio de quien imita no cuenta: estaba escribiendo distinto a propósito)
                row = next((r for r in e.get("ranking", []) if isinstance(r, dict)
                            and r.get("uid") == e.get("claimed_id") and r.get("total") is not None), None)
                if row and row["uid"] in profiles:
                    trials.append(Trial(False, row.get("ra"), row.get("z"), profiles[row["uid"]], cross_session=True))
                continue
            verify = e.get("mode") == "verify"
            if fb == "correct":
                if verify:
                    truth = e.get("user_id") if e.get("accepted") else None
                else:
                    truth = e.get("user_id")
            else:
                truth = e.get("true_user")
            for row in e.get("ranking", []):
                if not isinstance(row, dict) or row.get("uid") not in profiles or row.get("total") is None:
                    continue
                if verify and fb == "correct" and not e.get("accepted") and row["uid"] != e.get("claimed_id"):
                    continue   # solo sabemos que no era el usuario que decía ser
                prof = profiles[row["uid"]]
                trials.append(Trial(row["uid"] == truth, row.get("ra"), row.get("z"), prof, cross_session=True))
        return trials

    def log_challenge(self, sample: Sample, result: Identification, target: Candidate | None,
                      challenger_id: str | None, findings: list[Finding] = ()) -> dict:
        """Guarda un intento de imitación. El resultado verdadero se conoce (no era la persona
        imitada), así que queda verificado directamente y sirve para la calibración."""
        entry = self.log_identification(sample, result, "challenge", target, findings)
        entry["feedback"] = "incorrect" if entry["accepted"] else "correct"
        entry["true_user"] = challenger_id
        self.set_feedback(entry["id"], entry["feedback"], challenger_id)
        return entry

    def challenge_stats(self) -> tuple[int, int]:
        """(intentos de imitación, veces que KeyBio se dejó engañar)."""
        tries = [e for e in self.history() if e.get("mode") == "challenge"]
        return len(tries), sum(bool(e.get("accepted")) for e in tries)

    def run_calibration(self, data: list[UserData], extra: list[Trial]) -> Calibration:
        return calibrate(data, extra=extra)

    def apply_calibration(self, cal: Calibration) -> None:
        self.settings["sensitivity"] = "auto"
        self.settings["auto_k"] = round(cal.k, 2)
        self.settings["auto_weight"] = round(cal.weight, 2)
        self.save_settings()

    # -- verificación de acceso ----------------------------------------------
    # Al iniciar sesión en un sistema sensible se escribe una frase corta. La muestra se analiza en
    # memoria y se descarta: no se guarda, no se añade al perfil y no pasa al historial. Solo queda
    # la puntuación de coincidencia y, si no coincide, un aviso para el administrador.
    def has_profile(self, user_id: str) -> bool:
        return any(p.user_id == user_id for p in self.profiles())

    def access_check(self, sample: Sample, user_id: str) -> tuple[int, bool]:
        """(puntuación 0-100, coincide) de una muestra frente al perfil de ``user_id``. La
        puntuación es la confianza de la verificación: 50 es el umbral del perfil."""
        try:
            claimed = self.verify(sample, user_id)[1]
            blocked = is_blocking(self.liveness(sample))
        finally:
            self._feat_cache.pop(sample.id, None)   # las características tampoco se quedan en memoria
        if claimed is None or blocked:
            return 0, False
        return round(claimed.confidence), claimed.accepted

    def log_access(self, user_id: str, score: int, match: bool, system: str = "") -> dict:
        """Guarda lo imprescindible de una verificación de acceso. Si coincide: el día, la persona
        y la puntuación (para ver si un perfil se queda corto). Si no, es un aviso para el
        administrador: además la hora y el sistema, para poder revisarlo, y luego cómo terminó
        la verificación adicional (``finish_access``). Nunca las pulsaciones, el texto ni el equipo."""
        now = datetime.now()
        entry = {"id": uuid.uuid4().hex[:12], "user_id": user_id, "score": int(score), "match": bool(match)}
        if match:
            entry["date"] = now.date().isoformat()
        else:
            entry.update(date=now.isoformat(timespec="minutes"), system=clean_name(system), extra="pending")
        self.purge_access()
        self.storage.append_access(entry)
        return entry

    def finish_access(self, entry_id: str, outcome: str) -> None:
        """Anota en un aviso cómo terminó la verificación adicional (``ACCESS_OUTCOMES``)."""
        if outcome not in ACCESS_OUTCOMES:
            raise ValueError(outcome)
        entries = self.storage.read_access()
        for e in entries:
            if e.get("id") == entry_id and e.get("extra") == "pending":
                e["extra"] = outcome
        self.storage.rewrite_access(entries)

    def purge_access(self) -> list[dict]:
        """Borra los registros de acceso que han superado el plazo de conservación y devuelve el resto."""
        entries = self.storage.read_access()
        limit = datetime.now() - timedelta(days=int(self.settings.get("access_retention_days", 30)))
        keep = [e for e in entries if (d := _when(e.get("date"))) and d >= limit]
        if len(keep) != len(entries):
            self.storage.rewrite_access(keep)
        return keep

    def access_log(self) -> list[dict]:
        """Registros de acceso vigentes, del más reciente al más antiguo."""
        return list(reversed(self.purge_access()))

    def clear_access_log(self) -> None:
        self.storage.rewrite_access([])

    # -- historial ----------------------------------------------------------
    def log_identification(self, sample: Sample, result: Identification, mode: str = "identify",
                           claimed: Candidate | None = None, findings: list[Finding] = (),
                           adapted: User | None = None, early: bool = False) -> dict:
        one_to_one = mode in ("verify", "challenge")   # el desafío es una verificación con otra identidad
        shown = claimed if one_to_one else result.best
        accepted = bool(claimed and claimed.accepted) if one_to_one else result.best is not None
        if is_blocking(findings):
            accepted = False
        entry = {
            "id": uuid.uuid4().hex[:12],
            "date": datetime.now().isoformat(timespec="seconds"),
            "mode": mode,
            "free": sample.free,
            "text_id": sample.text_id,
            "accuracy": round(sample.accuracy * 100, 1),
            "wpm": round(self.features(sample).metrics["wpm"], 1),
            "sensitivity": self.sensitivity_label,
            "accepted": accepted,
            "claimed": claimed.name if claimed else None,
            "claimed_id": claimed.user_id if claimed else None,
            "user_id": shown.user_id if shown and accepted else None,
            "user_name": shown.name if shown and accepted else None,
            "confidence": round(shown.confidence, 1) if shown else None,
            "distance": round(shown.distance, 4) if shown else None,
            "threshold": round(shown.threshold, 4) if shown else None,
            "ambiguous": result.ambiguous,
            "keys": sum(k.kind in TYPING_KINDS for k in sample.keystrokes),
            "early": early,
            "suspicious": [f.code for f in findings],
            "adapted_user": adapted.id if adapted else None,
            "adapted_sample": sample.id if adapted else None,
            "ranking": [{"uid": c.user_id, "name": c.name, "total": round(c.distance, 4),
                         "threshold": round(c.threshold, 4),
                         "ra": None if c.ra is None else round(c.ra, 4),
                         "z": None if c.z is None else round(c.z, 4)} for c in result.candidates],
            "feedback": None,
            "true_user": None,
        }
        self.storage.append_history(entry)
        return entry

    def set_feedback(self, entry_id: str, feedback: str, true_user: str | None = None) -> str | None:
        """Guarda la verificación del usuario. Si la comprobación había adaptado un perfil y
        resulta incorrecta, retira esa muestra. Devuelve el nombre del perfil corregido."""
        entries = self.storage.read_history()
        undone = None
        for e in entries:
            if e.get("id") != entry_id:
                continue
            e["feedback"] = feedback
            e["true_user"] = true_user
            uid, sid = e.get("adapted_user"), e.get("adapted_sample")
            if feedback == "incorrect" and uid and sid and uid != true_user:
                user = self.storage.get_user(uid)
                if user and any(s.id == sid for s in user.samples):
                    self.delete_sample(uid, sid, force=True)
                    undone = user.name
                e["adapted_user"] = e["adapted_sample"] = None
        self.storage.rewrite_history(entries)
        return undone

    def history(self) -> list[dict]:
        return list(reversed(self.storage.read_history()))

    def clear_history(self) -> None:
        self.storage.rewrite_history([])

    # -- panel de control ---------------------------------------------------
    def dashboard_stats(self) -> dict:
        users = self.users()
        history = self.history()
        now = datetime.now()
        week_ago = now - timedelta(days=7)
        recent = [e for e in history if (d := _when(e.get("date"))) and d >= week_ago]
        verified = [e for e in history if e.get("feedback")]
        days = []
        for i in range(13, -1, -1):
            day = (now - timedelta(days=i)).date()
            todays = [e for e in history if (d := _when(e.get("date"))) and d.date() == day]
            days.append((day, sum(bool(e.get("accepted", e.get("user_id"))) for e in todays),
                         sum(not e.get("accepted", e.get("user_id")) for e in todays)))
        return {
            "users": len(users),
            "solid": sum(self.quality(u)[0] == "good" for u in users),
            "samples": sum(len(u.samples) for u in users),
            "keystrokes": sum(len(s.keystrokes) for u in users for s in u.samples),
            "checks": len(history),
            "checks_week": len(recent),
            "verified": len(verified),
            "verified_ok": sum(e["feedback"] == "correct" for e in verified),
            "unverified": len(history) - len(verified),
            "suspicious": sum(bool(e.get("suspicious")) for e in history),
            "days": days,
            "recent": history[:6],
        }

    def tips(self) -> list[tuple[str, str, str, str | None]]:
        """Sugerencias para el panel: (nivel, texto, acción, id de usuario)."""
        out = []
        week_ago = datetime.now() - timedelta(days=7)
        notices = [e for e in self.access_log() if not e.get("match") and (d := _when(e.get("date"))) and d >= week_ago]
        if notices:
            unresolved = sum(e.get("extra") != "passed" for e in notices)
            text = (_("Avisos de acceso esta semana: {n} ({unresolved} sin superar la verificación adicional).",
                      n=len(notices), unresolved=unresolved) if unresolved else
                    _("Avisos de acceso esta semana: {n} (verificación adicional superada).", n=len(notices)))
            out.append(("warn", text, "access", None))
        users = self.users()
        for u in users:
            if self.session_count(u) < 2 and len(u.samples) >= 2:
                out.append(("warn", _("El perfil de {name} es de una sola sesión. Añade muestras otro día "
                                      "para que te reconozca aunque escribas distinto.", name=u.name), "add_samples", u.id))
            elif len(u.samples) < 5:
                out.append(("warn", _n("{name} tiene {n} muestra; con 5 o más el perfil es más fiable.",
                                       "{name} tiene {n} muestras; con 5 o más el perfil es más fiable.",
                                       len(u.samples), name=u.name), "add_samples", u.id))
        if len(users) >= 3 and self.sensitivity != "auto":
            out.append(("good", _("Ya hay suficientes usuarios para calibrar la sensibilidad con vuestros "
                                  "propios datos."), "calibrate", None))
        if len(users) == 1:
            out.append(("warn", _("Con un solo usuario no se puede comprobar si el sistema rechaza a "
                                  "desconocidos. Registra a otra persona."), "enroll", None))
        if users and not self.storage.protected:
            out.append(("warn", _("Los perfiles se guardan sin cifrar. Puedes protegerlos con una contraseña."),
                        "protect", None))
        return out
