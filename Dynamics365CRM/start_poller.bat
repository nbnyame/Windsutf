@echo off
cd /d "%~dp0"
REM Kill any existing poller processes
for /f "tokens=2" %%a in ('wmic process where "commandline like '%%sharepoint_poller%%'" get processid /value 2^>nul ^| find "="') do (
    taskkill /PID %%a /F >nul 2>&1
)
python sharepoint_poller.py >> poller_output.log 2>&1
