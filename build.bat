@echo off
REM Build ThaiVoice.exe — slim (UPX + no-CUDA + module excludes)
cd /d "%~dp0"

echo Installing PyInstaller + Pillow...
pip install pyinstaller pillow
if errorlevel 1 goto :error

echo Generating icon.ico...
python make_icon.py
if errorlevel 1 goto :error

REM --- Bootstrap UPX (download once into tools\upx) ---
set UPX_DIR=%~dp0tools\upx
if not exist "%UPX_DIR%\upx.exe" (
    echo Downloading UPX...
    if not exist "%~dp0tools" mkdir "%~dp0tools"
    powershell -NoProfile -Command "$ErrorActionPreference='Stop'; $u='https://github.com/upx/upx/releases/download/v4.2.4/upx-4.2.4-win64.zip'; $z=Join-Path $env:TEMP 'upx.zip'; Invoke-WebRequest -Uri $u -OutFile $z; Expand-Archive -Path $z -DestinationPath '%~dp0tools' -Force; Remove-Item $z"
    if errorlevel 1 goto :error
    REM Move extracted folder contents to tools\upx\
    for /d %%D in ("%~dp0tools\upx-*") do (
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
python -m PyInstaller --noconfirm --clean --upx-dir "%UPX_DIR%" ThaiVoice.spec
if errorlevel 1 goto :error

echo.
echo ====================================
echo Done. Output: dist\ThaiVoice.exe
echo ====================================
pause
exit /b 0

:error
echo.
echo Build failed.
pause
exit /b 1
