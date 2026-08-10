# Manual Startup Guide - AeroFleet

## ⚠️ Virtual Environment Issue Detected

Your system has Python 3.14 which is creating corrupted virtual environments. Here's how to run the API server manually:

## ✅ Quick Start (3 Steps)

### Step 1: Install Dependencies with Homebrew
```bash
# Install uvicorn via homebrew (cleanest approach)
brew install pipx
pipx install uvicorn
pipx inject uvicorn fastapi sqlalchemy pydantic pyyaml python-dotenv colorlog
```

### Step 2: Set Environment Variables
```bash
export DATABASE_URL=sqlite:///./data/aerofleet.db
export ENVIRONMENT=development
export PYTHONPATH="/Volumes/One Touch/SpaceMissionArchitect:$PYTHONPATH"
mkdir -p data
```

### Step 3: Run the Server
```bash
cd "/Volumes/One Touch/SpaceMissionArchitect"
uvicorn aerofleet.api.app:app --reload --host 0.0.0.0 --port 8000
```

---

## 🔄 Alternative: Use Docker (Recommended for Production)

If you install Docker Desktop in the future:
```bash
docker compose up
```

---

## 🧪 Test the API

Once running, test with:
```bash
# In a new terminal
curl http://localhost:8000/health

# Or visit in browser
open http://localhost:8000/docs
```

---

## 📊 What We Built

✅ Complete REST API with FastAPI  
✅ Database models with SQLAlchemy  
✅ 11-agent council system + 5 trigger-based specialists  
✅ Real OSM city routing + DGCA airspace/geofence model  
✅ Control-Barrier-Function safety gate  
✅ Configuration management  
✅ Structured logging  
✅ Docker & Kubernetes deployment configs  
✅ CI/CD pipeline  

## 🎯 Key Modules

**Core Modules:**
- `aerofleet/city/` - OSM street graph, DGCA airspace/altitude-band model
- `aerofleet/fleet/` - drone/depot/battery models, dispatch engine, digital twin
- `aerofleet/safety/` - CBF gate, airspace conflict pre-screen, emergency landing
- `aerofleet/agents/` - local_agent, factory, council, tools
- `aerofleet/api/` - FastAPI app (orders, routing, fleet, geofence, agents, safety, ws)
- `aerofleet/data/` - database models and loaders
- `aerofleet/utils/` - config, logging, exceptions

**Deployment:**
- `Dockerfile` - multi-stage production build
- `docker-compose.yml` - full stack with PostgreSQL, Redis
- `k8s/deployment.yaml` - Kubernetes with autoscaling
- `.github/workflows/ci-cd.yml` - automated testing & deployment

**Database:**
- SQLAlchemy models: Drone, Depot, Order, Delivery, BatterySwap, Geofence, AgentInteraction
- Alembic migrations ready to run

Your framework is ready to demo! 🚁
