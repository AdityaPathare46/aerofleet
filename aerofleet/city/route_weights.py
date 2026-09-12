"""Zone- and energy-aware route weighting — a real alternative to plain
distance-shortest routing (CityGraph.shortest_path's default `weight="length"`)
when payload weight or real DGCA restricted zones should influence which
path a drone actually takes, not just how far it travels.

This is deliberately a separate module from graph.py rather than a change
to shortest_path itself: other callers may still want plain-distance
routing (it's cheaper, and "shortest by distance" is a perfectly valid
answer when nothing else matters), so the existing method stays untouched
and this is additive.
"""
from __future__ import annotations

from typing import Callable, List

import networkx as nx

from aerofleet.city.airspace import AirspaceModel, ZoneColor
from aerofleet.city.graph import CityGraph
from aerofleet.fleet.dispatch import DispatchEngine

# Cost-per-Wh weight, in the same km-equivalent units as distance — tunable
# independently of the raw energy formula. Small by design: energy should
# nudge the route, not dominate it outright for short/light deliveries.
ENERGY_WEIGHT_KM_PER_WH = 0.01

# Fixed additive penalties (km-equivalent) for an edge touching a zone.
# Red is large enough that no plausible energy/distance saving would ever
# make routing through one "worth it" to the search; yellow is a real but
# much smaller nudge, since yellow zones are legally enterable with ATC
# permission, not prohibited outright (aerofleet/city/restricted_sites.py).
RED_ZONE_PENALTY_KM = 50.0
YELLOW_ZONE_PENALTY_KM = 5.0


def _zone_penalty_km(g, airspace: AirspaceModel, u: int, v: int) -> float:
    """Real zone lookup at both edge endpoints (not just a midpoint
    approximation) via the same AirspaceModel.zone_at() every other real
    zone check in this codebase already uses. max(), not sum(), across the
    two endpoints — a single edge passing through one zone shouldn't be
    penalized twice just because both its ends happen to register."""
    penalty = 0.0
    for node in (u, v):
        data = g.nodes[node]
        zone = airspace.zone_at(float(data["y"]), float(data["x"]))
        if zone == ZoneColor.RED:
            penalty = max(penalty, RED_ZONE_PENALTY_KM)
        elif zone == ZoneColor.YELLOW:
            penalty = max(penalty, YELLOW_ZONE_PENALTY_KM)
    return penalty


def make_zone_energy_weight(g, airspace: AirspaceModel, payload_kg: float) -> Callable:
    """Returns a networkx-compatible weight callable — weight(u, v, data) —
    closed over the graph/airspace/payload for this one routing call.
    Combines real distance, real payload-weighted energy cost
    (DispatchEngine.estimate_energy_wh, not reimplemented here), and a real
    DGCA-zone penalty (restricted_sites.py via AirspaceModel.zone_at)."""

    def _weight(u, v, data) -> float:
        edge = CityGraph.edge_attrs(data)
        length_km = edge.get("length", 0.0) / 1000.0
        energy_wh = DispatchEngine.estimate_energy_wh(length_km, payload_kg)
        return length_km + ENERGY_WEIGHT_KM_PER_WH * energy_wh + _zone_penalty_km(g, airspace, u, v)

    return _weight


def optimized_shortest_path(g, airspace: AirspaceModel, orig_node: int, dest_node: int, payload_kg: float) -> List[int]:
    """A genuinely different path than CityGraph.shortest_path's plain
    distance-shortest result when payload or restricted zones matter —
    not the same path decomposed into checkpoints. Plain networkx Dijkstra
    (not A*): simpler and safe to ship first; A* with a straight-line-km
    heuristic is a valid, admissible future speed optimization here (every
    additive term above is >= 0, so straight-line distance never
    overestimates true weighted cost) but isn't needed at city-graph scale
    yet, so not added until it's actually a measured bottleneck."""
    weight_fn = make_zone_energy_weight(g, airspace, payload_kg)
    return nx.shortest_path(g, orig_node, dest_node, weight=weight_fn)
