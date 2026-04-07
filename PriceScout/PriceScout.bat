@echo off
title PriceScout
cd /d "%~dp0"

echo.
echo  ================================
echo   PriceScout - Price Comparison
echo  ================================
echo.

:: Kill any existing PriceScout server on port 5000
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5000 ^| findstr LISTENING 2^>nul') do (
    taskkill /PID %%a /F >nul 2>&1
)

:: Launch the exe (it auto-opens the browser and auto-shuts down when you close the tab)
echo  Starting PriceScout...
echo  (Close the browser tab to stop the server)
echo.
dist\PriceScout\PriceScout.exe
