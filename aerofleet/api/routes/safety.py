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

import math
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Query

from aerofleet.api.routes.auth import get_current_active_user
from aerofleet.api.schemas import VerifyRouteRequest
from aerofleet.city.registry import DEFAULT_CITY
from aerofleet.data.models.models import User
from aerofleet.fleet.state import get_fleet_state
from aerofleet.safety.cbf_gate import build_cbf_gate, build_trajectory_points_from_plan

router = APIRouter()

# Drone pairs closer than this (horizontally) are returned for the VR
# swarm view's separation lines — wide enough to show a pair approaching
# the 15 m CBF minimum well before it's breached.
PAIR_AWARENESS_RADIUS_M = 250.0
MAX_PAIRS = 80

# Which of the 11 CBF constraints live-margins evaluates from real, live
# per-drone state vs. a conservative dispatch-time default (no per-drone
# telemetry source exists yet for the latter). Surfaced so a display can
# say which numbers are actually measured.
LIVE_CONSTRAINTS = [
    "min_separation", "geofence_exclusion", "battery_reserve_margin", "altitude_ceiling", "payload_weight_limit",
]
DEFAULT_CONSTRAINTS = [
    "wind_limit", "noise_limit", "collision_probability", "comms_link_margin", "depot_capacity", "weather_visibility",
]


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
    import time

    from aerofleet.api.routes.fleet import _drone_lat_lon
    from aerofleet.city.airspace import DGCA_LEGAL_CEILING_M
    from aerofleet.fleet import flight_progress
    from aerofleet.fleet.models import DroneState

    # Only actively-flying drones — min_separation is an airborne-conflict
    # constraint, and drones idle/charging at the same depot pad are
    # legitimately closer than 15m without that meaning anything unsafe.
    IN_FLIGHT_STATES = {DroneState.EN_ROUTE, DroneState.DELIVERING, DroneState.RETURNING, DroneState.EMERGENCY_LANDING}

    fleet = get_fleet_state(city)
    now = time.time()
    min_sep_m = build_cbf_gate({}, city=city).config["min_separation_m"]

    positioned = []
    for drone in fleet.list_drones():
        if drone.state not in IN_FLIGHT_STATES:
            continue
        flight = flight_progress.get(city, drone.drone_id) if drone.link_mode != "LIVE" else None
        if flight is not None and flight.order_id == drone.order_id:
            fs = flight.state_at(now)
            lat, lon, altitude_m = fs.lat, fs.lon, flight.altitude_m
        else:
            fs = None
            lat, lon = _drone_lat_lon(fleet, drone)
            altitude_m = drone.altitude_band_m
        if lat is not None and lon is not None:
            positioned.append((drone, lat, lon, altitude_m, fs))

    # Pairwise geometry. min_separation (the CBF constraint) is horizontal
    # only — that's what the gate checks, so that's what colors a pair.
    # Vertical offset is reported alongside so a viewer can see when two
    # drones are horizontally close but stacked in different altitude bands.
    pairs: List[Dict[str, Any]] = []
    nearest: Dict[str, Tuple[Optional[str], float, float]] = {}
    for i, (a, alat, alon, aalt, _) in enumerate(positioned):
        for b, blat, blon, balt, _ in positioned[i + 1:]:
            horiz = flight_progress.haversine_m((alat, alon), (blat, blon))
            vert = abs(aalt - balt)
            for me, other in ((a.drone_id, b.drone_id), (b.drone_id, a.drone_id)):
                if me not in nearest or horiz < nearest[me][1]:
                    nearest[me] = (other, horiz, vert)
            if horiz <= PAIR_AWARENESS_RADIUS_M:
                pairs.append({
                    "a": a.drone_id, "b": b.drone_id,
                    "horizontal_m": round(horiz, 1),
                    "vertical_m": round(vert, 1),
                    "slant_m": round(math.hypot(horiz, vert), 1),
                    "separation_margin_m": round(horiz - min_sep_m, 1),
                })
    pairs.sort(key=lambda p: p["horizontal_m"])
    pairs = pairs[:MAX_PAIRS]

    per_drone: Dict[str, Any] = {}
    worst_case: Dict[str, float] = {}

    for drone, lat, lon, altitude_m, fs in positioned:
        nearest_id, nearest_sep_m, nearest_vert_m = nearest.get(drone.drone_id, (None, 999.0, 0.0))
        ceiling_m = fleet.airspace.altitude_ceiling_m_at(lat, lon)
        gate = build_cbf_gate({"max_altitude_m": ceiling_m}, city=city)

        point = {
            "separation_m": nearest_sep_m,
            "in_red_zone": fleet.airspace.is_no_fly(lat, lon),
            "battery_margin_wh": drone.battery.available_wh,
            "altitude_m": altitude_m,
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
        battery = drone.battery
        route = [[p[0], p[1]] for p in flight_progress.downsample(fs.remaining_path, 32)] if fs else []
        per_drone[drone.drone_id] = {
            "lat": lat,
            "lon": lon,
            "link_mode": drone.link_mode,
            "safety_margins": result.safety_margin_summary,
            "passed": result.passed,
            "state": drone.state.value,
            "order_id": drone.order_id,
            "altitude_m": altitude_m,
            "altitude_ceiling_m": ceiling_m,
            "zone": fleet.airspace.zone_at(lat, lon).value,
            "battery_soc_pct": round(battery.soc * 100.0, 1),
            "battery_available_wh": round(battery.available_wh, 1),
            "battery_reserve_wh": round(battery.reserve_wh, 1),
            "payload_kg": drone.current_payload_kg,
            "nearest_drone_id": nearest_id,
            "nearest_horizontal_m": round(nearest_sep_m, 1),
            "nearest_vertical_m": round(nearest_vert_m, 1),
            "heading_deg": round(fs.heading_deg, 1) if fs else None,
            "progress": round(fs.progress, 3) if fs else None,
            "remaining_m": round(fs.remaining_m, 1) if fs else None,
            "arrived": fs.arrived if fs else False,
            "route": route,
            "position_source": "TELEMETRY" if drone.link_mode == "LIVE" else ("ROUTE_DEAD_RECKONING" if fs else "DEPOT_NODE"),
        }
        for name, margin in result.safety_margin_summary.items():
            if name not in worst_case or margin < worst_case[name]:
                worst_case[name] = margin

    return {
        "city": city,
        "generated_at": now,
        "drone_count": len(per_drone),
        "drones": per_drone,
        "pairs": pairs,
        "fleet_worst_case": worst_case,
        "constants": {
            "min_separation_m": min_sep_m,
            "operational_ceiling_m": fleet.airspace.operational_ceiling_m,
            "legal_ceiling_m": DGCA_LEGAL_CEILING_M,
            "pair_awareness_radius_m": PAIR_AWARENESS_RADIUS_M,
            "cruise_speed_mps": flight_progress.CRUISE_SPEED_MPS,
        },
        "constraint_sources": {"live": LIVE_CONSTRAINTS, "default": DEFAULT_CONSTRAINTS},
    }
