"""Process-wide in-memory fleet simulation state — one per city.

Drones and depots live here as fast in-memory objects (fleet/models.py)
during a simulation run; the SQLAlchemy models (data/models/models.py)
are the durable record of orders/users/history. Keeping live simulation
state out of the database avoids a DB round-trip on every tick of the
dispatch loop.
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional

from aerofleet.city.airspace import AirspaceModel, build_airspace_from_sites, build_default_airspace
from aerofleet.city.graph import CityGraph
from aerofleet.city.registry import DEFAULT_CITY, get_city_config
from aerofleet.fleet.digital_twin import FleetDigitalTwin
from aerofleet.fleet.dispatch import DispatchEngine
from aerofleet.fleet.models import Battery, DeliveryOrder, Depot, Drone


class FleetState:
    def __init__(self, city: str = DEFAULT_CITY, radius_m: float = 4000.0):
        self.city = city
        cfg = get_city_config(city)
        self.city_config = cfg
        self.graph = CityGraph(city_name=cfg.osm_name, radius_m=radius_m)
        if cfg.restricted_sites:
            self.airspace: AirspaceModel = build_airspace_from_sites(
                cfg.restricted_sites, safe_zones=cfg.safe_zones
            )
        else:
            self.airspace = build_default_airspace(
                city_center=cfg.center, airport=cfg.airport, airport_name=cfg.airport_name
            )
        self.dispatch_engine = DispatchEngine(self.graph, self.airspace)
        self.twin = FleetDigitalTwin(fleet_id=city)
        self.drones: Dict[str, Drone] = {}
        self.depots: Dict[str, Depot] = {}
        self.orders: Dict[str, DeliveryOrder] = {}

    def seed_demo_fleet(self, n_depots: int = 6, drones_per_depot: int = 3) -> "FleetState":
        rng = random.Random(42)
        self.graph.load()
        for i in range(n_depots):
            node = self.graph.random_node(rng)
            depot_id = f"DEPOT-{i + 1}"
            self.depots[depot_id] = Depot(depot_id=depot_id, name=f"Micro-Depot {i + 1}", node=node)
            for j in range(drones_per_depot):
                drone_id = f"{depot_id}-D{j + 1}"
                self.drones[drone_id] = Drone(
                    drone_id=drone_id, node=node, battery=Battery(), home_depot_id=depot_id,
                )
        return self

    def list_drones(self) -> List[Drone]:
        return list(self.drones.values())

    def list_depots(self) -> List[Depot]:
        return list(self.depots.values())

    def get_drone(self, drone_id: str) -> Optional[Drone]:
        return self.drones.get(drone_id)

    def get_depot(self, depot_id: str) -> Optional[Depot]:
        return self.depots.get(depot_id)


_fleet_states: Dict[str, FleetState] = {}


def get_fleet_state(city: str = DEFAULT_CITY, reload: bool = False) -> FleetState:
    """Process-wide cached FleetState per city, lazily seeded on first request."""
    city = (city or DEFAULT_CITY).lower()
    if city not in _fleet_states or reload:
        _fleet_states[city] = FleetState(city=city).seed_demo_fleet()
    return _fleet_states[city]


def list_active_cities() -> List[str]:
    """Cities that have actually been loaded (not just registered)."""
    return list(_fleet_states.keys())
