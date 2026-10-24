#!/usr/bin/env sh
# Arranca KeyBio en Linux. La primera vez crea el entorno virtual e instala PySide6.
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
fi
exec .venv/bin/python main.py "$@"
