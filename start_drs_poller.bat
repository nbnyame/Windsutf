@echo off
cd /d "%~dp0"
REM Kill any existing DRS poller processes
for /f "tokens=2" %%a in ('wmic process where "commandline like '%%drs_update_poller%%'" get processid /value 2^>nul ^| find "="') do (
    taskkill /PID %%a /F >nul 2>&1
)
python drs_update_poller.py >> drs_poller_output.log 2>&1
