#!/bin/bash
# Simplified start script - runs the API directly with system Python

echo "🚀 Starting Space Mission Architect API (Simplified Mode)"
echo ""

# Set environment variables
export ENVIRONMENT=development
export DATABASE_URL=sqlite:///./data/space_missions.db
export LOG_LEVEL=INFO
export PYTHONPATH=/Volumes/One\ Touch/SpaceMissionArchitect:$PYTHONPATH

# Create database directory
mkdir -p data

echo "Installing required packages..."
python3 -m pip install --user --quiet uvicorn fastapi sqlalchemy pydantic pyyaml python-dotenv colorlog 2>/dev/null || {
    echo "Note: Some packages may already be installed"
}

echo ""
echo "✅ Starting API server on http://localhost:8000"
echo "📚 API Documentation: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Run the server
python3 -m uvicorn space_mission_architect.api.app:app --host 0.0.0.0 --port 8000 --reload
