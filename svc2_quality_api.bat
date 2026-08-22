@echo off
title IPMS [2] Quality Backend :8001
cd /d "d:\New folder (91)\component_quality"
echo Starting Quality Backend on port 8001...
python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8001
pause
