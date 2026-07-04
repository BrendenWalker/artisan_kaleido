@echo off
setlocal EnableExtensions
REM Run Artisan Kaleido from source during local development (Windows).
REM Requires Python 3.12+ on PATH.

cd /d "%~dp0"

echo.
echo === Artisan Kaleido local development startup ===
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python was not found on PATH.
    echo Install Python 3.12 or newer from https://www.python.org/downloads/
    exit /b 1
)

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.12 or newer is required.
    python --version
    exit /b 1
)

if not exist artisan_venv (
    echo [1/4] Creating virtual environment in src\artisan_venv ...
    python -m venv artisan_venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        exit /b 1
    )
) else (
    echo [1/4] Using existing virtual environment src\artisan_venv
)

echo [2/4] Activating virtual environment ...
call artisan_venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment.
    exit /b 1
)

echo [3/4] Installing/updating dependencies from requirements.txt ...
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    exit /b 1
)

echo [4/4] Starting Artisan ...
echo.
python artisan.py %*

endlocal
