@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-game.ps1" %*
set "SETUP_RESULT=%errorlevel%"
if not "%SETUP_RESULT%"=="0" pause
exit /b %SETUP_RESULT%
