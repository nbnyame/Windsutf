@echo off
setlocal

echo ============================================================
echo   Support Center Rule Toggle  ^|  EXE Builder
echo ============================================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Install from https://python.org and re-run.
    echo.
    pause
    exit /b 1
)

echo Step 1/2  Installing packages...
python -m pip install pyinstaller msal requests --quiet --upgrade
if errorlevel 1 (
    echo ERROR: pip install failed.
    pause & exit /b 1
)

echo.
echo Step 2/2  Building executable...
python -m PyInstaller --onefile --windowed ^
    --name "SupportCenter Rule Toggle" ^
    rule_toggle.py

echo.
if exist "dist\SupportCenter Rule Toggle.exe" (
    echo ============================================================
    echo   SUCCESS!
    echo.
    echo   EXE is at:  dist\SupportCenter Rule Toggle.exe
    echo.
    echo   Copy it to:
    echo   K:\02-SOFTWARE\Support Center Inbox\
    echo ============================================================
) else (
    echo BUILD FAILED. Review the errors above.
)

echo.
pause
