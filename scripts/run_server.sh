#!/usr/bin/env bash
# AidChain — start the backend on LinuxONE.
# Generates data + trains models on first run, then launches uvicorn.
set -euo pipefail

cd "$(dirname "$0")/.."

# Activate venv if present
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Generate data + train models if missing
if [ ! -f ml/data/claims.csv ]; then
    echo "==> Generating synthetic dataset..."
    python3 ml/generate_data.py --n 50000
fi

if [ ! -f ml/models/fraud_model.pkl ]; then
    echo "==> Training FraudGuard model..."
    python3 ml/train_fraud.py
fi

if [ ! -f ml/models/vulnerability_model.pkl ]; then
    echo "==> Training PriorityCare model..."
    python3 ml/train_vulnerability.py
fi

echo "==> Launching AidChain on http://0.0.0.0:8000"
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000
