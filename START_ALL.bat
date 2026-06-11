@echo off
title IPMS Unified System Launcher
echo ============================================
echo   IPMS Unified System - Starting All Services
echo ============================================
echo.

echo [1/5] Starting Adaptive Scheduling Backend (Port 8000)...
start "IPMS - Scheduling Backend" cmd /k "cd /d %~dp0component_scheduling && set PYTHONUTF8=1&& python -m uvicorn main:app --host 127.0.0.1 --port 8000"

ping 127.0.0.1 -n 4 >nul

echo [2/5] Starting Quality Assessment Backend (Port 8001)...
start "IPMS - Quality Backend" cmd /k "cd /d %~dp0component_quality && set PYTHONUTF8=1&& python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8001"

ping 127.0.0.1 -n 3 >nul

echo [3/5] Starting Quality Assessment Frontend (Port 3000)...
start "IPMS - Quality Frontend" cmd /k "cd /d %~dp0component_quality\frontend && set BROWSER=none&& npm.cmd start"

ping 127.0.0.1 -n 3 >nul

echo [4/5] Starting Risk Monitoring (Port 5000)...
start "IPMS - Risk Monitoring" cmd /k "cd /d %~dp0component_risk\ipms-risk-app && set PYTHONUTF8=1&& python -m uvicorn main:app --host 127.0.0.1 --port 5000"

ping 127.0.0.1 -n 3 >nul

echo [5/5] Starting Team Formation Backend (Port 8003) + Frontend (Port 3001)...
start "IPMS - Team Backend" cmd /k "cd /d %~dp0component_team\intelligent-team-formation-and-topic-feasiblity-analyzis\backend-fastapi && set PYTHONUTF8=1&& python -m uvicorn main:app --host 127.0.0.1 --port 8003"

ping 127.0.0.1 -n 3 >nul

start "IPMS - Team Frontend" cmd /k "cd /d %~dp0component_team\intelligent-team-formation-and-topic-feasiblity-analyzis\frontend && npm.cmd run dev -- --host 127.0.0.1 --port 3001"

echo.
echo ============================================
echo   All services are starting...
echo   Wait ~30 seconds for full boot-up.
echo.
echo   Dashboard:      open index.html manually
echo   Scheduling:     http://127.0.0.1:8000/app
echo   Quality:        http://127.0.0.1:3000
echo   Risk:           http://127.0.0.1:5000
echo   Team Formation: http://127.0.0.1:3001
echo ============================================
ping 127.0.0.1 -t >nul
