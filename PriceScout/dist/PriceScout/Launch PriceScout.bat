@echo off
cd /d "%~dp0"

:: Launch PriceScout hidden (no console window)
start "" /b PriceScout.exe
exit
