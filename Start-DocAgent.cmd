@echo off
setlocal
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-windows-portable.ps1" -OpenBrowser %*

if errorlevel 1 (
  echo.
  echo Doc Agent failed to start. See the error above.
  pause
)
