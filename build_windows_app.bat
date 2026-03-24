@echo off
setlocal

cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel%==0 (
  python -m PyInstaller --noconfirm --clean --windowed --name "Proxy Seller Launcher" app.py
) else (
  where py >nul 2>nul
  if %errorlevel%==0 (
    py -3.12 -m PyInstaller --noconfirm --clean --windowed --name "Proxy Seller Launcher" app.py
    if errorlevel 1 py -3 -m PyInstaller --noconfirm --clean --windowed --name "Proxy Seller Launcher" app.py
  ) else (
    echo Python not found. Install Python 3 and retry.
    exit /b 1
  )
)

if errorlevel 1 exit /b 1

echo.
echo Build complete.
echo Executable: %~dp0dist\Proxy Seller Launcher\Proxy Seller Launcher.exe
