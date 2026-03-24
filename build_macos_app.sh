#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

python3 -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "Proxy Seller Launcher" \
  app.py

echo
echo "Build complete."
echo "App bundle: $PROJECT_DIR/dist/Proxy Seller Launcher.app"
