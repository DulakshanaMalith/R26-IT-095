@echo off
title IPMS - Adaptive Scheduling System
color 0A

echo.
echo ============================================================
echo    IPMS - Generative Project Planning and Adaptive Scheduling
echo    Student ID : IT22117014
echo    Project ID : R26-IT-095
echo ============================================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.10 or later from https://python.org
    pause
    exit /b 1
)

echo [1/3] Checking dependencies...
pip install -r requirements.txt --quiet --disable-pip-version-check >nul 2>&1
echo       Dependencies OK.
echo.

echo [2/3] Loading AI Models and Starting Server...
echo       This may take 20-30 seconds for models to load.
echo.

:: Start the server
echo [3/3] Server is starting on http://localhost:8000
echo.
echo ============================================================
echo    Open your browser and go to: http://localhost:8000
echo    Press CTRL+C to stop the server.
echo ============================================================
echo.

python -m uvicorn main:app --host 0.0.0.0 --port 8000

pause
