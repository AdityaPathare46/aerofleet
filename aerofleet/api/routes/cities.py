"""City registry API endpoint — powers the frontend city selector."""

from typing import List

from fastapi import APIRouter

from aerofleet.city.registry import CITY_REGISTRY

router = APIRouter()


@router.get("/")
async def list_cities() -> List[dict]:
    return [
        {
            "slug": cfg.slug,
            "name": cfg.name,
            "center": list(cfg.center),
            "airport_name": cfg.airport_name,
            "bounds_radius_km": cfg.bounds_radius_km,
        }
        for cfg in CITY_REGISTRY.values()
    ]
