@echo off
rem TalentMind quick shutdown.
rem Double-click to stop backend + frontend and Docker containers started by start_system.bat.
rem Only ASCII characters allowed in this file (business logic is in scripts\stop_system.ps1).
chcp 65001 >nul
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop_system.ps1"
echo.
pause