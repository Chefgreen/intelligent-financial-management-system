@echo off
cd /d "%~dp0"

echo.
echo  =========================================
echo   IFMS Partner Setup Script
echo   Run this ONCE on a new PC
echo  =========================================
echo.

REM Step 1: Check Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python is not installed or not in PATH.
    echo.
    echo  Please install Python from: https://www.python.org/downloads/
    echo  IMPORTANT: Tick "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

echo  [OK] Python found:
python --version
echo.

REM Step 2: Create virtual environment
echo  [1/4] Creating virtual environment...
python -m venv .venv
echo  Done.
echo.

REM Step 3: Install packages
echo  [2/4] Installing packages (this takes 1-2 minutes)...
.venv\Scripts\pip install -r requirements.txt -q
echo  Done.
echo.

REM Step 4: Create .env from example if missing
if not exist ".env" (
    echo  [3/4] Creating .env file from template...
    copy .env.example .env >nul
    echo  Done. IMPORTANT: Open .env and enter your MySQL password!
) else (
    echo  [3/4] .env file already exists, skipping.
)
echo.

REM Step 5: Remind about MySQL
echo  [4/4] Database setup reminder:
echo.
echo   If you haven't already:
echo   1. Install MySQL Community Server
echo   2. Open MySQL Workbench
echo   3. Run schema.sql  (creates all tables)
echo   4. Run patch.sql   (adds any missing columns)
echo.
echo  =========================================
echo   Setup complete!
echo.
echo   Next steps:
echo   1. Open .env and set your MYSQL_PASSWORD
echo   2. Run schema.sql in MySQL Workbench
echo   3. Double-click run.bat to start the app
echo  =========================================
echo.
pause
EOF