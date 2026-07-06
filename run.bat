@echo off
cd /d "%~dp0"

echo.
echo  =========================================
echo   IFMS - Intelligent Financial Management
echo  =========================================
echo.

REM Check if .env exists, warn if not
if not exist ".env" (
    echo  WARNING: No .env file found!
    echo  Copy .env.example to .env and fill in your MySQL password.
    echo  See IFMS_TeamSetup_Guide.html for instructions.
    echo.
    pause
    exit /b 1
)

REM Check if .venv exists, create if not
if not exist ".venv" (
    echo  [1/3] Creating virtual environment...
    python -m venv .venv
)

echo  [2/3] Installing/updating packages...
.venv\Scripts\pip install -r requirements.txt -q

echo  [3/3] Starting IFMS...
echo.
echo  Open browser at: http://127.0.0.1:5000
echo  Press Ctrl+C to stop the server
echo.

.venv\Scripts\python.exe app.py
pause
