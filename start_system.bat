@echo off
rem TalentMind quick launcher.
rem Double-click to start Docker infra + backend + frontend and open browser.
rem Business logic is in scripts\start-local.ps1. Requires PowerShell 7.
chcp 65001 >nul
cd /d "%~dp0"
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-local.ps1"
echo.
pause
