@echo off
REM Run main.py with console + dump stderr to crash.log
cd /d "%~dp0"
echo Running ThaiVoice (debug). Console stays open on crash.
echo Log file: %LOCALAPPDATA%\ThaiVoice\app.log
echo.
python main.py 2> "%~dp0crash.log"
echo.
echo === Process exited with code %ERRORLEVEL% ===
echo Stderr captured to: %~dp0crash.log
echo App log:           %LOCALAPPDATA%\ThaiVoice\app.log
pause
