@echo off
REM ============================================================
REM  IFMS Fix & Run Script
REM  Automatically finds app.py, fixes config.py, starts app
REM ============================================================

REM Navigate to the folder containing app.py
cd /d "C:\Users\HP\OneDrive\Desktop\Lunga Greenhead UNILUS\Year 3, Semester 2\Group Studio ICT\Intelligent Financial Management System (IFMS) – AI-Powered Personal Finance\IFMS\IFMS\IFMS\IFMS\IFMS"

echo.
echo Current folder:
cd
echo.

REM Write the correct config.py directly into this folder
echo Writing fixed config.py...

(
echo import os
echo.
echo class Config:
echo     SECRET_KEY        = "IFMS_secure_2026_Lunga"
echo     JWT_SECRET        = "JWT_auth_2026_Greenhead"
echo     JWT_ALGORITHM     = "HS256"
echo     JWT_EXPIRY_HOURS  = 8
echo     MYSQL_HOST        = "localhost"
echo     MYSQL_USER        = "root"
echo     MYSQL_PASSWORD    = "894675Lunga"
echo     MYSQL_DB          = "ifms_db"
echo     MYSQL_PORT        = 3306
echo     MYSQL_CURSORCLASS = "DictCursor"
echo     SESSION_COOKIE_HTTPONLY    = True
echo     SESSION_COOKIE_SAMESITE    = "Lax"
echo     PERMANENT_SESSION_LIFETIME = 3600
echo     APP_NAME      = "IFMS"
echo     MFA_ISSUER    = "IFMS Financial"
echo     IS_PRODUCTION = False
) > config.py

echo Done. Verifying password is set...

"C:\Users\HP\OneDrive\Desktop\Lunga Greenhead UNILUS\Year 3, Semester 2\Group Studio ICT\Intelligent Financial Management System (IFMS) – AI-Powered Personal Finance\IFMS\IFMS\.venv\Scripts\python.exe" -c "from config import Config; print('PASSWORD =', Config.MYSQL_PASSWORD)"

echo.
echo Starting IFMS...
echo Open browser at: http://127.0.0.1:5000
echo.

"C:\Users\HP\OneDrive\Desktop\Lunga Greenhead UNILUS\Year 3, Semester 2\Group Studio ICT\Intelligent Financial Management System (IFMS) – AI-Powered Personal Finance\IFMS\IFMS\.venv\Scripts\python.exe" app.py

pause
