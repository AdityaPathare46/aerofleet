"""FastAPI application for the AeroFleet drone-dispatch REST API."""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from aerofleet.agents.explanation_worker import (
    start_background_explanation_worker,
    stop_background_explanation_worker,
)
from aerofleet.agents.incident_forensics_worker import (
    start_background_incident_forensics_worker,
    stop_background_incident_forensics_worker,
)
from aerofleet.agents.policy_review_worker import (
    start_background_policy_review_worker,
    stop_background_policy_review_worker,
)
from aerofleet.api.rate_limit import limiter
from aerofleet.api.routes import (
    admin,
    agents,
    auth,
    cities,
    fc_compliance,
    fleet,
    geofence,
    hardware,
    incidents,
    orders,
    policy,
    pomdp,
    routes,
    safety,
    settings,
)
from aerofleet.data.database import get_db_session, init_db
from aerofleet.hardware.fc_inspection_worker import (
    start_background_fc_inspection_worker,
    stop_background_fc_inspection_worker,
)
from aerofleet.utils.config import get_config
from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)

# Initialize configuration
config = get_config()

# Create FastAPI app
app = FastAPI(
    title="AeroFleet API",
    description="REST API for neuro-symbolic drone-fleet dispatch and airspace deconfliction",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.api.cors_origins,
    allow_origin_regex=r"^(https?://(localhost|127\.0\.0\.1|tauri\.localhost)(:\d+)?|tauri://.+)$",
    allow_credentials=config.api.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting — applied per-endpoint via @limiter.limit(...) in the route
# modules that need it (login, dispatch, hardware control); this just wires
# the shared limiter (aerofleet/api/rate_limit.py) into the app.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("Starting AeroFleet API")
    init_db()
    logger.info("Database initialized")
    with get_db_session() as db:
        auth.ensure_bootstrap_admin(db)
    hardware.start_background_polling()
    logger.info("Hardware telemetry poll loop started")
    hardware.start_background_redis_listener()
    if hardware.redis_bridge.redis_enabled:
        logger.info("Redis event relay active — telemetry fanout works across multiple workers")
    start_background_explanation_worker()
    logger.info("Council explanation worker started (async, never on the dispatch critical path)")
    start_background_policy_review_worker()
    logger.info("Policy review worker started (slow-cadence, human-approval-gated)")
    start_background_incident_forensics_worker()
    logger.info("Incident forensics worker started (auto-triggered, async, never on the decision path)")
    start_background_fc_inspection_worker()
    logger.info("Flight-controller compliance inspection worker started")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down AeroFleet API")
    hardware.stop_background_polling()
    hardware.stop_background_redis_listener()
    stop_background_explanation_worker()
    stop_background_incident_forensics_worker()
    stop_background_policy_review_worker()
    stop_background_fc_inspection_worker()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "AeroFleet API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "environment": config.environment}


# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(orders.router, prefix="/api/v1/orders", tags=["orders"])
app.include_router(routes.router, prefix="/api/v1/routes", tags=["routing"])
app.include_router(fleet.router, prefix="/api/v1/fleet", tags=["fleet"])
app.include_router(cities.router, prefix="/api/v1/cities", tags=["cities"])
app.include_router(geofence.router, prefix="/api/v1/geofence", tags=["geofence"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["agents"])
# CBF safety gate
app.include_router(safety.router, prefix="/api/v1/safety", tags=["safety"])
# Formal specification & patent-claim reference
app.include_router(pomdp.router, prefix="/api/v1/pomdp", tags=["formal-specification"])
# Real drone hardware — MAVLink connection lifecycle, manual overrides, kill switch
app.include_router(hardware.router, prefix="/api/v1/hardware", tags=["hardware"])
# Flight-controller compliance check — auto-detect (Mission Planner forward / USB), inspect, report, motor test
app.include_router(fc_compliance.router, prefix="/api/v1/hardware/fc", tags=["hardware", "compliance"])
# LLM connection settings — local/Tailscale/OpenRouter mode switch
app.include_router(settings.router, prefix="/api/v1/settings", tags=["settings"])
# Fleet-level CBF threshold policy proposals — council-drafted, operator-approved
app.include_router(policy.router, prefix="/api/v1/policy", tags=["policy"])
# Fleet incident forensics — auto-triggered multi-agent root-cause investigation
app.include_router(incidents.router, prefix="/api/v1/incidents", tags=["incidents"])


if __name__ == "__main__":
    uvicorn.run(
        "aerofleet.api.app:app",
        host=config.api.host,
        port=config.api.port,
        reload=config.api.reload,
        workers=config.api.workers if not config.api.reload else 1,
    )
