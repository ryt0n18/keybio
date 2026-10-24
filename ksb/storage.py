"""Almacenamiento local en JSON (un fichero por usuario), con cifrado opcional.

Estructura de la carpeta de datos::

    users/<id>.json     un usuario con todas sus muestras en bruto
    history.jsonl       una línea por comprobación
    access.jsonl        verificaciones de acceso: solo la puntuación, nunca las pulsaciones
    settings.json       ajustes (nunca se cifran: hacen falta antes de pedir la contraseña)
    keystore.json       solo si hay contraseña: sal y parámetros (no la contraseña)
    logs/keybio.log     registro de errores

Con contraseña, cada fichero de usuario y cada línea del historial y de los accesos se guardan
como ``{"keybio_encrypted": 1, "token": "..."}``. Los ficheros sin cifrar se
siguen leyendo, así que activar o quitar la contraseña es seguro aunque se
interrumpa a medias.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import unicodedata
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .capture import Sample, iso_date
from .crypto import Vault
from .i18n import _

SCHEMA_VERSION = 2
MAX_NAME = 40
MAX_SAMPLES = 1000
MAX_IMPORT_BYTES = 100 * 1024 * 1024   # por fichero importado y en total dentro de un .zip
MAX_ZIP_ENTRIES = 2000
# caracteres de control, invisibles y de dirección del texto, y < > (Qt los tomaría por HTML)
_NAME_DROP = re.compile(r"[\x00-\x1f\x7f-\x9f\u200b-\u200f\u202a-\u202e\u2066-\u2069<>]")

DEFAULT_SETTINGS = {
    "sensitivity": "normal",    # estricto | normal | permisivo | auto
    "auto_k": 2.0,              # K y peso de fusión de la sensibilidad "auto" (calibración)
    "auto_weight": 0.55,
    "enroll_samples": 3,
    "min_accuracy": 80,
    "theme": "system",          # system | light | dark
    "font_scale": 1.0,
    "show_keyboard": True,
    "language": "auto",         # idioma de la interfaz: auto (el del sistema) o un código de ksb/i18n.py
    "keyboard_layout": "auto",  # auto (según el idioma) | es | us | fr | de | it | pt
    "text_language": "auto",    # idioma de los textos para escribir: auto (el de la interfaz) | código | mixed
    "auto_adapt": True,         # añadir al perfil las comprobaciones muy seguras
    "live_identify": True,      # identificación en directo mientras se escribe
    "early_stop": True,         # terminar antes del final del texto si el resultado ya está claro
    "access_retention_days": 30,  # días que se conservan los registros de verificación de acceso
}

EXPORT_FORMAT = "keybio-users"


class LockedError(Exception):
    """Los datos están cifrados y todavía no se ha introducido la contraseña."""


class InvalidImport(ValueError):
    """El fichero que se quiere importar no es una exportación válida de KeyBio."""


def clean_name(name) -> str:
    """Nombre de usuario como texto llano: sin caracteres de control ni < > (los nombres se
    muestran en etiquetas con formato), con los espacios normalizados y como mucho 40 caracteres."""
    text = unicodedata.normalize("NFC", name if isinstance(name, str) else "")
    return " ".join(_NAME_DROP.sub(" ", text).split())[:MAX_NAME].strip()


def _private(path: Path, binary: bool = False, append: bool = False):
    """Abre un fichero para escribir que solo puede leer el usuario (en Linux y macOS)."""
    flags = os.O_WRONLY | os.O_CREAT | (os.O_APPEND if append else os.O_TRUNC) | getattr(os, "O_BINARY", 0)
    fd = os.open(path, flags, 0o600)
    if os.name == "posix":
        os.fchmod(fd, 0o600)   # por si el fichero ya existía con otros permisos
    return os.fdopen(fd, ("a" if append else "w") + ("b" if binary else ""), **({} if binary else {"encoding": "utf-8"}))


def default_data_dir() -> Path:
    if env := os.environ.get("KEYBIO_DATA_DIR"):
        return Path(env)
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        return base / "KeyBio"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "KeyBio"
    base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "keybio"


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _atomic_write(path: Path, data) -> None:
    _atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=1))


@dataclass
class User:
    name: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    created: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    samples: list[Sample] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"schema": SCHEMA_VERSION, "id": self.id, "name": self.name, "created": self.created,
                "samples": [s.to_dict() for s in self.samples]}

    @classmethod
    def from_dict(cls, d: dict) -> "User":
        """Lee un usuario comprobando tipos y tamaños (ValueError si no es válido).
        schema 1 (sin campo "schema") es compatible: los campos nuevos tienen valor por defecto."""
        if not isinstance(d, dict) or not isinstance(d.get("id"), str) or len(d["id"]) > 40:
            raise ValueError("usuario no válido")
        samples = d.get("samples", [])
        if not isinstance(samples, list) or len(samples) > MAX_SAMPLES:
            raise ValueError("muestras no válidas")
        return cls(clean_name(d.get("name")) or "Sin nombre", d["id"], iso_date(d.get("created", "")),
                   [Sample.from_dict(s) for s in samples])


class Storage:
    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else default_data_dir()
        self.users_dir = self.root / "users"
        self.users_dir.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":   # datos biométricos: la carpeta solo es accesible para el usuario
            try:
                os.chmod(self.root, 0o700)
            except OSError:
                pass
        self.history_path = self.root / "history.jsonl"
        self.access_path = self.root / "access.jsonl"
        self.settings_path = self.root / "settings.json"
        self.keystore_path = self.root / "keystore.json"
        self._vault: Vault | None = None

    # -- cifrado ------------------------------------------------------------
    @property
    def protected(self) -> bool:
        return self.keystore_path.exists()

    @property
    def locked(self) -> bool:
        return self.protected and self._vault is None

    def unlock(self, password: str) -> None:
        """Abre los datos cifrados. Lanza crypto.WrongPassword si no es correcta."""
        meta = json.loads(self.keystore_path.read_text(encoding="utf-8"))
        self._vault = Vault.open(password, meta)

    def _encode(self, data, indent: int | None = 1) -> str:
        text = json.dumps(data, ensure_ascii=False, indent=indent)
        if self._vault is None:
            return text
        return json.dumps({"keybio_encrypted": 1, "token": self._vault.encrypt(text.encode("utf-8"))})

    def _decode(self, text: str):
        data = json.loads(text)
        if isinstance(data, dict) and data.get("keybio_encrypted"):
            if self._vault is None:
                raise LockedError(_("Datos cifrados: hace falta la contraseña."))
            return json.loads(self._vault.decrypt(data["token"]).decode("utf-8"))
        return data

    def enable_protection(self, password: str) -> None:
        if self.locked:
            raise LockedError(_("Primero hay que desbloquear los datos."))
        users, history, access = self.list_users(), self.read_history(), self.read_access()
        vault, meta = Vault.create(password)
        _atomic_write(self.keystore_path, meta)
        self._vault = vault
        for u in users:
            self.save_user(u)
        self.rewrite_history(history)
        self.rewrite_access(access)

    def change_password(self, new_password: str) -> None:
        self.enable_protection(new_password)

    def disable_protection(self) -> None:
        if self.locked:
            raise LockedError(_("Primero hay que desbloquear los datos."))
        users, history, access = self.list_users(), self.read_history(), self.read_access()
        self._vault = None
        for u in users:
            self.save_user(u)
        self.rewrite_history(history)
        self.rewrite_access(access)
        self.keystore_path.unlink(missing_ok=True)

    # -- usuarios -----------------------------------------------------------
    def _user_path(self, user_id: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]+", user_id):
            raise ValueError(f"id de usuario no válido: {user_id!r}")
        return self.users_dir / f"{user_id}.json"

    def list_users(self) -> list[User]:
        users = []
        for path in sorted(self.users_dir.glob("*.json")):
            try:
                users.append(User.from_dict(self._decode(path.read_text(encoding="utf-8"))))
            except LockedError:
                raise
            except Exception as exc:  # un fichero dañado no debe impedir abrir el resto
                print(f"[keybio] no se pudo leer {path}: {exc}", file=sys.stderr)
        return sorted(users, key=lambda u: u.name.lower())

    def get_user(self, user_id: str) -> User | None:
        path = self._user_path(user_id)
        if not path.exists():
            return None
        return User.from_dict(self._decode(path.read_text(encoding="utf-8")))

    def find_by_name(self, name: str) -> User | None:
        key = name.strip().casefold()
        return next((u for u in self.list_users() if u.name.casefold() == key), None)

    def save_user(self, user: User) -> None:
        _atomic_write_text(self._user_path(user.id), self._encode(user.to_dict()))

    def delete_user(self, user_id: str) -> None:
        self._user_path(user_id).unlink(missing_ok=True)

    # -- exportar / importar ---------------------------------------------------
    def export_users(self, users: list[User], path: Path) -> None:
        """Exporta sin cifrar (para poder abrirlo en otro equipo)."""
        data = {"format": EXPORT_FORMAT, "version": SCHEMA_VERSION,
                "exported": datetime.now().isoformat(timespec="seconds"),
                "users": [u.to_dict() for u in users]}
        _atomic_write(Path(path), data)

    def export_backup(self, path: Path) -> None:
        """Copia de seguridad completa (usuarios, historial y ajustes) en un .zip sin cifrar. Los registros
        de acceso no entran: en una copia seguirían existiendo después de su plazo de conservación."""
        with _private(Path(path), binary=True) as fh, zipfile.ZipFile(fh, "w", zipfile.ZIP_DEFLATED) as zf:
            for u in self.list_users():
                zf.writestr(f"users/{u.id}.json", json.dumps(u.to_dict(), ensure_ascii=False, indent=1))
            zf.writestr("history.jsonl", "".join(json.dumps(e, ensure_ascii=False) + "\n"
                                                 for e in self.read_history()))
            if self.settings_path.exists():
                zf.write(self.settings_path, "settings.json")

    def _read_import(self, path: Path) -> list[dict]:
        path = Path(path)
        too_big = InvalidImport(_("El fichero es demasiado grande para ser una exportación de KeyBio."))
        if zipfile.is_zipfile(path):
            # Solo se leen en memoria las entradas users/*.json (nada se extrae a disco) y con un
            # límite de tamaño descomprimido, por si el .zip está hecho para agotar la memoria.
            out = []
            with zipfile.ZipFile(path) as zf:
                entries = [i for i in zf.infolist() if re.fullmatch(r"users/[^/\\]+\.json", i.filename)]
                if len(entries) > MAX_ZIP_ENTRIES or sum(i.file_size for i in entries) > MAX_IMPORT_BYTES:
                    raise too_big
                for info in entries:
                    out.append(self._decode(zf.read(info).decode("utf-8")))
            return out
        if path.stat().st_size > MAX_IMPORT_BYTES:
            raise too_big
        data = self._decode(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("format") == EXPORT_FORMAT:
            return list(data.get("users", []))
        if isinstance(data, dict) and "samples" in data and "name" in data:
            return [data]
        raise InvalidImport(_("El fichero no es una exportación de KeyBio."))

    def import_users(self, path: Path) -> list[tuple[str, int]]:
        """Importa usuarios. Devuelve [(nombre, muestras añadidas)].

        Si el usuario ya existe (mismo id) se añaden solo las muestras nuevas;
        si coincide el nombre pero no el id, se importa con otro nombre.
        """
        result = []
        try:
            incoming_users = [User.from_dict(raw) for raw in self._read_import(path)]
        except InvalidImport:
            raise
        except (ValueError, KeyError, TypeError, UnicodeDecodeError) as exc:
            raise InvalidImport(_("El fichero no es una exportación válida de KeyBio.")) from exc
        for incoming in incoming_users:
            if not re.fullmatch(r"[0-9a-f]+", incoming.id):
                incoming.id = uuid.uuid4().hex[:10]
            current = self.get_user(incoming.id)
            if current:
                known = {s.id for s in current.samples}
                new = [s for s in incoming.samples if s.id not in known]
                current.samples.extend(new)
                self.save_user(current)
                result.append((current.name, len(new)))
                continue
            base, n = incoming.name, 2
            while self.find_by_name(incoming.name):
                incoming.name = f"{base} ({n})"
                n += 1
            self.save_user(incoming)
            result.append((incoming.name, len(incoming.samples)))
        return result

    # -- historial y accesos (una línea JSON por entrada) ---------------------
    def _line(self, entry: dict) -> str:
        return self._encode(entry, indent=None).replace("\n", " ") + "\n"

    def _append_line(self, path: Path, entry: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with _private(path, append=True) as fh:
            fh.write(self._line(entry))

    def _read_lines(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        out = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                out.append(self._decode(line))
            except LockedError:
                raise
            except Exception:
                continue
        return out

    def _rewrite_lines(self, path: Path, entries: list[dict]) -> None:
        _atomic_write_text(path, "".join(self._line(e) for e in entries))

    def append_history(self, entry: dict) -> None:
        self._append_line(self.history_path, entry)

    def read_history(self) -> list[dict]:
        return self._read_lines(self.history_path)

    def rewrite_history(self, entries: list[dict]) -> None:
        self._rewrite_lines(self.history_path, entries)

    def append_access(self, entry: dict) -> None:
        self._append_line(self.access_path, entry)

    def read_access(self) -> list[dict]:
        return self._read_lines(self.access_path)

    def rewrite_access(self, entries: list[dict]) -> None:
        self._rewrite_lines(self.access_path, entries)

    # -- ajustes ------------------------------------------------------------
    def load_settings(self) -> dict:
        settings = dict(DEFAULT_SETTINGS)
        try:
            settings.update(json.loads(self.settings_path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
        return settings

    def save_settings(self, settings: dict) -> None:
        _atomic_write(self.settings_path, settings)
