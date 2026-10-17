@echo off
cd /d "%~dp0"
where py >nul 2>nul && (py dashboard\launcher.py & exit /b)
where python >nul 2>nul && (python dashboard\launcher.py & exit /b)
echo Python 3 is required.
pause
exit /b 1
