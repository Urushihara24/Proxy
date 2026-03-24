#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

PYTHON_BIN="$PROJECT_DIR/.venv-macos/bin/python"
PIP_BIN="$PROJECT_DIR/.venv-macos/bin/pip"

if [[ ! -x "$PYTHON_BIN" ]]; then
  if [[ -x "/opt/homebrew/bin/python3.12" ]]; then
    /opt/homebrew/bin/python3.12 -m venv "$PROJECT_DIR/.venv-macos"
  else
    echo "Homebrew Python 3.12 not found at /opt/homebrew/bin/python3.12"
    echo "Install it first: brew install python@3.12 python-tk@3.12"
    exit 1
  fi
fi

"$PYTHON_BIN" -m pip install --upgrade pip >/dev/null
"$PIP_BIN" install -r requirements.txt pyinstaller >/dev/null

"$PYTHON_BIN" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "Proxy Seller Launcher" \
  app.py

echo
echo "Build complete."
echo "App bundle: $PROJECT_DIR/dist/Proxy Seller Launcher.app"
