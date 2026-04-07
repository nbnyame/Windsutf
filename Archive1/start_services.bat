@echo off
setlocal enabledelayedexpansion

echo Starting WindSurf Services...
echo.
echo [1/2] Starting Email Processor...
start "Email Processor" /MIN cmd /c "title Email Processor && python email_processor_gpt4.py && pause"

echo [2/2] Starting Form Filler...
start "Form Filler" /MIN cmd /c "title Form Filler && python form_filler.py && pause"

echo.
echo Both services are now running in the background.
echo Check the taskbar for minimized command windows.
echo.
echo To stop the services, close their respective command windows.
pause
