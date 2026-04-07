@echo off
echo ============================================
echo   Winmark Onboarding Guide - Starting...
echo ============================================
echo.
cd /d "%~dp0"
echo Installing dependencies (if needed)...
cd backend
python -m pip install -r requirements.txt -q >nul 2>&1
cd ..
echo.
echo Starting server (browser will open automatically)...
echo Close the browser tab to shut down the server.
echo.
start "" pythonw launcher.py
echo ============================================
echo   Server is running. You may close this window.
echo ============================================
timeout /t 4 /nobreak >nul
