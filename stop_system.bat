@echo off
rem TalentMind quick shutdown.
rem Stop this workspace's application processes. Preserve Docker data and Edge.
rem Business logic is in scripts\stop-local.ps1. Requires PowerShell 7.
chcp 65001 >nul
cd /d "%~dp0"
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-local.ps1"
echo.
pause
