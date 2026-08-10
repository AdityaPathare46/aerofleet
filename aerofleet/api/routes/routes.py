"""Route / ETA calculation API endpoints."""

from fastapi import APIRouter, HTTPException, Query

from aerofleet.api.schemas import RouteRequest, RouteResponse
from aerofleet.city.registry import DEFAULT_CITY
from aerofleet.fleet.state import get_fleet_state
from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/calculate", response_model=RouteResponse)
async def calculate_route(request: RouteRequest, city: str = Query(DEFAULT_CITY)):
    """Calculate distance, ETA and energy requirement between two points
    over the live city street graph."""
    fleet = get_fleet_state(city)
    try:
        origin_node = fleet.graph.nearest_node(request.origin_lat, request.origin_lon)
        dest_node = fleet.graph.nearest_node(request.destination_lat, request.destination_lon)
        distance_km = fleet.graph.route_distance_km(origin_node, dest_node)
        energy_wh = fleet.dispatch_engine.estimate_energy_wh(distance_km, request.payload_kg)
        eta_minutes = (distance_km / fleet.dispatch_engine.AVG_SPEED_KMH) * 60.0

        return RouteResponse(
            origin=[request.origin_lat, request.origin_lon],
            destination=[request.destination_lat, request.destination_lon],
            distance_km=round(distance_km, 3),
            eta_minutes=round(eta_minutes, 1),
            energy_wh_required=round(energy_wh, 1),
            status="SUCCESS",
            calculation_method="SYNTHETIC_GRID" if fleet.graph.is_synthetic else "OSMNX",
        )
    except Exception as e:
        logger.error(f"Route calculation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Route calculation failed: {e}")


@router.get("/city-info")
async def city_info(city: str = Query(DEFAULT_CITY)):
    """Return basic info about the currently loaded city graph."""
    fleet = get_fleet_state(city)
    fleet.graph.load()
    return {
        "city_name": fleet.graph.city_name,
        "is_synthetic": fleet.graph.is_synthetic,
        "node_count": fleet.graph.node_count(),
    }
