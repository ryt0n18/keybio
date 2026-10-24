@echo off
rem Arranca KeyBio en Windows. La primera vez crea el entorno virtual e instala PySide6.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    py -3 -m venv .venv || python -m venv .venv
    .venv\Scripts\pip install -r requirements.txt
)
.venv\Scripts\python main.py %*
