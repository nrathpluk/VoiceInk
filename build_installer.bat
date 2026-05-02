@echo off
setlocal

:: Build ThaiVoice installer (.exe wrapper around dist\ThaiVoice.exe)
:: Prereq: Inno Setup 6+ installed (https://jrsoftware.org/isinfo.php)
::         dist\ThaiVoice.exe must already exist (run build.bat first)

if not exist "dist\ThaiVoice.exe" (
    echo [ERROR] dist\ThaiVoice.exe not found.
    echo Run build.bat first to produce the exe.
    exit /b 1
)

:: Locate ISCC.exe — try standard install paths
set "ISCC="
for %%D in (
    "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
    "%ProgramFiles%\Inno Setup 6\ISCC.exe"
    "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
) do (
    if exist %%D set "ISCC=%%~D"
)

if "%ISCC%"=="" (
    echo [ERROR] Inno Setup compiler ^(ISCC.exe^) not found.
    echo Install from https://jrsoftware.org/isinfo.php
    exit /b 1
)

echo Using compiler: %ISCC%
"%ISCC%" installer.iss
if errorlevel 1 (
    echo [ERROR] Inno Setup compilation failed.
    exit /b %errorlevel%
)

echo.
echo Done. Installer: dist\ThaiVoice-Setup-0.1.0.exe
endlocal
