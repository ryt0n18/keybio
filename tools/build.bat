@echo off
rem Crea KeyBio.exe en dist\KeyBio\ (usa --onefile para un unico .exe)
rem Uso, desde la carpeta del proyecto: tools\build.bat
cd /d "%~dp0.."
if not exist .venv\Scripts\python.exe (
    py -3 -m venv .venv || python -m venv .venv
    .venv\Scripts\pip install -r requirements.txt
)
.venv\Scripts\pip install -q pyinstaller
.venv\Scripts\python tools\build.py %*
