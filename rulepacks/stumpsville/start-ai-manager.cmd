@echo off
title Stumpsville - AI provider manager
set PYTHONUTF8=1
set PYTHONDONTWRITEBYTECODE=1
"%~dp0..\..\engineering\.venv\Scripts\python.exe" -B "%~dp0..\..\engineering\ai\scripts\manager.py" --config "%~dp0..\..\engineering\ai\config\ai-providers.json" --data-dir "%~dp0runtime\ai-manager" %*
pause
