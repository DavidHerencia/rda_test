@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if errorlevel 1 (
    echo python no esta disponible mediante el launcher py
    pause
    exit /b 1
)

if not exist .venv (
    py -3 -m venv .venv
    if errorlevel 1 goto :error
)

call .venv\Scripts\activate.bat
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
    echo se requiere python 3.10 o superior
    pause
    exit /b 1
)

dir /b wheelhouse\*.whl >nul 2>&1
if not errorlevel 1 (
    python -m pip install --no-index --find-links=wheelhouse -r requirements.txt
) else (
    python -m pip install -r requirements.txt
)

if errorlevel 1 goto :error

echo instalacion completada
pause
exit /b 0

:error
echo error durante la instalacion
pause
exit /b 1
