@echo off
title IPMS C1 - Adaptive Scheduling [Port 8000]
cd /d "D:\New folder (91)\component_scheduling"
if not defined SCHEDULING_DATABASE_URL set "SCHEDULING_DATABASE_URL=postgresql://postgres@127.0.0.1:5432/ipms_scheduling"
if not defined ENABLE_T5_WBS set "ENABLE_T5_WBS=0"
echo Database: PostgreSQL ipms_scheduling on 127.0.0.1:5432
echo Optional T5 fallback: disabled for memory-safe startup
python -m uvicorn main:app --host 127.0.0.1 --port 8000
pause
