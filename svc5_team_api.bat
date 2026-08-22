@echo off
title IPMS [5] Team Backend :8003
cd /d "d:\New folder (91)\component_team\intelligent-team-formation-and-topic-feasiblity-analyzis\backend-fastapi"
echo Starting Team Backend on port 8003...
python -m uvicorn main:app --host 127.0.0.1 --port 8003
pause
