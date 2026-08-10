"""Airspace geofence API endpoints — DGCA Red/Yellow/Green zones + safe zones, per city."""

from typing import List

from fastapi import APIRouter, Query

from aerofleet.api.schemas import GeofenceResponse
from aerofleet.city.registry import DEFAULT_CITY
from aerofleet.fleet.state import get_fleet_state

router = APIRouter()


@router.get("/zones", response_model=List[GeofenceResponse])
async def list_zones(city: str = Query(DEFAULT_CITY)):
    fleet = get_fleet_state(city)
    return [
        GeofenceResponse(
            zone_id=z.zone_id, zone_type=z.color.value, name=None,
            reason=z.reason, center_lat=z.center_lat, center_lon=z.center_lon,
            radius_m=z.radius_m,
        )
        for z in fleet.airspace.zones
    ]


@router.get("/safe-zones")
async def list_safe_zones(city: str = Query(DEFAULT_CITY)):
    fleet = get_fleet_state(city)
    return [
        {"zone_id": s.zone_id, "name": s.name, "lat": s.center_lat, "lon": s.center_lon}
        for s in fleet.airspace.safe_zones
    ]


@router.get("/altitude-bands")
async def list_altitude_bands(city: str = Query(DEFAULT_CITY)):
    fleet = get_fleet_state(city)
    return [
        {"name": b.name, "floor_m": b.floor_m, "ceiling_m": b.ceiling_m}
        for b in fleet.airspace.altitude_bands
    ]


@router.get("/check")
async def check_point(lat: float, lon: float, city: str = Query(DEFAULT_CITY)):
    fleet = get_fleet_state(city)
    zone = fleet.airspace.zone_at(lat, lon)
    return {"lat": lat, "lon": lon, "zone_colour": zone.value, "is_no_fly": zone.value == "RED"}
