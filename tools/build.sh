#!/usr/bin/env sh
# Crea el ejecutable de KeyBio: Linux → dist/KeyBio/, macOS → dist/KeyBio.app
# Uso, desde la carpeta del proyecto: tools/build.sh
set -e
cd "$(dirname "$0")/.."
[ -x .venv/bin/python ] || { python3 -m venv .venv && .venv/bin/pip install -r requirements.txt; }
.venv/bin/pip install -q pyinstaller
.venv/bin/python tools/build.py "$@"
