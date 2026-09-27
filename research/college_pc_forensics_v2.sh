#!/usr/bin/env bash
# AeroFleet — forensics v2 experiment on a Linux/macOS machine (ZIP-based, no git, no tokens).
# Same as college_pc_forensics_v2.ps1. Usage, from the extracted repo folder:
#   bash research/college_pc_forensics_v2.sh [N]      (N = unseen cases per dataset, default 60)
# Resumable; send back research/results/forensics_v2 when done.
set -euo pipefail
N="${1:-60}"
[ -f requirements.txt ] && [ -d research/forensics_v2 ] || { echo "Run from the extracted repo folder."; exit 1; }
command -v ollama >/dev/null || { echo "Install Ollama first: https://ollama.com/download"; exit 1; }
curl -sf http://localhost:11434/api/tags >/dev/null || { (ollama serve >/dev/null 2>&1 &); sleep 6; }
ollama pull phi4-mini-reasoning
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q --upgrade pip && pip install -q -r requirements.txt
export OLLAMA_HOST=http://localhost:11434 AEROFLEET_VR_NETWORK=off
unset USE_MOCK_AGENTS || true
python -m research.forensics_v2.run --condition C0 C1 C2 C3 C4 --dataset eval --n "$N"
python -m research.forensics_v2.run --condition C0 C4 --dataset hard --n "$N"
python -m research.forensics_v2.analyze
echo "Done. Send back: research/results/forensics_v2"
