@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0exporter\Export-SolidWorks.ps1" -Root "%~dp0."
set "result=%errorlevel%"
echo.
if not "%result%"=="0" echo Export needs attention. Read the message above.
pause
exit /b %result%
