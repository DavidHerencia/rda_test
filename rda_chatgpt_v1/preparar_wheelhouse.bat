@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if errorlevel 1 (
    echo python no esta disponible mediante el launcher py
    pause
    exit /b 1
)

if not exist wheelhouse mkdir wheelhouse
py -3 -m pip download --only-binary=:all: --dest wheelhouse -r requirements.txt

if errorlevel 1 (
    echo error preparando wheelhouse
    pause
    exit /b 1
)

echo wheelhouse preparado
pause
