# Quick Start Guide - No Docker Required

## Running the Application Locally

### 1. Quick Start (Recommended)

Run the startup script:
```bash
./start.sh
```

This will:
- Create a virtual environment
- Install all dependencies
- Set up the database
- Start the API server on http://localhost:8000

### 2. Manual Setup

If you prefer manual setup:

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e .

# Set environment variables
export DATABASE_URL=sqlite:///./data/aerofleet.db
export ENVIRONMENT=development

# Run API server
uvicorn aerofleet.api.app:app --reload
```

### 3. Access the Application

Once running:
- **API Documentation**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

### 4. Test the API

Try these endpoints:

**Check the fleet**:
```bash
curl "http://localhost:8000/api/v1/fleet/depots"
curl "http://localhost:8000/api/v1/fleet/drones"
```

**Calculate a Route**:
```bash
curl -X POST "http://localhost:8000/api/v1/routes/calculate" \
  -H "Content-Type: application/json" \
  -d '{
    "origin_lat": 18.5204, "origin_lon": 73.8567,
    "destination_lat": 18.53, "destination_lon": 73.86,
    "payload_kg": 1.5
  }'
```

See [API_TEST_GUIDE.md](API_TEST_GUIDE.md) for the full register → order → dispatch flow.

**Get Agent Roster**:
```bash
curl "http://localhost:8000/api/v1/agents/roster"
```

---

## Running with Docker

```bash
docker compose up --build
```

Starts Postgres, Redis, and the API (`http://localhost:8000`). Only these
three services exist — an earlier `dashboard`/`nginx` pair referenced
files that were never built and has been removed; the real UI is the
Tauri desktop app (`cd tauri-app && npm run tauri dev`), not a
server-rendered dashboard.

The OSM city-graph cache (`./data`) is mounted into the container so
Pune/Mumbai's street graph isn't re-fetched from Overpass on every
restart.

To connect a real drone from inside the container (USB/serial, not
UDP/SITL), see the commented `devices:` block on the `api` service in
`docker-compose.yml` and [`docs/HARDWARE_SETUP.md`](docs/HARDWARE_SETUP.md).

> **On an external/non-APFS drive** (e.g. this repo living on a USB/
> Thunderbolt drive on macOS): `docker compose build` can fail with
> `failed to xattr .../._<file>: operation not permitted` — BuildKit's
> context walker chokes on macOS's shadow `._*` AppleDouble files before
> `.dockerignore` filtering applies. Build with the legacy builder
> instead: `DOCKER_BUILDKIT=0 docker compose build`.

---

## Development Workflow

### Running Tests
```bash
pytest tests/ -v
```

### Code Formatting
```bash
black aerofleet/
```

### Type Checking
```bash
mypy aerofleet/
```

### Linting
```bash
flake8 aerofleet/
```

---

## Troubleshooting

**Issue**: `ModuleNotFoundError`
**Solution**: Make sure you're in the virtual environment and have installed dependencies:
```bash
source venv/bin/activate
pip install -e .
```

**Issue**: Port 8000 already in use
**Solution**: Use a different port:
```bash
uvicorn aerofleet.api.app:app --port 8001 --reload
```

**Issue**: Database errors
**Solution**: Delete and recreate the database:
```bash
rm -rf data/aerofleet.db
# Restart the application
```
