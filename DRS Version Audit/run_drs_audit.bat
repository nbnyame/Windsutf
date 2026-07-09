@echo off
cd /d "%~dp0"
title DRS Version Audit
pythonw drs_audit_gui.py
if %errorlevel% neq 0 (
    python drs_audit_gui.py
    pause
)
