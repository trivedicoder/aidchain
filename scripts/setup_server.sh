#!/usr/bin/env bash
# AidChain — one-time server setup on LinuxONE.
# Creates a Python venv and installs all dependencies.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "==> Upgrading pip..."
pip install --upgrade pip

echo "==> Installing dependencies (this may take a few minutes on s390x)..."
pip install -r requirements.txt

echo ""
echo "==> Setup complete."
echo "    Next: bash scripts/run_server.sh"
