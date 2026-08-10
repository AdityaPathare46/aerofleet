#!/bin/bash
# Ultra-Simple Start - No venv, just run with system Python 3.10 directly

echo "🚀 Ultra-Simple Start - Running API with system Python 3.10..."

# Kill any existing process on port 8000
lsof -ti:8000 | xargs kill -9 2>/dev/null || true

# Set environment
export DATABASE_URL=sqlite:///./data/space_missions.db
export ENVIRONMENT=development  
export PYTHONPATH="/Volumes/One Touch/SpaceMissionArchitect:$PYTHONPATH"

# Create data directory
mkdir -p data

echo ""
echo "✅ Starting API server on http://localhost:8000"
echo "📚 API Documentation: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Run directly with Python 3.10 and pipx's uvicorn
~/.local/pipx/venvs/uvicorn/bin/python -m uvicorn space_mission_architect.api.app:app --reload --host 0.0.0.0 --port 8000
