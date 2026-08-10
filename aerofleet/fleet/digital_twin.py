"""Fleet Digital Twin — real-time shadow of the drone fleet's operational state.

Port of the mission digital twin pattern (aerofleet/digital_twin/mission_twin.py)
onto fleet-operations fields.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class FleetTwinState:
    battery_consumed_wh: float
    distance_km: float
    deliveries_completed: int
    near_misses_resolved: int
    council_decisions: int
    cbf_interventions: int
    fault_events: int
    depot_utilization: Dict[str, int]
    health_score: float
    last_updated: float = field(default_factory=time.time)


class FleetDigitalTwin:
    """Updated on every council decision, telemetry tick, and dispatch
    event. Provides predictive analytics ('what-if a depot goes offline')
    without touching the live simulation state."""

    def __init__(self, fleet_id: str = "default") -> None:
        self.fleet_id = fleet_id
        self._state = FleetTwinState(
            battery_consumed_wh=0.0,
            distance_km=0.0,
            deliveries_completed=0,
            near_misses_resolved=0,
            council_decisions=0,
            cbf_interventions=0,
            fault_events=0,
            depot_utilization={},
            health_score=1.0,
        )
        self._history: List[FleetTwinState] = []
        logger.info(f"FleetDigitalTwin created for fleet: {fleet_id}")

    def update(self, event: Dict[str, Any]) -> FleetTwinState:
        etype = event.get("type", "UNKNOWN")
        if etype == "DELIVERY_LEG":
            self._state.battery_consumed_wh += float(event.get("energy_wh", 0))
            self._state.distance_km += float(event.get("distance_km", 0))
        elif etype == "DELIVERY_COMPLETED":
            self._state.deliveries_completed += 1
        elif etype == "NEAR_MISS_RESOLVED":
            self._state.near_misses_resolved += 1
        elif etype == "COUNCIL_DECISION":
            self._state.council_decisions += 1
        elif etype == "CBF_INTERVENTION":
            self._state.cbf_interventions += 1
        elif etype == "FAULT":
            self._state.fault_events += 1
            self._state.health_score = max(0.0, self._state.health_score - 0.05)
        elif etype == "DEPOT_UTILIZATION":
            depot_id = event.get("depot_id")
            if depot_id:
                self._state.depot_utilization[depot_id] = int(event.get("active_drones", 0))

        self._state.last_updated = time.time()
        self._history.append(FleetTwinState(**vars(self._state)))
        if len(self._history) > 10000:
            self._history = self._history[-10000:]
        return self._state

    def get_health_trend(self, last_n: int = 100) -> List[float]:
        return [s.health_score for s in self._history[-last_n:]]

    def what_if(self, scenario: Dict[str, Any]) -> Dict[str, Any]:
        """E.g. {'depot_offline': 'DEPOT-3'} -> projected impact on fleet throughput."""
        offline_depot = scenario.get("depot_offline")
        remaining_capacity = sum(
            v for k, v in self._state.depot_utilization.items() if k != offline_depot
        )
        return {
            "scenario": scenario,
            "projected_remaining_capacity": remaining_capacity,
            "projected_health_score": self._state.health_score,
            "fleet_viable": remaining_capacity > 0,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fleet_id": self.fleet_id,
            "battery_consumed_wh": round(self._state.battery_consumed_wh, 1),
            "distance_km": round(self._state.distance_km, 2),
            "deliveries_completed": self._state.deliveries_completed,
            "near_misses_resolved": self._state.near_misses_resolved,
            "council_decisions": self._state.council_decisions,
            "cbf_interventions": self._state.cbf_interventions,
            "fault_events": self._state.fault_events,
            "depot_utilization": dict(self._state.depot_utilization),
            "health_score": round(self._state.health_score, 3),
        }
