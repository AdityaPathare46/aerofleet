#!/bin/bash
# Final working startup script

echo "🚀 Space Mission Architect API - Starting..."

# Set environment variables
export DATABASE_URL=sqlite:///./data/space_missions.db
export ENVIRONMENT=development
export PYTHONPATH="/Volumes/One Touch/SpaceMissionArchitect:$PYTHONPATH"

# Create data directory
mkdir -p data

# Install missing Python packages into pipx uvicorn environment
echo "📦 Installing dependencies..."
pipx inject uvicorn numpy ollama 2>/dev/null || echo "Dependencies already installed"

echo ""
echo "✅ Starting API server on http://localhost:8000"
echo "📚 API Documentation: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start the server using pipx's Python
~/.local/pipx/venvs/uvicorn/bin/python -m uvicorn space_mission_architect.api.app:app --reload --port 8000
