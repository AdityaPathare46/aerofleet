"""
CBF/ASIF Safety Gate — REST endpoints.

POST /api/v1/safety/verify
  Standalone route verification against 11 CBF constraints.

GET /api/v1/safety/live-margins
  Continuous re-evaluation against the fleet's *current* live state —
  powers the VR safety view (tauri-app/src/pages/VRSafetyView.tsx). This
  is a supervisory display, not part of the actual safety-authority
  chain: it reuses the same CBF gate dispatch_order already runs, but
  read-only and after the fact — nothing here can approve or block a
  dispatch.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, Query

from aerofleet.api.routes.auth import get_current_active_user
from aerofleet.api.schemas import VerifyRouteRequest
from aerofleet.city.registry import DEFAULT_CITY
from aerofleet.data.models.models import User
from aerofleet.fleet.state import get_fleet_state
from aerofleet.safety.cbf_gate import build_cbf_gate, build_trajectory_points_from_plan

router = APIRouter()


@router.post("/verify")
async def verify_route(
    body: VerifyRouteRequest, current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Verify a proposed route against all 11 Control Barrier Function constraints.

    Returns::
        {
          "passed": true/false,
          "violations": [...],
          "safety_margins": { "min_separation": 35.0, ... },
          "execution_time_ms": 0.87,
          "formally_verified": true/false
        }
    """
    dispatch_plan = body.dispatch_plan
    route_points = (
        [p.model_dump() for p in body.route_points]
        if body.route_points
        else build_trajectory_points_from_plan(dispatch_plan)
    )

    gate = build_cbf_gate(dispatch_plan)
    result = gate.evaluate_trajectory(route_points)

    return {
        "passed": result.passed,
        "violations": [
            {
                "constraint": v.constraint_name,
                "constraint_index": v.constraint_index,
                "magnitude": v.violation_magnitude,
                "time_index": v.trajectory_time_index,
                "required_correction": v.required_correction,
            }
            for v in result.violations
        ],
        "safety_margins": result.safety_margin_summary,
        "execution_time_ms": result.execution_time_ms,
        "formally_verified": result.passed,
        "constraint_count": len(gate.constraints),
    }


@router.get("/constraints")
async def list_constraints() -> Dict[str, Any]:
    """
    List all CBF constraint definitions.
    Useful for dispatch operators to understand what is checked.
    """
    gate = build_cbf_gate({})
    return {
        "constraints": [
            {"index": i, "name": c["name"], "description": c["description"]}
            for i, c in enumerate(gate.constraints)
        ],
        "total": len(gate.constraints),
        "method": "ASIF / Active Set Invariance Filter",
    }


@router.get("/live-margins")
async def live_margins(
    city: str = Query(DEFAULT_CITY), current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    CBF safety margins for every currently-active drone, evaluated against
    live fleet state rather than a one-shot dispatch plan. Genuinely live
    where the fleet actually tracks it (real inter-drone separation via
    haversine, real geofence check, real battery/altitude/payload); the
    handful of constraints with no live per-drone telemetry today (wind,
    noise, comms link, visibility, depot queue, collision probability)
    fall back to the same conservative defaults dispatch-time evaluation
    already uses, same as build_trajectory_points_from_plan.
    """
    from aerofleet.api.routes.fleet import _drone_lat_lon
    from aerofleet.fleet.models import DroneState

    # Only actively-flying drones — min_separation is an airborne-conflict
    # constraint, and drones idle/charging at the same depot pad are
    # legitimately closer than 15m without that meaning anything unsafe.
    IN_FLIGHT_STATES = {DroneState.EN_ROUTE, DroneState.DELIVERING, DroneState.RETURNING, DroneState.EMERGENCY_LANDING}

    fleet = get_fleet_state(city)
    gate = build_cbf_gate({})

    positioned = []
    for drone in fleet.list_drones():
        if drone.state not in IN_FLIGHT_STATES:
            continue
        lat, lon = _drone_lat_lon(fleet, drone)
        if lat is not None and lon is not None:
            positioned.append((drone, lat, lon))

    per_drone: Dict[str, Any] = {}
    worst_case: Dict[str, float] = {}

    for drone, lat, lon in positioned:
        nearest_sep_m = min(
            (
                fleet.airspace._haversine_m(lat, lon, other_lat, other_lon)
                for other_drone, other_lat, other_lon in positioned
                if other_drone.drone_id != drone.drone_id
            ),
            default=999.0,
        )

        point = {
            "separation_m": nearest_sep_m,
            "in_red_zone": fleet.airspace.is_no_fly(lat, lon),
            "battery_margin_wh": drone.battery.available_wh,
            "altitude_m": drone.altitude_band_m,
            "payload_kg": drone.current_payload_kg,
            # Not yet tracked as live per-drone telemetry — same
            # conservative defaults dispatch-time evaluation uses.
            "wind_speed_mps": 3.0,
            "noise_db": 55.0,
            "collision_probability": 0.0,
            "link_margin_db": 10.0,
            "depot_queue_length": 0,
            "visibility_m": 8000.0,
        }
        result = gate.evaluate_trajectory([point])
        per_drone[drone.drone_id] = {
            "lat": lat,
            "lon": lon,
            "link_mode": drone.link_mode,
            "safety_margins": result.safety_margin_summary,
            "passed": result.passed,
        }
        for name, margin in result.safety_margin_summary.items():
            if name not in worst_case or margin < worst_case[name]:
                worst_case[name] = margin

    return {
        "city": city,
        "drone_count": len(per_drone),
        "drones": per_drone,
        "fleet_worst_case": worst_case,
    }
