@echo off
title IPMS - Full System Launcher
color 0A

echo.
echo  ================================================================
echo   IPMS - Intelligent Project Management System
echo   Starting All Services...
echo  ================================================================
echo.

echo  [0] Starting PostgreSQL 18 on port 5432...
start "PostgreSQL-Server" "D:\New folder (91)\START_POSTGRES.bat"
echo      Waiting 12 seconds for PostgreSQL to be ready...
timeout /t 12 /nobreak >nul

echo      Ensuring databases exist...
"D:\New Folder (3)\pgsql\bin\psql.exe" -U postgres -c "CREATE DATABASE ipms_scheduling;" 2>nul
"D:\New Folder (3)\pgsql\bin\psql.exe" -U postgres -c "CREATE DATABASE team_formation_db;" 2>nul
"D:\New Folder (3)\pgsql\bin\psql.exe" -U postgres -c "CREATE DATABASE researchpilot;" 2>nul
echo      Database check complete.
echo.

echo  [1] Starting Component 1 - Adaptive Scheduling (Port 8000)...
echo      Database: PostgreSQL ipms_scheduling (SQLite is no longer used).
echo      NOTE: ML models take 60-90 seconds to load. Please wait.
start "IPMS-C1-Scheduling" "D:\New folder (91)\svc1_scheduling.bat"
timeout /t 5 /nobreak >nul
echo.

echo  [2] Starting Component 2 - Quality Assessment...
start "IPMS-C2-Quality-API" "D:\New folder (91)\svc2_quality_api.bat"
timeout /t 3 /nobreak >nul
start "IPMS-C2-Quality-UI" "D:\New folder (91)\svc3_quality_ui.bat"
timeout /t 3 /nobreak >nul
echo.

echo  [3] Starting Component 3 - Risk Monitoring (Port 5000 + 5175)...
echo      Authentication remains local to the Risk component.
start "IPMS-C3-Risk-API" "D:\New folder (91)\svc4_risk.bat"
timeout /t 3 /nobreak >nul
start "IPMS-C3-Risk-UI" "D:\New folder (91)\svc7_risk_ui.bat"
timeout /t 3 /nobreak >nul
echo.

echo  [4] Starting Component 4 - Team Formation (Port 8003 + 5174)...
start "IPMS-C4-Team-API" "D:\New folder (91)\svc5_team_api.bat"
timeout /t 3 /nobreak >nul
start "IPMS-C4-Team-UI" "D:\New folder (91)\svc6_team_ui.bat"
timeout /t 3 /nobreak >nul
echo.

echo  Waiting for all component ports to become ready...
powershell -NoProfile -Command "$ports=@(8000,9000,5173,5000,5175,8003,5174); $limit=(Get-Date).AddSeconds(120); do { $missing=@($ports | Where-Object { -not (Test-NetConnection 127.0.0.1 -Port $_ -InformationLevel Quiet -WarningAction SilentlyContinue) }); if($missing.Count -eq 0){ exit 0 }; Start-Sleep -Seconds 2 } while((Get-Date) -lt $limit); Write-Host ('Timed out waiting for ports: ' + ($missing -join ', ')); exit 1"
if errorlevel 1 (
    color 0E
    echo  [WARNING] One or more components did not become ready within 120 seconds.
    echo            Check the individual component windows for the exact error.
) else (
    echo      All component ports are accepting connections.
)

echo  Opening IPMS Login Page in browser...
start "" "http://127.0.0.1:8000/home"
timeout /t 2 /nobreak >nul

echo.
echo  ================================================================
echo   ALL SERVICES STARTED
echo  ================================================================
echo   PostgreSQL         : localhost:5432
echo   C1 Scheduling      : http://127.0.0.1:8000/home
echo   C2 Quality API     : http://127.0.0.1:9000
echo   C2 Quality UI      : http://127.0.0.1:5173
echo   C3 Risk API        : http://127.0.0.1:5000
echo   C3 Risk UI/Login   : http://127.0.0.1:5175/login
echo   C4 Team API        : http://127.0.0.1:8003
echo   C4 Team UI         : http://127.0.0.1:5174
echo   Login Page         : http://127.0.0.1:8000/home
echo  ================================================================
echo   Keep ALL 8 service windows open while running!
echo  ================================================================
echo.
pause
