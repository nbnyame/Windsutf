@echo off
cd /d "%~dp0"
REM Kill any existing poller processes
taskkill /F /FI "WINDOWTITLE eq sharepoint_poller*" >nul 2>&1
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *sharepoint_poller*" >nul 2>&1
python sharepoint_poller.py >> poller_output.log 2>&1
