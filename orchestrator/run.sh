#!/bin/bash
# Beacon — Full orchestration entry point
# Usage: bash orchestrator/run.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🌟 Beacon — Starting orchestration..."

# Run the Python orchestrator
python3 "$ROOT_DIR/orchestrator/orchestrate.py"

echo ""
echo "To view the dashboard, run:"
echo "  cd $ROOT_DIR/app && python3 -m http.server 3333"
echo "  Then open http://localhost:3333"
