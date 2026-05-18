@echo off
cd /d "%~dp0"
python crm_case_folder_monitor.py >> folder_monitor_output.log 2>&1
