@echo off
echo Creating desktop shortcut for CRM Log Summary Dashboard...
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0create_desktop_shortcut.ps1"

echo.
echo Done!
pause
