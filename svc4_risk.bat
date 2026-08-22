@echo off
title IPMS [4] Risk Monitor :5000
cd /d "d:\New folder (91)\component_risk\ipms-risk-app"
echo Starting Risk Backend on port 5000...
python -m uvicorn main:app --host 127.0.0.1 --port 5000
pause
