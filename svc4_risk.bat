@echo off
title IPMS C3 - Risk Monitoring [Port 5000]
cd /d "D:\New folder (91)\component_risk\ipms-risk-app"
if exist "..\.venv\Scripts\python.exe" (
    "..\.venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 5000
) else (
    echo [INFO] component_risk\.venv not found; using the active Python installation.
    python -m uvicorn main:app --host 127.0.0.1 --port 5000
)
pause
