#!/bin/bash
# Beacon — Run Scout agent (Phase 1 entry point)
# Usage: bash orchestrator/run.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
STATE_FILE="$ROOT_DIR/orchestrator/state.json"
SCOUT_PROMPT_FILE="$ROOT_DIR/agents/scout.md"
SCOUT_OUTPUT="$ROOT_DIR/outputs/reports/scout-report.json"
DASHBOARD_DATA="$ROOT_DIR/dashboard/data"

# Read disease from state.json
DISEASE=$(python3 -c "import json; print(json.load(open('$STATE_FILE'))['disease'])")
PATIENT_NAME=$(python3 -c "import json; print(json.load(open('$STATE_FILE'))['patient']['name'])")

echo "🔬 Beacon — Launching Scout agent for $DISEASE..."
echo "   Patient: $PATIENT_NAME"

# Read scout system prompt
SCOUT_PROMPT=$(cat "$SCOUT_PROMPT_FILE")

# Update state: scout running
python3 -c "
import json, datetime
with open('$STATE_FILE', 'r') as f: state = json.load(f)
state['agents']['scout']['status'] = 'running'
state['agents']['scout']['lastRun'] = datetime.datetime.now().isoformat()
with open('$STATE_FILE', 'w') as f: json.dump(state, f, indent=2)
"

# Run Scout via Claude
echo "   Running Scout..."
claude -p "$SCOUT_PROMPT

The disease is: $DISEASE
The patient's name is: $PATIENT_NAME

Search the web for real, current research on $DISEASE. Output ONLY valid JSON." \
  --model claude-opus-4-6 \
  --dangerously-skip-permissions \
  --output-format json \
  > "$SCOUT_OUTPUT" 2>/dev/null

# Update state: scout complete
python3 -c "
import json, datetime
with open('$STATE_FILE', 'r') as f: state = json.load(f)
state['agents']['scout']['status'] = 'complete'
# Load scout findings count
try:
    with open('$SCOUT_OUTPUT', 'r') as f: report = json.load(f)
    state['agents']['scout']['findings'] = [f['title'] for f in report.get('findings', [])[:5]]
except: pass
with open('$STATE_FILE', 'w') as f: json.dump(state, f, indent=2)
"

# Copy to dashboard data
cp "$SCOUT_OUTPUT" "$DASHBOARD_DATA/scout-report.json"
cp "$STATE_FILE" "$DASHBOARD_DATA/state.json"

echo "✅ Scout complete. Output: $SCOUT_OUTPUT"
echo "   Dashboard data updated."
