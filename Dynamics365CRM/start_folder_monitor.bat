@echo off
cd /d "%~dp0"
echo Starting CRM Case Folder Monitor...
python crm_case_folder_monitor.py >> folder_monitor_output.log 2>&1
pause
