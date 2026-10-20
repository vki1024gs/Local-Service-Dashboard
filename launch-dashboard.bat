@echo off
cd /d "%~dp0"
start "" /b wscript.exe "%~dp0launch-dashboard.vbs"
exit /b
