"""Captura de pulsaciones independiente del toolkit gráfico.

La interfaz (Qt) llama a ``press`` / ``release`` / ``text_changed`` con un
identificador físico de tecla (scancode) y una marca de tiempo de alta
resolución (``time.perf_counter_ns``). El grabador empareja pulsación y
liberación, descarta la autorepetición y lleva la cuenta de errores.
"""

from __future__ import annotations

import math
import platform
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from . import APP_VERSION
from .textutil import levenshtein, normalize_typed

# Tipos de tecla
CHAR = "char"          # letra, número o signo
SPACE = "space"
BACKSPACE = "backspace"
MOD = "mod"            # shift, ctrl, alt, altgr, bloq mayús
DEAD = "dead"          # tecla muerta (tilde, diéresis...)
OTHER = "other"        # flechas, enter, tab... (bloqueadas pero registradas)

TYPING_KINDS = (CHAR, SPACE, DEAD)
KINDS = {CHAR, SPACE, BACKSPACE, MOD, DEAD, OTHER}
SAMPLE_KINDS = {"enroll", "verify", "adapt"}

# Límites al leer muestras de un fichero (pueden venir de una importación de otra persona)
MAX_KEYSTROKES = 20_000
MAX_TEXT = 20_000
_ISO_DATE = re.compile(r"[0-9T:+\-. ]{0,40}")
_SAFE_ID = re.compile(r"[0-9A-Za-z_-]{1,40}")


def _number(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"valor numérico no válido: {value!r}")
    return float(value)


def _count(value) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10 * MAX_KEYSTROKES:
        raise ValueError(f"contador no válido: {value!r}")
    return value


def _text(value, limit: int) -> str:
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError("texto no válido o demasiado largo")
    return value


def iso_date(value) -> str:
    """Fecha ISO tal cual, o "" si no lo parece (no se muestra texto arbitrario de un fichero)."""
    return value if isinstance(value, str) and _ISO_DATE.fullmatch(value) else ""


@dataclass
class Keystroke:
    label: str
    kind: str
    press: float                 # ms desde el inicio de la muestra
    release: float | None = None

    @property
    def dwell(self) -> float | None:
        if self.release is None:
            return None
        return self.release - self.press

    def to_list(self) -> list:
        return [self.label, self.kind, round(self.press, 3),
                None if self.release is None else round(self.release, 3)]

    @classmethod
    def from_list(cls, row: list) -> "Keystroke":
        if not isinstance(row, (list, tuple)) or len(row) != 4 or row[1] not in KINDS:
            raise ValueError(f"pulsación no válida: {row!r}"[:120])
        return cls(_text(row[0], 40), row[1], _number(row[2]), None if row[3] is None else _number(row[3]))


@dataclass
class Sample:
    """Una muestra de escritura completa (un texto tecleado)."""

    target: str
    typed: str
    keystrokes: list[Keystroke]
    errors_committed: int = 0          # caracteres erróneos tecleados (corregidos o no)
    error_positions: list[int] = field(default_factory=list)
    autorepeats: int = 0
    blocked_keys: int = 0               # flechas, enter, pegar... intentos bloqueados
    text_id: str = ""
    kind: str = "enroll"                # enroll | verify | adapt
    free: bool = False                  # texto libre: no hay texto objetivo que comparar
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    platform: str = field(default_factory=lambda: f"{platform.system()} {platform.release()}")
    app_version: str = APP_VERSION

    # -- métricas derivadas simples -------------------------------------
    @property
    def duration_ms(self) -> float:
        if not self.keystrokes:
            return 0.0
        last = max((k.release or k.press) for k in self.keystrokes)
        return last - self.keystrokes[0].press

    @property
    def typed_norm(self) -> str:
        return normalize_typed(self.typed, self.target)

    @property
    def uncorrected_errors(self) -> int:
        if self.free:
            return 0
        target = normalize_typed(self.target, self.target)
        return levenshtein(self.typed_norm, target)

    @property
    def accuracy(self) -> float:
        n = max(len(self.target), 1)
        return max(0.0, 1.0 - self.uncorrected_errors / n)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "created": self.created,
            "kind": self.kind,
            "free": self.free,
            "text_id": self.text_id,
            "target": self.target,
            "typed": self.typed,
            "errors_committed": self.errors_committed,
            "error_positions": self.error_positions,
            "autorepeats": self.autorepeats,
            "blocked_keys": self.blocked_keys,
            "platform": self.platform,
            "app_version": self.app_version,
            "keystrokes": [k.to_list() for k in self.keystrokes],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Sample":
        """Lee una muestra comprobando tipos y tamaños (ValueError si no es válida)."""
        if not isinstance(d, dict):
            raise ValueError("muestra no válida")
        keys = d.get("keystrokes")
        positions = d.get("error_positions", [])
        if not isinstance(keys, list) or len(keys) > MAX_KEYSTROKES:
            raise ValueError("pulsaciones no válidas")
        if not isinstance(positions, list) or len(positions) > MAX_TEXT:
            raise ValueError("posiciones de error no válidas")
        kind = d.get("kind", "enroll")
        sample_id = d.get("id")
        return cls(
            target=_text(d.get("target"), MAX_TEXT),
            typed=_text(d.get("typed"), MAX_TEXT),
            keystrokes=[Keystroke.from_list(r) for r in keys],
            errors_committed=_count(d.get("errors_committed", 0)),
            error_positions=[_count(x) for x in positions],
            autorepeats=_count(d.get("autorepeats", 0)),
            blocked_keys=_count(d.get("blocked_keys", 0)),
            text_id=_text(d.get("text_id", ""), 40),
            kind=kind if kind in SAMPLE_KINDS else "enroll",
            free=bool(d.get("free", False)),
            id=sample_id if isinstance(sample_id, str) and _SAFE_ID.fullmatch(sample_id) else uuid.uuid4().hex[:12],
            created=iso_date(d.get("created", "")),
            platform=_text(d.get("platform", ""), 100),
            app_version=_text(d.get("app_version", ""), 20),
        )


