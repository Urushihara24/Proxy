#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is required on macOS."
  echo "Install Homebrew first: https://brew.sh"
  exit 1
fi

echo "[1/5] Installing system dependencies (python@3.12, python-tk@3.12)..."
brew install python@3.12 python-tk@3.12 >/dev/null

PYTHON_BIN="/opt/homebrew/bin/python3.12"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "python3.12 was not found at $PYTHON_BIN after install."
  exit 1
fi

echo "[2/5] Creating virtual environment (.venv-macos)..."
"$PYTHON_BIN" -m venv .venv-macos

echo "[3/5] Installing Python dependencies..."
./.venv-macos/bin/python -m pip install --upgrade pip >/dev/null
./.venv-macos/bin/pip install -r requirements.txt pyinstaller >/dev/null

echo "[4/5] Running Tkinter health check..."
./.venv-macos/bin/python - <<'PY'
import tkinter as tk
root = tk.Tk()
print("Tk patchlevel:", root.tk.call("info", "patchlevel"))
root.destroy()
PY

echo "[5/5] Running project sanity checks..."
./.venv-macos/bin/python -m py_compile app.py desktop_proxy_launcher.py proxy_seller_client.py system_proxy.py

echo
echo "Environment is ready."
echo "Build app: ./build_macos_app.sh"
echo "Run from source: ./.venv-macos/bin/python app.py"
