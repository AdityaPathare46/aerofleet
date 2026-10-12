#!/usr/bin/env bash
# AeroFleet 2.0 — review-panel evaluation on Linux or macOS. Instructions: docs/aerofleet2/PANEL_EVAL_RUNBOOK.md
#
#   bash research/college_pc_panel_eval.sh                         # default models, 60 cases
#   MODELS="qwen2.5:14b,qwen2.5:7b" N=30 bash research/college_pc_panel_eval.sh
#
# Safe to stop and re-run: it continues where it left off. Send back: research/results/panel_eval
set -euo pipefail
MODELS="${MODELS:-qwen2.5:7b,llama3.2}"
N="${N:-60}"
[ -f research/panel_eval/run.py ] || { echo "Run this from the repo folder (the one containing 'research')."; exit 1; }
command -v ollama >/dev/null || { echo "Ollama isn't installed: https://ollama.com/download"; exit 1; }
curl -s -m 3 localhost:11434/api/tags >/dev/null || { echo "Starting Ollama..."; (ollama serve >/dev/null 2>&1 &); sleep 6; }
[ -d .venv-panel ] || python3 -m venv .venv-panel
. .venv-panel/bin/activate
python -m pip install --quiet requests
IFS=',' read -ra LIST <<< "$MODELS"
for model in "${LIST[@]}"; do
  model="$(echo "$model" | xargs)"; [ -n "$model" ] || continue
  echo; echo "--- $model: downloading if needed ---"; ollama pull "$model"
  echo "--- $model: running $N cases ---"; python -m research.panel_eval.run --n "$N" --model "$model"
done
echo; echo "=== Report ==="
python -m research.panel_eval.run --report
python -m research.panel_eval.injection_reach >/dev/null 2>&1 || true
echo; echo "Done. Send back the folder: research/results/panel_eval"
