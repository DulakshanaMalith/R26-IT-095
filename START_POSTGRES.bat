@echo off
title PostgreSQL 18 Server - Port 5432
color 0B
echo.
echo  ========================================
echo   PostgreSQL 18 - ipms_scheduling
echo   Port: 5432   User: postgres
echo  ========================================
echo.
echo  Starting server... (keep this window open!)
echo.
"D:\New Folder (3)\pgsql\bin\postgres.exe" -D "D:\New Folder (3)\pgsql\data" -p 5432
pause
