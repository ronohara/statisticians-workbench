#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../backend"

if [ ! -d "venv" ]; then
    echo "ERROR: Virtual environment not found at backend/venv"
    echo "Create it with (from the repository root):"
    echo "  python3 -m venv backend/venv && backend/venv/bin/pip install -r backend/requirements.txt"
    echo "The script activates the venv itself, so there is no need to source it first."
    exit 1
fi

source venv/bin/activate

# Load environment variables from .env
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

exec python main.py
