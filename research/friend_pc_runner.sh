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

# 4. Clone (or update) the private repo — only asks for the token on a fresh
# clone; an already-cloned repo's `git pull` reuses the token already saved
# in its remote URL from the first run, no need to re-enter it.
REPO_DIR="aerofleet"
if [ ! -d "$REPO_DIR" ]; then
    if [ -z "$GH_PAT" ]; then
        read -sp "Paste your GitHub token (read access to AdityaPathare46/aerofleet): " GH_PAT
        echo
    fi
    git clone --depth 1 "https://${GH_PAT}@github.com/AdityaPathare46/aerofleet.git" "$REPO_DIR"
    unset GH_PAT
else
    echo "Repo already present — pulling latest (no token needed, already saved from the first run)."
    (cd "$REPO_DIR" && git pull)
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
