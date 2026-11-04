@echo off
cd /d "%~dp0"
title Sony Headphones Control

if exist "SonyHeadphonesControl.exe" (
  start "" "SonyHeadphonesControl.exe" %*
  exit /b 0
)

echo [Standalone exe not found - running from Python source]
where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found in PATH. Run  python build.py  first.
  pause
  exit /b 1
)
python appmain.py %*
pause
