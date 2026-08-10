#!/bin/bash
# AeroFleet API - one-command local startup (no Docker required)
set -e

cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "Creating virtual environment (.venv, Python 3.10)..."
  python3.10 -m venv .venv
fi

source .venv/bin/activate

echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

export DATABASE_URL="${DATABASE_URL:-sqlite:///./aerofleet.db}"
export ENVIRONMENT="${ENVIRONMENT:-development}"
# No Ollama server reachable? Run the whole pipeline against the
# deterministic mock agent backend instead:
#   USE_MOCK_AGENTS=true ./start.sh
mkdir -p data logs

echo ""
echo "Starting AeroFleet API on http://localhost:8000"
echo "API docs: http://localhost:8000/docs"
echo ""

exec python -m uvicorn aerofleet.api.app:app --reload --host 0.0.0.0 --port 8000
