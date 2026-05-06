@echo off
echo Installing frontend dependencies...
cd /d "%~dp0frontend"
call npm install
echo.
echo Dependencies installed!
pause
