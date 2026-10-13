@echo off
setlocal
title IPMS - Student Document Submission Portal
cd /d "%~dp0"
if not defined SCHEDULING_API_URL set "SCHEDULING_API_URL=http://127.0.0.1:8000"
echo Starting standalone Student Document Submission Portal...
echo Scheduling API: %SCHEDULING_API_URL%
echo Portal: http://127.0.0.1:8010
echo Keep this window open while students use the portal.
echo.
start "" powershell -NoProfile -WindowStyle Hidden -Command "$limit=(Get-Date).AddSeconds(30); do { if(Test-NetConnection 127.0.0.1 -Port 8010 -InformationLevel Quiet -WarningAction SilentlyContinue){ Start-Process 'http://127.0.0.1:8010'; exit }; Start-Sleep -Milliseconds 500 } while((Get-Date) -lt $limit)"
python -m uvicorn student_submission_portal.app:app --host 127.0.0.1 --port 8010
pause
