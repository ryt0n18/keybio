"""La versión se cambia solo en ksb/__init__.py: el resto de sitios que la nombran deben coincidir."""

import re
from pathlib import Path

from ksb import APP_VERSION

ROOT = Path(__file__).resolve().parent.parent


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_changelog_starts_with_this_version():
    assert re.search(r"^## (\S+)", _read("CHANGELOG.md"), re.M).group(1) == APP_VERSION


def test_installer_and_docs_use_this_version():
    assert f'#define AppVersion "{APP_VERSION}"' in _read("tools/keybio.iss")
    assert f"/DAppVersion={APP_VERSION}" in _read("docs/desarrollo.md")


def test_web_downloads_point_to_this_release():
    config = _read("web/public/assets/js/config.js")
    assert f'version: "{APP_VERSION}"' in config
    assert f"/releases/download/v{APP_VERSION}/" in config
    # los nombres de los ficheros que crea la CI (.github/workflows/ci.yml)
    for name in (f"KeyBio-{APP_VERSION}-setup.exe", "KeyBio-windows-x64.zip", "KeyBio-linux-x64.tar.gz",
                 f"KeyBio-{APP_VERSION}-linux-amd64.deb", f"KeyBio-{APP_VERSION}-macos-arm64.dmg"):
        assert f'"{name}"' in config, name


def test_desktop_integration_ids_match():
    """Linux une la ventana con su entrada del menú por el identificador, y Windows el acceso del menú
    Inicio con la barra de tareas: si no coinciden, sale otro icono o no se puede anclar."""
    import importlib.util
    import shutil
    import subprocess
    import tempfile

    spec = importlib.util.spec_from_file_location("linux_tool", ROOT / "tools" / "linux.py")
    linux = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(linux)
    app = _read("ksb/gui/app.py")
    assert f'DESKTOP_ID = "{linux.APP_ID}"' in app
    assert f"ID={linux.APP_ID}\n" in _read("tools/linux/instalar.sh")
    model_id = re.search(r'SetCurrentProcessExplicitAppUserModelID\("([^"]+)"\)', app).group(1)
    assert _read("tools/keybio.iss").count(f'AppUserModelID: "{model_id}"') == 2

    entry = linux.desktop_entry("/opt/keybio/KeyBio")
    from ksb.i18n import FALLBACK, LANGUAGES
    for code in LANGUAGES:
        if code != FALLBACK:
            assert f"GenericName[{code}]=" in entry and f"Comment[{code}]=" in entry and f"Keywords[{code}]=" in entry
    assert f"Icon={linux.APP_ID}\n" in entry and f"<id>{linux.APP_ID}</id>" in linux.metainfo()
    if shutil.which("desktop-file-validate"):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / f"{linux.APP_ID}.desktop"
            path.write_text(entry, encoding="utf-8")
            result = subprocess.run(["desktop-file-validate", str(path)], capture_output=True, text=True)
            assert result.returncode == 0 and not result.stdout.strip(), result.stdout
