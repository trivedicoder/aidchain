#!/usr/bin/env bash
# AidChain — one-time server setup on LinuxONE (s390x).
#
# Hybrid install: heavy ML libs via apt (s390x has pre-built packages),
# pure-Python web stack via pip into a venv that inherits system packages.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Installing system packages (numpy/pandas/scipy/sklearn via apt)..."
sudo apt update
sudo apt install -y \
    python3-numpy python3-pandas python3-scipy \
    python3-sklearn python3-joblib \
    python3-venv python3-pip \
    pkg-config build-essential

# Wipe any old venv that didn't have system-site-packages
if [ -d "venv" ]; then
    echo "==> Removing existing venv to recreate with system-site-packages..."
    rm -rf venv
fi

echo "==> Creating Python virtual environment (with system site packages)..."
python3 -m venv --system-site-packages venv
source venv/bin/activate

echo "==> Upgrading pip..."
pip install --upgrade pip

echo "==> Installing pip-only dependencies (FastAPI web stack)..."
pip install -r requirements.txt

echo ""
echo "==> Setup complete."
echo "    Next: bash scripts/run_server.sh"
