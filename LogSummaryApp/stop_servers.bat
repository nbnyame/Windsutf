@echo off
echo Stopping CRM Log Summary servers...

taskkill /F /IM node.exe 2>nul
taskkill /F /FI "WINDOWTITLE eq Flask*" /IM python.exe 2>nul
taskkill /F /FI "COMMANDLINE eq *app.py*" /IM python.exe 2>nul

echo Servers stopped.
timeout /t 2 /nobreak >nul
