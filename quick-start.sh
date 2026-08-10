#!/bin/bash
# Quick Start - Minimal API Dependencies Only
# This gets the API running fast, full features can be installed later

echo "🚀 Quick Start - Installing minimal API dependencies..."

# Clean up
rm -rf venv
find . -name "._*.egg-info" -o -name "*.egg-info" -type d 2>/dev/null | xargs rm -rf 2>/dev/null

# Create fresh venv
python3.10 -m venv venv
source venv/bin/activate

# Install ONLY what's needed for the API to run (fast!)
echo "📦 Installing core API dependencies (takes ~30 seconds)..."
pip install -q --upgrade pip
pip install -q uvicorn fastapi sqlalchemy pydantic pyyaml python-dotenv colorlog numpy

# Set environment
export DATABASE_URL=sqlite:///./data/space_missions.db
export ENVIRONMENT=development
mkdir -p data

echo ""
echo "✅ Starting API server on http://localhost:8000"
echo "📚 API Documentation: http://localhost:8000/docs"
echo ""
echo "ℹ️  Note: Running with minimal dependencies"
echo "   Some advanced features (trajectory, plotting) disabled"
echo "   To install full features later: pip install -r requirements.txt"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start server
python -m uvicorn space_mission_architect.api.app:app --reload --port 8000
