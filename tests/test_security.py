"""Pruebas de seguridad: ficheros importados, nombres, CSV, permisos y parámetros de cifrado."""

import copy
import json
import os
import random
import zipfile

import pytest

from ksb import crypto, storage
from ksb.service import BiometricService
from ksb.storage import InvalidImport, Storage, User, clean_name
from ksb.texts import ENROLL_TEXTS
from tests.simulate import SyntheticTypist


def _user_dict(name="Eva", n=2):
    rng = random.Random(8)
    t = SyntheticTypist(70)
    samples = [t.type_text(x, rng, text_id=k).build_sample() for k, x in list(ENROLL_TEXTS.items())[:n]]
    return User(name, samples=samples).to_dict()


def test_names_are_plain_text():
    assert clean_name("  Ana   María ") == "Ana María"
    assert clean_name("<b>Eva</b>") == "b Eva /b"
    assert clean_name("x‮oyx\u0000y") == "x oyx y"
    assert clean_name("ñ" * 60) == "ñ" * 40
    assert clean_name(None) == "" and clean_name("<>") == ""


def test_import_cleans_names_and_rejects_malformed_files(tmp_path):
    st = Storage(tmp_path / "datos")
    evil = _user_dict("<img src='file:///etc/passwd'>Eva")
    evil["created"] = "<script>"
    (tmp_path / "eva.json").write_text(json.dumps(evil), encoding="utf-8")
    [(name, n)] = st.import_users(tmp_path / "eva.json")
    assert "<" not in name and ">" not in name and n == 2
    assert st.list_users()[0].created == ""

    for mutate in (
        lambda d: d["samples"][0]["keystrokes"][0].__setitem__(2, "rápido"),       # tiempo que no es un número
        lambda d: d["samples"][0]["keystrokes"][0].__setitem__(1, "teclado"),      # tipo de tecla inventado
        lambda d: d["samples"][0]["keystrokes"].append([1, 2]),                     # pulsación incompleta
        lambda d: d["samples"][0].__setitem__("errors_committed", -5),
        lambda d: d["samples"][0]["keystrokes"][0].__setitem__(3, float("inf")),
        lambda d: d.__setitem__("samples", "muchas"),
    ):
        bad = _user_dict()
        mutate(bad)
        (tmp_path / "mal.json").write_text(json.dumps(bad), encoding="utf-8")
        with pytest.raises(InvalidImport):
            st.import_users(tmp_path / "mal.json")
    assert len(st.list_users()) == 1   # nada de lo inválido se ha guardado


def test_corrupt_profile_on_disk_is_skipped_not_loaded(tmp_path):
    st = Storage(tmp_path)
    good = _user_dict("Bea")
    bad = copy.deepcopy(good)
    bad["id"], bad["name"] = "abc123", "Rota"
    bad["samples"][0]["keystrokes"][5][2] = None
    (st.users_dir / f"{good['id']}.json").write_text(json.dumps(good), encoding="utf-8")
    (st.users_dir / "abc123.json").write_text(json.dumps(bad), encoding="utf-8")
    assert [u.name for u in st.list_users()] == ["Bea"]


def test_import_limits_uncompressed_size(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "MAX_IMPORT_BYTES", 50_000)
    big = tmp_path / "bomba.zip"
    with zipfile.ZipFile(big, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("users/abc.json", " " * 200_000)   # se comprime a casi nada
    assert big.stat().st_size < 5_000
    with pytest.raises(InvalidImport, match="demasiado grande"):
        Storage(tmp_path / "datos").import_users(big)
    plain = tmp_path / "grande.json"
    plain.write_text(" " * 60_000, encoding="utf-8")
    with pytest.raises(InvalidImport, match="demasiado grande"):
        Storage(tmp_path / "datos").import_users(plain)


def test_service_rejects_names_without_text(tmp_path):
    svc = BiometricService(Storage(tmp_path))
    with pytest.raises(ValueError):
        svc.create_user("<>", [])
    user = svc.create_user("Carla <admin>", [])
    assert user.name == "Carla admin"


@pytest.mark.skipif(os.name != "posix", reason="permisos de Linux y macOS")
def test_private_permissions(tmp_path):
    st = Storage(tmp_path / "datos")
    st.append_history({"id": "a1"})
    st.export_backup(tmp_path / "copia.zip")
    assert (tmp_path / "datos").stat().st_mode & 0o777 == 0o700
    assert (tmp_path / "datos" / "history.jsonl").stat().st_mode & 0o777 == 0o600
    assert (tmp_path / "copia.zip").stat().st_mode & 0o777 == 0o600
    assert zipfile.ZipFile(tmp_path / "copia.zip").namelist() == ["history.jsonl"]


def test_csv_cells_are_not_formulas():
    pytest.importorskip("PySide6")
    from ksb.gui.pages.history import csv_cell
    assert csv_cell("=HYPERLINK(\"http://x\")") == "'=HYPERLINK(\"http://x\")"
    assert csv_cell("@SUM(A1)") == "'@SUM(A1)" and csv_cell("+34") == "'+34"
    assert csv_cell("Ana") == "Ana" and csv_cell(-0.5) == -0.5


def test_tampered_keystore_parameters_are_rejected():
    if not crypto.AVAILABLE:
        pytest.skip("cryptography no instalado")
    _, meta = crypto.Vault.create("clave")
    for n, r in ((2 ** 24, 8), (3000, 8), (2 ** 15, 10 ** 6), ("x", 8)):
        with pytest.raises(ValueError):
            crypto.Vault.open("clave", {**meta, "n": n, "r": r})
    assert crypto.Vault.open("clave", meta)
