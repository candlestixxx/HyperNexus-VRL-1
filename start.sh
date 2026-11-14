#!/usr/bin/env bash
set -e

echo "=================================================================="
echo "  HyperNexus VRL-1: Universal Multi-Tenant API Gateway"
echo "  United Beats Flagship Control Plane & Radial Vector Vault"
echo "=================================================================="

if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 could not be found."
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "[INFO] Creating virtual environment 'venv'..."
    python3 -m venv venv
fi

source venv/bin/activate
echo "[INFO] Installing requirements..."
pip install -r requirements.txt --quiet

echo "[INFO] Starting HyperNexus VRL-1 on port 8000..."
echo "[INFO] Developer Portal: http://localhost:8000/portal"
python3 main.py
