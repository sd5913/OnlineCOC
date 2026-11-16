@echo off
setlocal
if exist "%~dp0.venv\Scripts\python.exe" goto run
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
if errorlevel 1 goto failed
:run
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
if errorlevel 1 goto failed
exit /b 0
:failed
echo Startup failed. Python 3.14 x64 is required. See README.txt or README.md.
pause
exit /b 1
