#!/usr/bin/env bash
# Run Artisan Kaleido from source during local development (macOS/Linux).
# Requires Python 3.12+ on PATH.

set -euo pipefail

cd "$(dirname "$0")"

echo
echo "=== Artisan Kaleido local development startup ==="
echo

if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERROR] python3 was not found on PATH."
    exit 1
fi

PYTHON=python3
if ! "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)'; then
    echo "[ERROR] Python 3.12 or newer is required."
    "$PYTHON" --version
    exit 1
fi

if [[ ! -d artisan_venv ]]; then
    echo "[1/4] Creating virtual environment in src/artisan_venv ..."
    "$PYTHON" -m venv artisan_venv
else
    echo "[1/4] Using existing virtual environment src/artisan_venv"
fi

echo "[2/4] Activating virtual environment ..."
# shellcheck disable=SC1091
source artisan_venv/bin/activate

echo "[3/4] Installing/updating dependencies from requirements.txt ..."
python -m pip install --upgrade pip
pip install -r requirements.txt

echo "[4/4] Starting Artisan ..."
echo
python artisan.py "$@"
