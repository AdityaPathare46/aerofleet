"""Turns a real, multi-node route (aerofleet/city/route_weights.py's
optimized_shortest_path, or any other node-ID path) into the List[Dict]
aerofleet/safety/cbf_gate.py's evaluate_trajectory() already expects — it's
been multi-waypoint-ready since it was written, just never fed more than
one point until now.

Honest scope note: only battery_margin_wh, in_red_zone, and altitude_m get
real per-waypoint fidelity here, because those are the only three of the
11 CBF-checkable fields this codebase has a real per-location source for
today (real zone data, real altitude-band rules, real energy accounting).
The other six (separation_m, wind_speed_mps, noise_db,
collision_probability, link_margin_db, depot_queue_length, visibility_m)
carry forward the same flat per-dispatch defaults
build_trajectory_points_from_plan already used — this function does not
invent new physics for those, and callers should not assume it does.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from aerofleet.city.airspace import AirspaceModel, ZoneColor
from aerofleet.city.graph import CityGraph
from aerofleet.fleet.dispatch import DispatchEngine

# Mirrors build_trajectory_points_from_plan's own defaults exactly
# (aerofleet/safety/cbf_gate.py) for the fields this function can't give
# real per-waypoint values to.
_FLAT_DEFAULTS: Dict[str, Any] = {
    "separation_m": 50.0,
    "wind_speed_mps": 3.0,
    "noise_db": 55.0,
    "collision_probability": 0.0,
    "link_margin_db": 10.0,
    "depot_queue_length": 0,
    "visibility_m": 8000.0,
}


def build_trajectory_points_from_path(
    node_path: List[int],
    graph: CityGraph,
    airspace: AirspaceModel,
    payload_kg: float,
    available_wh: float,
    priority: str = "STANDARD",
    overrides: Optional[Dict[str, Any]] = None,
) -> List[Dict]:
    """One dict per node in node_path, in order. battery_margin_wh is real
    and cumulative (starts at available_wh, subtracts real per-leg energy
    cost via DispatchEngine.estimate_energy_wh — deliberately NOT clamped
    at zero, since a genuinely negative value here is exactly what should
    make the battery_reserve_margin CBF constraint fire, not something to
    hide). in_red_zone and altitude_m are real per-waypoint zone_at()/
    assign_altitude_band() lookups — the same calls orders.py's
    dispatch_order already makes once, just looped per waypoint here."""
    overrides = overrides or {}
    defaults = {**_FLAT_DEFAULTS, **overrides}

    points: List[Dict] = []
    remaining_wh = available_wh
    for i, node in enumerate(node_path):
        lat, lon = graph.node_lat_lon(node)
        zone = airspace.zone_at(lat, lon)
        altitude_band = airspace.assign_altitude_band(priority, lat, lon)
        altitude_m = (altitude_band.floor_m + altitude_band.ceiling_m) / 2.0

        if i > 0:
            leg_km = graph.path_length_km([node_path[i - 1], node])
            remaining_wh -= DispatchEngine.estimate_energy_wh(leg_km, payload_kg)

        points.append({
            "separation_m": defaults["separation_m"],
            "in_red_zone": zone == ZoneColor.RED,
            "battery_margin_wh": round(remaining_wh, 1),
            "altitude_m": altitude_m,
            "wind_speed_mps": defaults["wind_speed_mps"],
            "payload_kg": payload_kg,
            "noise_db": defaults["noise_db"],
            "collision_probability": defaults["collision_probability"],
            "link_margin_db": defaults["link_margin_db"],
            "depot_queue_length": defaults["depot_queue_length"],
            "visibility_m": defaults["visibility_m"],
        })

    return points
