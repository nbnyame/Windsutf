@echo off
echo ============================================================
echo CRM Log Summary Dashboard - First Time Setup
echo ============================================================
echo.

echo [1/3] Installing Python dependencies...
cd /d "%~dp0backend"
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install Python dependencies
    pause
    exit /b 1
)
echo Python dependencies installed successfully!
echo.

echo [2/3] Installing Node.js dependencies...
cd /d "%~dp0frontend"
call npm install
if %errorlevel% neq 0 (
    echo ERROR: Failed to install Node.js dependencies
    pause
    exit /b 1
)
echo Node.js dependencies installed successfully!
echo.

echo [3/3] Creating desktop shortcut...
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "create_desktop_shortcut.ps1"
echo.

echo ============================================================
echo Setup Complete!
echo ============================================================
echo.
echo You can now launch the app by double-clicking the
echo "CRM Log Summary" icon on your desktop.
echo.
pause
