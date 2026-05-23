@echo off
setlocal

cd /d "%~dp0"

where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  python scripts\dev_start.py %*
  exit /b %ERRORLEVEL%
)

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -3 scripts\dev_start.py %*
  exit /b %ERRORLEVEL%
)

echo Python 3.11+ was not found on PATH. Install Python, then rerun start-dev.bat.
exit /b 1
