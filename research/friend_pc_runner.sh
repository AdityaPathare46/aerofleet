#!/usr/bin/env bash
# AeroFleet — friend's-PC batch runner (Linux / macOS), ZIP-based, no token/git.
#
# Setup:
#   1. On github.com (logged in as a collaborator on the repo), click the
#      green "Code" button -> "Download ZIP".
#   2. Extract it. You should see requirements.txt, scenario_engine/, etc.
#      directly inside the extracted folder.
#   3. Put this script (friend_pc_runner.sh) into that same extracted folder.
#   4. chmod +x friend_pc_runner.sh && ./friend_pc_runner.sh
#
# Runs batches 15-26 of the 1,000-case mass forensics study on this machine.
# Safe to re-run any time (Ctrl+C, close the terminal, reboot) — progress is
# saved per-case to mass_forensics_friend/results.jsonl on this machine's own
# disk, and re-running this script picks up exactly where it left off.

set -e

echo "=== AeroFleet — friend's-PC batch runner (batches 15-26) ==="
echo

# 0. Sanity check: are we actually inside the extracted repo?
if [ ! -f "requirements.txt" ] || [ ! -d "scenario_engine" ]; then
    echo "ERROR: requirements.txt or scenario_engine/ not found in this folder."
    echo "Move this script INSIDE the extracted repo folder (the one that has"
    echo "requirements.txt directly in it) and run it from there."
    exit 1
fi

# 1. Check Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "Ollama isn't installed. Install it first, then re-run this script:"
    echo "  Linux: curl -fsSL https://ollama.com/install.sh | sh"
    echo "  macOS: brew install ollama   (or https://ollama.com/download/mac)"
    exit 1
fi

# 2. Start the Ollama server if it isn't already running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "Starting Ollama server..."
    ollama serve > ollama_serve.log 2>&1 &
    sleep 5
fi

if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "ERROR: Ollama did not start. Check ollama_serve.log in this folder."
    exit 1
fi
echo "Ollama is up."
echo

# 3. Pull the model (~3.2GB, only happens once)
echo "Pulling phi4-mini-reasoning..."
ollama pull phi4-mini-reasoning
echo

# 4. Python environment
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt

# 5. Confirm Ollama is really reachable before committing to a long run
python3 -c "
import requests, sys
try:
    r = requests.get('http://localhost:11434/api/tags', timeout=5)
    print('Ollama reachable:', r.json())
except Exception as e:
    print('Ollama NOT reachable:', e)
    sys.exit(1)
"

# 6. Run the harness — this machine's assigned batch range.
# Change ONLY_BATCHES below if you've been assigned a different range —
# just double-check it doesn't overlap whatever the other machines are
# already covering.
ONLY_BATCHES="15-26"

export OLLAMA_HOST="http://localhost:11434"
unset USE_MOCK_AGENTS

STUDY_DIR="mass_forensics_friend"
mkdir -p "$STUDY_DIR"

echo
echo "Starting the harness — batches ${ONLY_BATCHES}."
echo "This runs for a long time. Leave this terminal window open, or run it"
echo "inside tmux/screen if you want to close the terminal and keep it going."
echo

python -m scenario_engine.mass_forensics_evaluation \
    --study-dir "$STUDY_DIR" \
    --target 1000 --batch-size 25 \
    --only-batches "$ONLY_BATCHES" \
    --retry-failed-max 5

echo
echo "Stopped (finished, or you interrupted it — either way, progress is saved)."
echo "Results are in: $STUDY_DIR/results.jsonl"
echo "Send that whole '$STUDY_DIR' folder back when ready to merge with the other machines."
