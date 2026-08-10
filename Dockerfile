# AeroFleet - Multi-stage Dockerfile
FROM python:3.10-slim as base

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt requirements-dev.txt ./

#  Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Development stage
FROM base as development
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY . .
CMD ["uvicorn", "aerofleet.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Production stage
FROM base as production

# Create non-root user
RUN useradd -m -u 1000 aerofleet && \
    chown -R aerofleet:aerofleet /app

# Copy application code
COPY --chown=aerofleet:aerofleet . .

# Install package
RUN pip install --no-cache-dir -e .

# Switch to non-root user
USER aerofleet

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Run application
#
# --workers is pinned to 1, not a placeholder to raise later: FleetState
# (aerofleet/fleet/state.py), DroneLinkRegistry (aerofleet/hardware/
# telemetry_service.py), and AsyncEventBus (aerofleet/api/routes/hardware.py)
# are all plain module-level singletons, one independent copy per OS process.
# Under uvicorn's multi-worker mode each worker is a separate process, so
# >1 worker would each independently run their own hardware telemetry poll
# loop and MAVLink connection to the same real vehicle — a correctness bug
# that becomes a safety one once real hardware is attached. Scaling this
# horizontally needs Redis for the small mutable drone/depot/order state
# (trivial — already JSON-ready via each model's to_dict()) plus a real
# redesign of MAVLink-link ownership and WebSocket fan-out (the actual hard
# part) — not implemented; see PROJECT_SUMMARY.md.
CMD ["uvicorn", "aerofleet.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
