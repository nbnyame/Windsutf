@echo off
cd /d "%~dp0"
python splunk_alert_poller.py >> splunk_alert_poller_output.log 2>&1
