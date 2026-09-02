@echo off
rem TalentMind quick launcher.
rem Double-click to start Docker infra + backend + frontend and open browser.
rem Only ASCII characters allowed in this file (business logic is in scripts\start_system.ps1).
chcp 65001 >nul
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_system.ps1"
echo.
pause