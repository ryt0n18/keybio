"""Cifrado opcional de los datos biométricos con contraseña.

* La clave se deriva de la contraseña con **scrypt** (sal aleatoria por
  instalación) y se usa con **Fernet** (AES-128-CBC + HMAC-SHA256) de la
  librería ``cryptography``.
* La contraseña nunca se guarda: ``keystore.json`` solo contiene la sal, los
  parámetros de scrypt y un testigo cifrado para comprobar la contraseña.
* Si se olvida la contraseña, los datos cifrados **no se pueden recuperar**.
"""

from __future__ import annotations

import base64
import hashlib
import os

try:
    from cryptography.fernet import Fernet
    AVAILABLE = True
except ImportError:  # el resto de la aplicación funciona sin cifrado
    Fernet = None
    AVAILABLE = False

SCRYPT_N = 2 ** 15
SCRYPT_R = 8
SCRYPT_P = 1
MAX_MEM = 256 * 1024 * 1024   # memoria máxima de scrypt (también limita un keystore manipulado)
_CHECK = b"keybio-ok"


class WrongPassword(Exception):
    pass


class Vault:
    def __init__(self, key: bytes):
        if not AVAILABLE:
            raise RuntimeError("Falta el paquete 'cryptography' (pip install cryptography).")
        self._f = Fernet(key)

    @staticmethod
    def derive(password: str, salt: bytes, n: int = SCRYPT_N, r: int = SCRYPT_R, p: int = SCRYPT_P) -> bytes:
        raw = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=32, maxmem=MAX_MEM + 1024 * 1024)
        return base64.urlsafe_b64encode(raw)

    @classmethod
    def create(cls, password: str) -> tuple["Vault", dict]:
        salt = os.urandom(16)
        vault = cls(cls.derive(password, salt))
        meta = {"version": 1, "kdf": "scrypt", "n": SCRYPT_N, "r": SCRYPT_R, "p": SCRYPT_P,
                "salt": base64.b64encode(salt).decode(), "check": vault.encrypt(_CHECK)}
        return vault, meta

    @classmethod
    def open(cls, password: str, meta: dict) -> "Vault":
        n, r, p = meta.get("n", SCRYPT_N), meta.get("r", SCRYPT_R), meta.get("p", SCRYPT_P)
        if not all(isinstance(x, int) and x > 0 for x in (n, r, p)) or n & (n - 1) or 128 * r * n * p > MAX_MEM:
            raise ValueError("keystore.json está dañado: parámetros de cifrado no válidos.")
        salt = base64.b64decode(meta["salt"])
        vault = cls(cls.derive(password, salt, n, r, p))
        try:
            ok = vault.decrypt(meta["check"]) == _CHECK
        except Exception:
            ok = False
        if not ok:
            raise WrongPassword("Contraseña incorrecta.")
        return vault

    def encrypt(self, data: bytes) -> str:
        return self._f.encrypt(data).decode("ascii")

    def decrypt(self, token: str) -> bytes:
        return self._f.decrypt(token.encode("ascii"))
