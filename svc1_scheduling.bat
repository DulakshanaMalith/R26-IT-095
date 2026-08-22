@echo off
title IPMS [1] Scheduling :8000
cd /d "d:\New folder (91)\component_scheduling"
echo Starting Scheduling Backend on port 8000...
python -m uvicorn main:app --host 127.0.0.1 --port 8000
pause
