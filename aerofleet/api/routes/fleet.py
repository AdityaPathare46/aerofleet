"""Fleet state API endpoints — live drones and depots, per city."""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from aerofleet.api.schemas import DepotResponse, DroneResponse
from aerofleet.city.registry import DEFAULT_CITY
from aerofleet.fleet.state import FleetState, get_fleet_state
from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


def _node_lat_lon(fleet: FleetState, node: Optional[int]):
    if node is None:
        return None, None
    try:
        lat, lon = fleet.graph.node_lat_lon(node)
        return lat, lon
    except Exception:
        return None, None


def _drone_lat_lon(fleet: FleetState, drone):
    """LIVE drones report their own real position via MAVLink telemetry;
    SIMULATED drones only have a graph-node position — fall back to that."""
    if drone.link_mode == "LIVE" and drone.lat is not None and drone.lon is not None:
        return drone.lat, drone.lon
    return _node_lat_lon(fleet, drone.node)


@router.get("/drones", response_model=List[DroneResponse])
async def list_drones(city: str = Query(DEFAULT_CITY)):
    fleet = get_fleet_state(city)
    out = []
    for d in fleet.list_drones():
        data = d.to_dict()
        data["lat"], data["lon"] = _drone_lat_lon(fleet, d)
        out.append(DroneResponse(**data))
    return out


@router.get("/drones/{drone_id}", response_model=DroneResponse)
async def get_drone(drone_id: str, city: str = Query(DEFAULT_CITY)):
    fleet = get_fleet_state(city)
    drone = fleet.get_drone(drone_id)
    if not drone:
        raise HTTPException(status_code=404, detail=f"Drone '{drone_id}' not found")
    data = drone.to_dict()
    data["lat"], data["lon"] = _drone_lat_lon(fleet, drone)
    return DroneResponse(**data)


@router.get("/depots", response_model=List[DepotResponse])
async def list_depots(city: str = Query(DEFAULT_CITY)):
    fleet = get_fleet_state(city)
    out = []
    for d in fleet.list_depots():
        data = d.to_dict()
        data["lat"], data["lon"] = _node_lat_lon(fleet, d.node)
        out.append(DepotResponse(**data))
    return out


@router.get("/depots/{depot_id}", response_model=DepotResponse)
async def get_depot(depot_id: str, city: str = Query(DEFAULT_CITY)):
    fleet = get_fleet_state(city)
    depot = fleet.get_depot(depot_id)
    if not depot:
        raise HTTPException(status_code=404, detail=f"Depot '{depot_id}' not found")
    data = depot.to_dict()
    data["lat"], data["lon"] = _node_lat_lon(fleet, depot.node)
    return DepotResponse(**data)


@router.get("/twin")
async def get_digital_twin(city: str = Query(DEFAULT_CITY)):
    """Live fleet digital twin snapshot."""
    fleet = get_fleet_state(city)
    return fleet.twin.to_dict()


@router.post("/twin/what-if")
async def what_if(scenario: dict, city: str = Query(DEFAULT_CITY)):
    fleet = get_fleet_state(city)
    return fleet.twin.what_if(scenario)
