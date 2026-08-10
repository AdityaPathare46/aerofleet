"""Database models for drone fleet dispatch data storage."""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    """User model for authentication."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    # Gates hardware-control endpoints (arm/disarm/emergency-stop) — being
    # able to log in shouldn't be enough to command a real drone. Grant via
    # the admin panel (Phase AI, aerofleet/api/routes/admin.py) rather than
    # raw SQL — the one exception is bootstrapping the very first admin,
    # see AEROFLEET_BOOTSTRAP_ADMIN_USERNAME in auth.py.
    is_operator = Column(Boolean, default=False, nullable=False)
    # Gates the admin panel itself (user list, granting/revoking
    # is_operator and is_admin on other accounts) — deliberately separate
    # from is_operator: flying a drone and managing user permissions are
    # different privilege types, and conflating them would mean any
    # operator could silently mint more operators.
    is_admin = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    orders = relationship("Order", back_populates="owner", cascade="all, delete-orphan")


class Depot(Base):
    """Micro-depot model — a fulfillment/launch node in the city graph."""

    __tablename__ = "depots"

    id = Column(Integer, primary_key=True, index=True)
    depot_id = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    node_id = Column(Integer)             # city street-graph node id
    lat = Column(Float)
    lon = Column(Float)

    launch_pad_slots = Column(Integer, default=4)
    battery_swap_slots = Column(Integer, default=2)
    fast_charge_slots = Column(Integer, default=2)
    swap_time_minutes = Column(Float, default=3.0)

    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    drones = relationship("Drone", back_populates="home_depot")
    orders = relationship("Order", back_populates="origin_depot")


class Drone(Base):
    """Drone fleet model."""

    __tablename__ = "drones"

    id = Column(Integer, primary_key=True, index=True)
    drone_id = Column(String(50), unique=True, index=True, nullable=False)
    home_depot_id = Column(Integer, ForeignKey("depots.id"))

    state = Column(String(30), default="IDLE")  # IDLE, EN_ROUTE, DELIVERING, RETURNING,
                                                  # CHARGING, SWAPPING_BATTERY, EMERGENCY_LANDING, GROUNDED
    node_id = Column(Integer)
    lat = Column(Float)
    lon = Column(Float)
    altitude_band_m = Column(Float, default=60.0)

    payload_capacity_kg = Column(Float, default=5.0)
    current_payload_kg = Column(Float, default=0.0)

    battery_capacity_wh = Column(Float, default=500.0)
    battery_soc = Column(Float, default=1.0)
    battery_degradation = Column(Float, default=0.0)

    total_distance_km = Column(Float, default=0.0)
    total_deliveries = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    home_depot = relationship("Depot", back_populates="drones")
    deliveries = relationship("Delivery", back_populates="drone")


class Order(Base):
    """Delivery order model."""

    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String(50), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))
    origin_depot_id = Column(Integer, ForeignKey("depots.id"))

    city = Column(String(50), default="pune")  # which city's fleet this order belongs to
    destination_node_id = Column(Integer)
    destination_lat = Column(Float)
    destination_lon = Column(Float)

    payload_kg = Column(Float, nullable=False)
    priority = Column(String(20), default="STANDARD")   # STANDARD, EXPRESS, MEDICAL
    deadline_minutes = Column(Float, default=30.0)

    status = Column(String(30), default="PENDING")  # PENDING, ASSIGNED, EN_ROUTE, DELIVERED, FAILED

    # Deterministic dispatch decision — set synchronously by the CBF gate,
    # never by the council (see aerofleet/api/routes/orders.py's
    # dispatch_order; the council is never on this critical path).
    council_verdict = Column(Text)
    cbf_certificate = Column(JSON)
    # The exact plan dict the gate evaluated — persisted so a later async
    # explanation request explains the real decision, not a re-derived
    # approximation of it (fleet state may have moved on by then).
    dispatch_plan = Column(JSON)

    # Async, optional, non-blocking: a natural-language explanation of the
    # decision above, generated after the fact by aerofleet.agents.council
    # via aerofleet/agents/explanation_worker.py. NOT_REQUESTED until a
    # client calls POST /orders/{id}/request-explanation.
    council_transcript = Column(JSON)
    council_explanation_status = Column(String(20), default="NOT_REQUESTED")
    council_explanation_requested_at = Column(DateTime, nullable=True)
    council_explanation_completed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="orders")
    origin_depot = relationship("Depot", back_populates="orders")
    delivery = relationship("Delivery", back_populates="order", uselist=False, cascade="all, delete-orphan")


class Delivery(Base):
    """A single dispatch/delivery run for an order."""

    __tablename__ = "deliveries"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    drone_id = Column(Integer, ForeignKey("drones.id"), nullable=False)

    distance_km = Column(Float)
    energy_wh_used = Column(Float)
    eta_minutes = Column(Float)

    status = Column(String(30), default="EN_ROUTE")  # EN_ROUTE, DELIVERED, FAILED, DIVERTED
    fault_events = Column(JSON)

    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

    order = relationship("Order", back_populates="delivery")
    drone = relationship("Drone", back_populates="deliveries")


class BatterySwap(Base):
    """Log of battery-swap events at a depot swap station."""

    __tablename__ = "battery_swaps"

    id = Column(Integer, primary_key=True, index=True)
    drone_id = Column(Integer, ForeignKey("drones.id"), nullable=False)
    depot_id = Column(Integer, ForeignKey("depots.id"), nullable=False)

    soc_before = Column(Float)
    soc_after = Column(Float)
    swap_duration_minutes = Column(Float)
    queue_wait_minutes = Column(Float, default=0.0)

    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)


class Geofence(Base):
    """DGCA-style airspace zone (Red/Yellow/Green) or pre-mapped safe zone."""

    __tablename__ = "geofences"

    id = Column(Integer, primary_key=True, index=True)
    zone_id = Column(String(50), unique=True, index=True, nullable=False)
    zone_type = Column(String(20))    # RED, YELLOW, GREEN, SAFE_ZONE
    name = Column(String(255))
    reason = Column(Text)

    center_lat = Column(Float)
    center_lon = Column(Float)
    radius_m = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)


class AgentInteraction(Base):
    """Log of agent interactions and council debates."""

    __tablename__ = "agent_interactions"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))

    agent_id = Column(String(50), index=True)  # ROUTE, BATTERY, AIRSPACE_SAFETY, etc.
    agent_role = Column(String(100))

    prompt = Column(Text)
    response = Column(Text)
    tool_used = Column(String(100))
    tool_result = Column(JSON)

    interaction_type = Column(String(50))  # COUNCIL_DEBATE, CONTINGENCY_RESPONSE, DISPATCH_PLANNING
    execution_time_ms = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)


class PolicyProposal(Base):
    """A council-drafted proposal to adjust CBF safety-threshold defaults
    for a city, generated on a slow cadence by
    aerofleet/agents/policy_review_worker.py — never auto-applied. Only an
    operator's explicit approve/reject (aerofleet/api/routes/policy.py)
    changes what aerofleet/safety/policy_store.py's get_active_policy()
    returns, which build_cbf_gate() consults as an overlay on its hardcoded
    defaults. Approving a proposal never touches the gate's constraint
    definitions themselves — only the numeric thresholds they're checked
    against."""

    __tablename__ = "policy_proposals"

    id = Column(Integer, primary_key=True, index=True)
    proposal_id = Column(String(50), unique=True, index=True, nullable=False)
    city = Column(String(50), index=True, nullable=False)

    # Threshold overrides proposed, e.g. {"min_separation_m": 18.0}. Keys
    # must be a subset of build_cbf_gate()'s known config keys — validated
    # at approval time, not here, so a malformed proposal can still be
    # reviewed and rejected rather than failing to save.
    proposed_changes = Column(JSON, nullable=False)
    rationale = Column(Text)
    stats_snapshot = Column(JSON)  # the fleet/dispatch/fault stats the council was shown

    status = Column(String(20), default="PENDING_REVIEW")  # PENDING_REVIEW, APPROVED, REJECTED
    reviewed_by = Column(String(50), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class IncidentReport(Base):
    """A multi-agent forensic investigation of a fleet anomaly — the
    Fleet Incident Forensics Council's output. See
    aerofleet/agents/incident_taxonomy.py for the structured taxonomy
    (Tier 1 immediate trigger, Tier 2 contributing domain factors, Tier 3
    systemic/policy factors, Tier 4 regulatory) and
    aerofleet/agents/incident_forensics_worker.py for the worker that
    produces this. Unlike PolicyProposal (human-triggered review of
    aggregate fleet stats on a slow cadence), an IncidentReport is
    auto-triggered by a single real anomaly — a CBF rejection, a fault
    event, an emergency landing — and investigates that ONE incident using
    the frozen state at the time it happened, never re-derived state."""

    __tablename__ = "incident_reports"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(String(50), unique=True, index=True, nullable=False)
    city = Column(String(50), index=True, nullable=False)
    order_id = Column(String(50), ForeignKey("orders.order_id"), nullable=True, index=True)

    # Tier 1 — taken directly from the deterministic system's own record,
    # never LLM-derived (see incident_taxonomy.py's IncidentTrigger).
    trigger_type = Column(String(30), nullable=False)  # CBF_REJECTION | FAULT_EVENT | EMERGENCY_LANDING
    trigger_detail = Column(JSON, nullable=False)

    # The actual, real state at the moment of the incident (CBF certificate,
    # dispatch plan, telemetry snapshot) — every agent investigates against
    # THIS, not a re-derived approximation, same principle as
    # explanation_worker.py's precomputed_cbf_certificate.
    frozen_context = Column(JSON, nullable=False)

    status = Column(String(20), default="PENDING")  # PENDING, INVESTIGATING, READY, FAILED

    # Tier 2 — one entry per domain agent: {"factor", "contributed",
    # "confidence", "evidence"}.
    contributing_factors = Column(JSON, nullable=True)
    # Tier 3/4 synthesis, from the Dispatcher + Compliance agents.
    root_cause_summary = Column(Text, nullable=True)
    systemic_factor_note = Column(Text, nullable=True)
    recommended_action = Column(Text, nullable=True)
    recommended_policy_change = Column(JSON, nullable=True)
    regulatory_reportable = Column(Boolean, nullable=True)
    regulatory_citation = Column(Text, nullable=True)

    # Full agent-by-agent transcript, same shape as Order.council_transcript.
    investigation_transcript = Column(JSON, nullable=True)

    # Set once an operator turns recommended_policy_change into a real
    # PolicyProposal via POST /incidents/{id}/promote-to-policy-proposal —
    # never auto-applied, same human-gate as every other safety-threshold
    # change in this project.
    promoted_policy_proposal_id = Column(String(50), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class RouteCalculation(Base):
    """Cache of route/ETA calculations over the city graph."""

    __tablename__ = "route_calculations"

    id = Column(Integer, primary_key=True, index=True)

    origin_node_id = Column(Integer, index=True)
    destination_node_id = Column(Integer, index=True)

    distance_km = Column(Float)
    eta_minutes = Column(Float)
    energy_wh_required = Column(Float)
    path_node_ids = Column(JSON)

    calculation_method = Column(String(50))   # OSMNX, SYNTHETIC_GRID
    calculation_status = Column(String(50))   # SUCCESS, FAILED, APPROXIMATE

    created_at = Column(DateTime, default=datetime.utcnow)
