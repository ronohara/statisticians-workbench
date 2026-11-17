#!/bin/bash
# Start Workbench frontend (Next.js production server)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
cd "$REPO_DIR/frontend"

echo "Starting Workbench frontend..."
export PATH="$HOME/.local/bin:$PATH"
pnpm start
