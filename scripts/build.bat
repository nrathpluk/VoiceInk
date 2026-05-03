@echo off
REM Build ThaiVoice.exe — slim (UPX + no-CUDA + module excludes)
REM Resolve project root from this script's directory (scripts\ -> ..)
set "ROOT=%~dp0.."
pushd "%ROOT%"

echo Installing PyInstaller + Pillow...
pip install pyinstaller pillow
if errorlevel 1 goto :error

echo Generating packaging\icon.ico...
python "%ROOT%\scripts\make_icon.py"
if errorlevel 1 goto :error

REM --- Bootstrap UPX (download once into tools\upx) ---
set "UPX_DIR=%ROOT%\tools\upx"
if not exist "%UPX_DIR%\upx.exe" (
    echo Downloading UPX...
    if not exist "%ROOT%\tools" mkdir "%ROOT%\tools"
    powershell -NoProfile -Command "$ErrorActionPreference='Stop'; $u='https://github.com/upx/upx/releases/download/v4.2.4/upx-4.2.4-win64.zip'; $z=Join-Path $env:TEMP 'upx.zip'; Invoke-WebRequest -Uri $u -OutFile $z; Expand-Archive -Path $z -DestinationPath '%ROOT%\tools' -Force; Remove-Item $z"
    if errorlevel 1 goto :error
    REM Move extracted folder contents to tools\upx\
    for /d %%D in ("%ROOT%\tools\upx-*") do (
        if not exist "%UPX_DIR%" mkdir "%UPX_DIR%"
        move /Y "%%D\*" "%UPX_DIR%\" >nul
        rmdir "%%D"
    )
)

if not exist "%UPX_DIR%\upx.exe" (
    echo UPX bootstrap failed.
    goto :error
)

REM Kill running exe + free the dist file (avoid PermissionError on rebuild)
taskkill /IM ThaiVoice.exe /F >nul 2>&1
if exist "dist\ThaiVoice.exe" del /F /Q "dist\ThaiVoice.exe" >nul 2>&1

echo Building (UPX + no-CUDA, via spec)...
python -m PyInstaller --noconfirm --clean --upx-dir "%UPX_DIR%" "%ROOT%\packaging\ThaiVoice.spec"
if errorlevel 1 goto :error

echo.
echo ====================================
echo Done. Output: dist\ThaiVoice.exe
echo ====================================
popd
pause
exit /b 0

:error
echo.
echo Build failed.
popd
pause
exit /b 1
