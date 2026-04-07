@echo off
cd /d "%~dp0"
python sharepoint_poller.py >> poller_output.log 2>&1
