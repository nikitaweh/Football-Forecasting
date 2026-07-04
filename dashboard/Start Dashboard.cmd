@echo off
REM Double-click launcher for the ORAKEL R dashboard.
REM Runs run_dashboard.ps1 (installs packages on first run, refreshes data,
REM starts the Shiny server, and opens the browser). Close this window to stop.
title ORAKEL Dashboard
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_dashboard.ps1"
echo.
echo Dashboard stopped. Press any key to close.
pause >nul
