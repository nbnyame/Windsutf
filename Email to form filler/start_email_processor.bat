@echo off
setlocal enabledelayedexpansion

echo Starting Email Processor...
start "Email Processor" /MIN cmd /c "title Email Processor && python email_to_form_processor.py && pause"

echo Email Processor started in a new window.
