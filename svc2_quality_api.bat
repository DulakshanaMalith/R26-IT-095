@echo off
title IPMS C2 - Quality Assessment Backend [Port 9000]
cd /d "D:\New folder (91)\component_quality\backend"
python -m uvicorn src.api.main:app --host 127.0.0.1 --port 9000
pause
