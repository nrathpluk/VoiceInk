@echo off
setlocal

:: Build ThaiVoice installer (.exe wrapper around dist\ThaiVoice.exe)
:: Prereq: Inno Setup 6+ installed (https://jrsoftware.org/isinfo.php)
::         dist\ThaiVoice.exe must already exist (run scripts\build.bat first)

set "HERE=%~dp0"
set "ROOT=%HERE%.."
pushd "%ROOT%"

if not exist "dist\ThaiVoice.exe" (
    echo [ERROR] dist\ThaiVoice.exe not found.
    echo Run scripts\build.bat first to produce the exe.
    popd
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
    popd
    exit /b 1
)

echo Using compiler: %ISCC%
"%ISCC%" "%HERE%installer.iss"
if errorlevel 1 (
    echo [ERROR] Inno Setup compilation failed.
    popd
    exit /b %errorlevel%
)

echo.
echo Done. Installer: dist\ThaiVoice-Setup-0.1.0.exe
popd
endlocal
