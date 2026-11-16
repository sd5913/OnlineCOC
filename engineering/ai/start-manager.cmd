@echo off
setlocal
cd /d "%~dp0..\.."
engineering\.venv\Scripts\python.exe -B engineering\ai\scripts\manager.py %*
if errorlevel 1 pause
