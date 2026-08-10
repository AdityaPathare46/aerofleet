"""Pydantic schemas for API request/response validation."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserResponse(UserBase):
    id: int
    is_active: bool
    is_operator: bool
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserPermissionsUpdate(BaseModel):
    """Admin-only patch to another user's flags — every field optional so a
    caller only sends what it actually wants to change."""
    is_operator: Optional[bool] = None
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None


# ─────────────────────────────────────────────────────────────────────────
#  ORDERS / DISPATCH
# ─────────────────────────────────────────────────────────────────────────

class OrderBase(BaseModel):
    """Base delivery-order schema."""
    city: Optional[str] = "pune"               # which city's fleet this order dispatches from
    origin_depot_id: str = Field(..., description="Origin micro-depot id")
    destination_lat: float
    destination_lon: float
    payload_kg: float = Field(..., gt=0)
    priority: Optional[str] = "STANDARD"       # STANDARD, EXPRESS, MEDICAL
    deadline_minutes: Optional[float] = 30.0


class OrderCreate(OrderBase):
    """Schema for creating a new delivery order."""
    pass


class OrderUpdate(BaseModel):
    """Schema for updating an order."""
    status: Optional[str] = None
    council_verdict: Optional[str] = None
    council_transcript: Optional[List[Dict[str, Any]]] = None
    cbf_certificate: Optional[Dict[str, Any]] = None


class OrderResponse(OrderBase):
    """Schema for order response."""
    id: int
    order_id: str
    status: str
    council_verdict: Optional[str] = None
    cbf_certificate: Optional[Dict[str, Any]] = None

    # Async, optional — see aerofleet/agents/explanation_worker.py. The
    # decision above is always already final by the time this is anything
    # other than NOT_REQUESTED/PENDING; this never gates or delays it.
    council_explanation_status: str = "NOT_REQUESTED"
    council_transcript: Optional[List[Dict[str, Any]]] = None
    council_explanation_requested_at: Optional[datetime] = None
    council_explanation_completed_at: Optional[datetime] = None

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────────────
#  FLEET POLICY PROPOSALS
# ─────────────────────────────────────────────────────────────────────────

class PolicyProposalResponse(BaseModel):
    """A council-drafted, human-reviewable proposal to adjust CBF threshold
    defaults for a city. See aerofleet/safety/policy_store.py — approving
    one never touches the CBF gate's constraint definitions, only the
    numeric thresholds they're checked against."""
    id: int
    proposal_id: str
    city: str
    proposed_changes: Dict[str, float]
    rationale: Optional[str] = None
    stats_snapshot: Optional[Dict[str, Any]] = None
    status: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PolicyReviewDecision(BaseModel):
    """Optional free-text note an operator can attach when approving or
    rejecting a proposal — surfaced back in the response, not stored
    beyond it (no dedicated column; keeps the model additive/minimal)."""
    note: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────
#  FLEET INCIDENT FORENSICS
# ─────────────────────────────────────────────────────────────────────────

class IncidentReportResponse(BaseModel):
    """A multi-agent forensic investigation of one real fleet anomaly. See
    aerofleet/agents/incident_taxonomy.py for the tiered taxonomy this
    follows. Auto-triggered — never something a user requests, unlike
    Order.council_transcript's on-demand explanation."""
    id: int
    incident_id: str
    city: str
    order_id: Optional[str] = None
    trigger_type: str
    trigger_detail: Dict[str, Any]
    frozen_context: Dict[str, Any]
    status: str
    contributing_factors: Optional[List[Dict[str, Any]]] = None
    root_cause_summary: Optional[str] = None
    systemic_factor_note: Optional[str] = None
    recommended_action: Optional[str] = None
    recommended_policy_change: Optional[Dict[str, float]] = None
    regulatory_reportable: Optional[bool] = None
    regulatory_citation: Optional[str] = None
    investigation_transcript: Optional[List[Dict[str, Any]]] = None
    promoted_policy_proposal_id: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────────────
