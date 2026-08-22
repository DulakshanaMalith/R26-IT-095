@echo off
title IPMS - System Launcher
color 0A
echo.
echo  Starting IPMS - All Services
echo  =====================================
echo.
echo  [1/6] Scheduling Backend (Port 8000)...
start "" "%~dp0svc1_scheduling.bat"
echo  Waiting 70 seconds for ML models...
timeout /t 70 /nobreak >nul
echo  [2/6] Quality Backend (Port 8001)...
start "" "%~dp0svc2_quality_api.bat"
timeout /t 10 /nobreak >nul
echo  [3/6] Quality Frontend (Port 3000)...
start "" "%~dp0svc3_quality_ui.bat"
timeout /t 5 /nobreak >nul
echo  [4/6] Risk Backend (Port 5000)...
start "" "%~dp0svc4_risk.bat"
timeout /t 5 /nobreak >nul
echo  [5/6] Team Backend (Port 8003)...
start "" "%~dp0svc5_team_api.bat"
timeout /t 5 /nobreak >nul
echo  [6/6] Team Frontend (Port 3001)...
start "" "%~dp0svc6_team_ui.bat"
timeout /t 8 /nobreak >nul
echo.
echo  Opening Main Dashboard first...
start "" "d:\New folder (91)\index.html"
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:8000/app"
echo.
echo  =====================================
echo   ALL SERVICES LAUNCHED!
echo  =====================================
echo.
echo   [1] Scheduling   http://127.0.0.1:8000/app
echo   [2] Quality API  http://127.0.0.1:8001/docs
echo   [3] Quality UI   http://localhost:3000
echo   [4] Risk         http://127.0.0.1:5000
echo   [5] Team API     http://127.0.0.1:8003/docs
echo   [6] Team UI      http://127.0.0.1:3001
echo.
pause
