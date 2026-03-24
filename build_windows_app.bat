@echo off
setlocal

cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
  py -3 -m PyInstaller --noconfirm --clean --windowed --name "Proxy Seller Launcher" app.py
) else (
  python -m PyInstaller --noconfirm --clean --windowed --name "Proxy Seller Launcher" app.py
)

if errorlevel 1 exit /b 1

echo.
echo Build complete.
echo Executable: %~dp0dist\Proxy Seller Launcher\Proxy Seller Launcher.exe
