@echo off
setlocal
cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
    echo ejecuta instalar.bat primero
    pause
    exit /b 1
)

.venv\Scripts\python.exe app.py
