#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "==============================================================================="
echo " Propeller CFD // STEP Generator - Unix Launcher"
echo "==============================================================================="

if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 could not be found. Please install Python 3.10+."
    exit 1
fi

if [ ! -f "venv/bin/python" ]; then
    echo "[SETUP] Creating local virtual environment in ./venv ..."
    python3 -m venv venv
    echo "[SETUP] Upgrading pip..."
    venv/bin/pip install --upgrade pip
    echo "[SETUP] Installing requirements from requirements.txt..."
    venv/bin/pip install -r requirements.txt
fi

echo "[INFO] Starting Propeller CFD Generator..."
venv/bin/python main.py