class KeystrokeRecorder:
    """Graba pulsaciones de una sesión de escritura sobre un texto objetivo."""

    def __init__(self, target: str, text_id: str = "", kind: str = "enroll", free: bool = False):
        self.target = target
        self.free = free
        self.text_id = text_id
        self.kind = kind
        self._target_norm = normalize_typed(target, target)
        self._t0: int | None = None
        self._down: dict[object, Keystroke] = {}
        self.keystrokes: list[Keystroke] = []
        self.autorepeats = 0
        self.blocked_keys = 0
        self.errors_committed = 0
        self.error_positions: list[int] = []
        self._prev_len = 0
        self.typed = ""

    @property
    def started(self) -> bool:
        return self._t0 is not None

    def elapsed_ms(self, t_ns: int | None = None) -> float:
        if self._t0 is None:
            return 0.0
        t_ns = time.perf_counter_ns() if t_ns is None else t_ns
        return (t_ns - self._t0) / 1e6

    def press(self, key_id, label: str, kind: str, t_ns: int, autorepeat: bool = False) -> None:
        if autorepeat or key_id in self._down:
            self.autorepeats += 1
            return
        if self._t0 is None:
            self._t0 = t_ns
        ks = Keystroke(label, kind, (t_ns - self._t0) / 1e6)
        self._down[key_id] = ks
        self.keystrokes.append(ks)

    def release(self, key_id, t_ns: int, autorepeat: bool = False) -> None:
        if autorepeat or self._t0 is None:
            return
        ks = self._down.pop(key_id, None)
        if ks is not None:
            ks.release = (t_ns - self._t0) / 1e6

    def block(self) -> None:
        """Registra un intento de acción bloqueada (pegar, flechas, ratón...)."""
        self.blocked_keys += 1

    def text_changed(self, typed: str) -> None:
        """Actualiza el texto escrito y cuenta los caracteres erróneos nuevos."""
        self.typed = typed
        if self.free:
            return
        norm = normalize_typed(typed, self.target)
        if len(norm) > self._prev_len:
            for pos in range(self._prev_len, len(norm)):
                if pos >= len(self._target_norm) or norm[pos] != self._target_norm[pos]:
                    self.errors_committed += 1
                    self.error_positions.append(pos)
        self._prev_len = len(norm)

    @property
    def keys_down(self) -> int:
        return len(self._down)

    def build_sample(self) -> Sample:
        return Sample(
            target=self.typed if self.free else self.target,
            free=self.free,
            typed=self.typed,
            keystrokes=list(self.keystrokes),
            errors_committed=self.errors_committed,
            error_positions=list(self.error_positions),
            autorepeats=self.autorepeats,
            blocked_keys=self.blocked_keys,
            text_id=self.text_id,
            kind=self.kind,
        )