#  ROUTING
# ─────────────────────────────────────────────────────────────────────────

class RouteRequest(BaseModel):
    """Schema for a route/ETA calculation request."""
    origin_lat: float
    origin_lon: float
    destination_lat: float
    destination_lon: float
    payload_kg: float = Field(default=1.0, ge=0)


class RouteResponse(BaseModel):
    """Schema for a route/ETA calculation response."""
    origin: List[float]
    destination: List[float]
    distance_km: float
    eta_minutes: float
    energy_wh_required: float
    status: str
    calculation_method: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────
#  FLEET / DEPOTS
# ─────────────────────────────────────────────────────────────────────────

class DroneResponse(BaseModel):
    drone_id: str
    node: Optional[int] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    soc: float
    state: str
    payload_kg: float
    payload_capacity_kg: float
    altitude_band_m: float
    home_depot_id: Optional[str] = None
    order_id: Optional[str] = None
    total_distance_km: float
    link_mode: str = "SIMULATED"
    armed: bool = False
    flight_mode: str = ""
    last_telemetry_at: Optional[float] = None
    d2d_link_state: str = "NOMINAL"


class DepotResponse(BaseModel):
    depot_id: str
    name: str
    node: Optional[int] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    launch_pad_slots: int
    battery_swap_slots: int
    queued_drones: List[str] = []


class GeofenceResponse(BaseModel):
    zone_id: str
    zone_type: str
    name: Optional[str] = None
    reason: Optional[str] = None
    center_lat: float
    center_lon: float
    radius_m: float


# ─────────────────────────────────────────────────────────────────────────
#  AGENT COUNCIL
# ─────────────────────────────────────────────────────────────────────────

class AgentDebateRequest(BaseModel):
    """Schema for agent council dispatch-debate request."""
    dispatch_plan: Dict[str, Any]
    chat_history: Optional[List[Dict[str, str]]] = []


class AgentDebateResponse(BaseModel):
    """Schema for agent debate response."""
    final_plan: Dict[str, Any]
    transcript: List[Dict[str, Any]]
    verdict: str
    execution_time_ms: float


# ─────────────────────────────────────────────────────────────────────────
#  SIMULATION
# ─────────────────────────────────────────────────────────────────────────

class SimulationRequest(BaseModel):
    """Schema for a fleet simulation run request."""
    scenario_name: str
    duration_hours: float = 4.0
    time_step_seconds: float = 10.0
    enable_anomalies: bool = True


class SimulationResponse(BaseModel):
    """Schema for a fleet simulation run response."""
    id: int
    scenario_name: str
    status: str
    duration_hours: float
    anomalies_encountered: Optional[List[Dict[str, Any]]] = None
    final_state: Optional[Dict[str, Any]] = None
    started_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────────────
#  SAFETY / CBF GATE
# ─────────────────────────────────────────────────────────────────────────

class TrajectoryPoint(BaseModel):
    """One state point the CBF gate evaluates its 11 constraints against —
    mirrors aerofleet.safety.cbf_gate.build_trajectory_points_from_plan's
    field set exactly, so a caller can supply real telemetry per point
    instead of relying on the plan-level defaults."""
    separation_m: float = 50.0
    in_red_zone: bool = False
    battery_margin_wh: float = 50.0
    altitude_m: float = 60.0
    wind_speed_mps: float = 3.0
    payload_kg: float = 1.0
    noise_db: float = 55.0
    collision_probability: float = 0.0
    link_margin_db: float = 10.0
    depot_queue_length: int = 0
    visibility_m: float = 8000.0


class VerifyRouteRequest(BaseModel):
    """POST /api/v1/safety/verify body — feeds the CBF gate directly, so
    this is validated rather than accepted as a raw dict."""
    dispatch_plan: Dict[str, Any] = Field(default_factory=dict)
    route_points: Optional[List[TrajectoryPoint]] = None
