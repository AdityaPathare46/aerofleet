#!/usr/bin/env bash
# AeroFleet — friend's-PC batch runner (Linux / macOS)
# Runs batches 15-26 of the 1,000-case mass forensics study on this machine.
#
# Usage:
#   chmod +x friend_pc_runner.sh
#   ./friend_pc_runner.sh
#
# Safe to re-run any time (Ctrl+C, close the terminal, reboot) — progress is
# saved per-case to mass_forensics_friend/results.jsonl on this machine's own
# disk, and re-running this script picks up exactly where it left off. No
# manual "resume" step needed — that's a Kaggle/Colab-specific problem this
# doesn't have, since nothing gets wiped between runs.

set -e

echo "=== AeroFleet — friend's-PC batch runner (batches 15-26) ==="
echo

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
    echo "ERROR: Ollama did not start. Check ollama_serve.log in this directory."
    exit 1
fi
echo "Ollama is up."
echo

# 3. Pull the model (~3.2GB, only happens once — skipped if already present)
echo "Pulling phi4-mini-reasoning..."
ollama pull phi4-mini-reasoning
echo

# 4. Clone (or update) the private repo.
#
# IMPORTANT: the token is passed as an HTTP header (-c http.extraheader), never
# embedded in the URL. A URL-embedded token gets echoed back verbatim by git's
# own error messages (e.g. "repository not found") — a real credential leak
# that happened during testing. A header is never echoed back either way.
#
# Asks once per terminal session (if GH_PAT isn't already set) and reuses it
# for the rest of this session — close the terminal and it'll ask again next
# time, which is the deliberate, safer default over saving it to disk.
if [ -z "$GH_PAT" ]; then
    read -sp "Paste your GitHub token (read access to AdityaPathare46/aerofleet): " GH_PAT
    echo
fi

REPO_DIR="aerofleet"
AUTH_HEADER="AUTHORIZATION: bearer ${GH_PAT}"
if [ ! -d "$REPO_DIR" ]; then
    git -c http.extraheader="$AUTH_HEADER" clone --depth 1 "https://github.com/AdityaPathare46/aerofleet.git" "$REPO_DIR"
else
    echo "Repo already present — pulling latest."
    (cd "$REPO_DIR" && git -c http.extraheader="$AUTH_HEADER" pull)
fi
cd "$REPO_DIR"

# 5. Python environment
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt

# 6. Confirm Ollama is really reachable before committing to a long run
python3 -c "
import requests, sys
try:
    r = requests.get('http://localhost:11434/api/tags', timeout=5)
    print('Ollama reachable:', r.json())
except Exception as e:
    print('Ollama NOT reachable:', e)
    sys.exit(1)
"

# 7. Run the harness — this machine's assigned batch range
export OLLAMA_HOST="http://localhost:11434"
unset USE_MOCK_AGENTS

STUDY_DIR="../mass_forensics_friend"
mkdir -p "$STUDY_DIR"

echo
echo "Starting the harness — batches 15-26 (cases MFI-00351 - MFI-00650)."
echo "This runs for a long time. Leave this terminal window open, or run it"
echo "inside tmux/screen if you want to close the terminal and keep it going."
echo

python -m scenario_engine.mass_forensics_evaluation \
    --study-dir "$STUDY_DIR" \
    --target 1000 --batch-size 25 \
    --only-batches 15-26 \
    --retry-failed-max 5

echo
echo "Stopped (finished, or you interrupted it — either way, progress is saved)."
echo "Results are in: $STUDY_DIR/results.jsonl"
echo "Send that whole '$STUDY_DIR' folder back when ready to merge with the other machines."
