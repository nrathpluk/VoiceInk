@echo off
REM Run main.py with console + dump stderr to crash.log
set "ROOT=%~dp0.."
pushd "%ROOT%"
echo Running ThaiVoice (debug). Console stays open on crash.
echo Log file: %LOCALAPPDATA%\ThaiVoice\app.log
echo.
python main.py 2> "%ROOT%\crash.log"
echo.
echo === Process exited with code %ERRORLEVEL% ===
echo Stderr captured to: %ROOT%\crash.log
echo App log:           %LOCALAPPDATA%\ThaiVoice\app.log
popd
pause
