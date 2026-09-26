"""Dispatch engine — deterministic candidate assignment.

Generates ranked drone-to-order assignment candidates from hard physical
facts (battery margin, payload capacity, ETA). This is the "candidate
generation" half of the hybrid architecture: the agent council
(aerofleet/agents/council.py) reasons over these candidates for tradeoffs
and exceptions, and the CBF safety gate (aerofleet/safety/cbf_gate.py) has
final, non-negotiable say over whether a candidate is allowed to launch.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import networkx as nx

from aerofleet.city.airspace import AirspaceModel
from aerofleet.city.graph import CityGraph
from aerofleet.fleet.models import DeliveryOrder, Depot, Drone

logger = logging.getLogger(__name__)

# Rough energy model: base consumption per km, scaled up by carried payload.
WH_PER_KM = 3.5
PAYLOAD_ENERGY_FACTOR = 0.15  # +15% energy per kg carried


@dataclass
class DispatchCandidate:
    drone_id: str
    depot_id: str
    order_id: str
    outbound_km: float
    return_km: float
    energy_wh_required: float
    battery_margin_wh: float
    eta_minutes: float
    score: float


class DispatchEngine:
    AVG_SPEED_KMH = 40.0

    def __init__(self, graph: CityGraph, airspace: AirspaceModel):
        self.graph = graph
        self.airspace = airspace

    @staticmethod
    def estimate_energy_wh(distance_km: float, payload_kg: float) -> float:
        return distance_km * WH_PER_KM * (1.0 + PAYLOAD_ENERGY_FACTOR * payload_kg)

    def generate_candidates(
        self,
        order: DeliveryOrder,
        drones: List[Drone],
        depots: Dict[str, Depot],
        top_k: int = 3,
    ) -> List[DispatchCandidate]:
        """Rank feasible drones for an order by a blend of ETA and battery
        safety margin. Infeasible drones (payload too heavy, insufficient
        battery for the round trip) are excluded outright."""
        candidates: List[DispatchCandidate] = []

        for drone in drones:
            if not drone.is_available:
                continue
            if order.payload_kg > drone.payload_capacity_kg:
                continue

            depot = depots.get(drone.home_depot_id) if drone.home_depot_id else None
            origin_node = depot.node if depot else drone.node

            # A real OSM street graph is directed (one-way streets) and not fully
            # connected, so a destination can be unreachable from — or unable to
            # return to — a given drone's depot. That drone is infeasible for
            # this order, not a server error.
            try:
                outbound_km = self.graph.route_distance_km(drone.node, order.destination_node)
                return_km = self.graph.route_distance_km(order.destination_node, origin_node)
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue
            total_km = outbound_km + return_km

            energy_needed = self.estimate_energy_wh(total_km, order.payload_kg)
            margin = drone.battery.available_wh - energy_needed
            if margin < 0:
                continue

            eta_minutes = (outbound_km / self.AVG_SPEED_KMH) * 60.0
            # Penalize both slow ETAs and razor-thin battery margins.
            score = eta_minutes + max(0.0, 20.0 - margin / 10.0)

            candidates.append(
                DispatchCandidate(
                    drone_id=drone.drone_id,
                    depot_id=drone.home_depot_id or "",
                    order_id=order.order_id,
                    outbound_km=round(outbound_km, 3),
                    return_km=round(return_km, 3),
                    energy_wh_required=round(energy_needed, 1),
                    battery_margin_wh=round(margin, 1),
                    eta_minutes=round(eta_minutes, 1),
                    score=round(score, 2),
                )
            )

        candidates.sort(key=lambda c: c.score)
        return candidates[:top_k]

    def best_candidate(
        self, order: DeliveryOrder, drones: List[Drone], depots: Dict[str, Depot]
    ) -> Optional[DispatchCandidate]:
        candidates = self.generate_candidates(order, drones, depots, top_k=1)
        return candidates[0] if candidates else None
