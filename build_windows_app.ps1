$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 -m PyInstaller --noconfirm --clean --windowed --name "Proxy Seller Launcher" app.py
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python -m PyInstaller --noconfirm --clean --windowed --name "Proxy Seller Launcher" app.py
} else {
    throw "Python launcher not found. Install Python 3 and retry."
}

Write-Host ""
Write-Host "Build complete."
Write-Host "Executable: $ProjectDir\dist\Proxy Seller Launcher\Proxy Seller Launcher.exe"
