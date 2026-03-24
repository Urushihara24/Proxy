$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir

# Prefer "python" first. In CI this points to actions/setup-python interpreter.
if (Get-Command python -ErrorAction SilentlyContinue) {
    & python -m PyInstaller --noconfirm --clean --windowed --name "Proxy Seller Launcher" app.py
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    # Fallback for local machines where "python" is missing from PATH.
    if ((& py -3.12 -c "import sys; print(sys.version_info[:2])" 2>$null)) {
        & py -3.12 -m PyInstaller --noconfirm --clean --windowed --name "Proxy Seller Launcher" app.py
    } else {
        & py -3 -m PyInstaller --noconfirm --clean --windowed --name "Proxy Seller Launcher" app.py
    }
} else {
    throw "Python launcher not found. Install Python 3 and retry."
}

Write-Host ""
Write-Host "Build complete."
Write-Host "Executable: $ProjectDir\dist\Proxy Seller Launcher\Proxy Seller Launcher.exe"
