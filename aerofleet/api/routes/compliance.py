"""AeroFleet 2.0 — Pre-Flight Compliance API routes.

Provides the complete ground-based compliance check API:
  POST /api/v1/compliance/pre-flight     — full pre-flight report
  GET  /api/v1/compliance/zone           — classify a coordinate
  GET  /api/v1/compliance/dgca-checklist — document checklist by category
  GET  /api/v1/compliance/rules          — list all applicable rules

All endpoints are deterministic and synchronous. No in-flight drone control.
The LLM council may be invoked separately (async) for narrative explanation.
"""
from __future__ import annotations

import dataclasses
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from aerofleet.api.routes.auth import get_current_active_user
from aerofleet.city.airspace import AirspaceModel
from aerofleet.city.registry import CITY_REGISTRY, DEFAULT_CITY, get_city_config
from aerofleet.city.restricted_sites import PUNE_RESTRICTED_SITES, MUMBAI_RESTRICTED_SITES
from aerofleet.compliance.dgca_checklist import build_dgca_checklist
from aerofleet.compliance.pre_flight import run_pre_flight_check
from aerofleet.data.models.models import User
from aerofleet.fleet.state import get_fleet_state
from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()

_RESTRICTED_SITES_BY_CITY = {
    "pune": PUNE_RESTRICTED_SITES,
    "mumbai": MUMBAI_RESTRICTED_SITES,
}


# ── Request / Response schemas ────────────────────────────────────────────────

class MissionPlanRequest(BaseModel):
    """Mission plan parameters for pre-flight check."""
    # Location
    origin_lat: float = Field(..., description="Origin latitude")
    origin_lon: float = Field(..., description="Origin longitude")
    dest_lat: float = Field(..., description="Destination latitude")
    dest_lon: float = Field(..., description="Destination longitude")
    altitude_m: float = Field(60.0, description="Planned flight altitude (m AGL)")
    city: str = Field(DEFAULT_CITY, description="City key: pune or mumbai")

    # Drone specs
    drone_weight_kg: Optional[float] = Field(None, description="Drone airframe weight (kg)")
    payload_kg: float = Field(0.5, description="Payload weight (kg)")
    battery_soc: float = Field(0.85, description="Battery state of charge (0–1)")
    battery_capacity_wh: float = Field(500.0, description="Battery capacity (Wh)")
    drone_category: str = Field("Small", description="DGCA weight category: Nano/Micro/Small/Medium/Large")

    # Operations
    bvlos: bool = Field(False, description="Beyond Visual Line of Sight operation")
    priority: str = Field("STANDARD", description="STANDARD | EXPRESS | MEDICAL")
    deadline_minutes: float = Field(60.0, description="Delivery deadline (minutes)")

    # Regulatory status
    uin_registered: bool = Field(False, description="UIN registered on Digital Sky")
    uaop_provided: bool = Field(False, description="UAOP permit available")
    atc_permission: bool = Field(False, description="ATC/ATS permission obtained")
    rpc_provided: bool = Field(False, description="Remote Pilot Certificate held")
    insurance_provided: bool = Field(False, description="Third-party insurance in force")
    flight_plan_filed: bool = Field(False, description="NPNT flight plan filed")
    maintenance_log_current: bool = Field(False, description="Maintenance logbook current")
    safety_pilot_present: bool = Field(False, description="Safety pilot/observer assigned")

    # RF / Link security
    tx_power_w: float = Field(0.1, description="C2 transmitter power (W)")
    data_rate_mbps: float = Field(1.0, description="C2 data rate (Mbps)")
    mavlink_signing_enabled: bool = Field(False, description="MAVLink 2 message signing enabled")
    c2_encryption: str = Field("none", description="C2 encryption type: none | aes128 | aes256")
    dual_frequency_gnss: bool = Field(False, description="Dual-frequency GNSS receiver")
    gnss_anti_spoofing: bool = Field(False, description="GNSS anti-spoofing enabled")

    # Weather
    wind_speed_mps: float = Field(3.0, description="Wind speed (m/s)")
    visibility_m: float = Field(5000.0, description="Visibility (m)")
    precipitation: bool = Field(False, description="Active precipitation")


# ── Zone auto-classification helper ──────────────────────────────────────────

def _classify_point_zones(lat: float, lon: float, city: str) -> Dict[str, Any]:
    """Classify a lat/lon against known restricted sites and return zone info."""
    import math
    sites = _RESTRICTED_SITES_BY_CITY.get(city.lower(), [])
    in_red = False
    in_yellow = False
    site_matches = []

    for site in sites:
        dlat = math.radians(lat - site.lat)
        dlon = math.radians(lon - site.lon)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(site.lat)) * math.cos(math.radians(lat)) * math.sin(dlon / 2) ** 2
        dist_m = 6371000 * 2 * math.asin(math.sqrt(a))

        if dist_m <= site.red_radius_m:
            in_red = True
            site_matches.append({
                "site": site.name,
                "zone": "RED",
                "dist_m": round(dist_m),
                "radius_m": site.red_radius_m,
                "source": site.source_note,
            })
        elif site.yellow_radius_m and dist_m <= site.yellow_radius_m:
            in_yellow = True
            site_matches.append({
                "site": site.name,
                "zone": "YELLOW",
                "dist_m": round(dist_m),
                "radius_m": site.yellow_radius_m,
                "source": site.source_note,
            })

    zone_color = "RED" if in_red else ("YELLOW" if in_yellow else "GREEN")
    altitude_ceiling = 60.0 if in_yellow else 100.0
    required_permissions = []
    if in_red:
        required_permissions.append("Flight PROHIBITED — Rule 24 DGCA Drone Rules 2021")
    elif in_yellow:
        required_permissions.append("ATC/ATS permission required — Rule 24(2)")
        required_permissions.append("UIN registration mandatory — Rule 15(1)")

    return {
        "lat": lat,
        "lon": lon,
        "city": city,
        "zone_color": zone_color,
        "in_red_zone": in_red,
        "in_yellow_zone": in_yellow,
        "altitude_ceiling_m": altitude_ceiling,
        "applicable_sites": site_matches,
        "required_permissions": required_permissions,
        "dgca_rule": "DGCA Drone Rules 2021 — Rule 24 (airspace classification)",
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/pre-flight", summary="Full pre-flight compliance check")
async def pre_flight_compliance(
    body: MissionPlanRequest,
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Run the full pre-flight compliance check for a mission plan.

    Returns a structured report across 6 domains (DGCA Regulatory,
    Airworthiness, Energy, Airspace Safety CBF, RF/Link Security,
    Document Checklist) plus an attestation signature.

    **AeroFleet 2.0**: this is the primary entry point for all pre-flight
    validation. The CBF gate runs as a trajectory pre-checker (not
    in-flight authority). The LLM council can be requested separately
    for a narrative explanation.
    """
    plan = body.model_dump()

    # Auto-classify origin and destination zones
    origin_zone = _classify_point_zones(body.origin_lat, body.origin_lon, body.city)
    dest_zone = _classify_point_zones(body.dest_lat, body.dest_lon, body.city)

    # Inject zone classification into plan for downstream checks
    plan["in_red_zone"] = dest_zone["in_red_zone"]
    plan["in_yellow_zone"] = dest_zone["in_yellow_zone"]

    # Estimate distance if not provided
    if "distance_km" not in plan:
        import math
        dlat = math.radians(body.dest_lat - body.origin_lat)
        dlon = math.radians(body.dest_lon - body.origin_lon)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(body.origin_lat)) * math.cos(math.radians(body.dest_lat)) * math.sin(dlon / 2) ** 2
        plan["distance_km"] = round(6371 * 2 * math.asin(math.sqrt(a)), 3)

    # Add coordinate keys the CBF gate and mission planner expect
    plan["origin_lat"] = body.origin_lat
    plan["origin_lon"] = body.origin_lon
    plan["dest_lat"] = body.dest_lat
    plan["dest_lon"] = body.dest_lon
    plan["altitude_m"] = body.altitude_m

    try:
        mission_id = f"MIS-{uuid.uuid4().hex[:8].upper()}"
        report = run_pre_flight_check(plan, city=body.city, mission_id=mission_id)
    except Exception as exc:
        logger.error(f"Pre-flight check failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Compliance check failed: {exc}")

    return {
        **dataclasses.asdict(report),
        "zone_info": {
            "origin": origin_zone,
            "destination": dest_zone,
        },
        "estimated_distance_km": plan["distance_km"],
    }


@router.get("/zone", summary="Classify a coordinate against DGCA zones")
async def classify_zone(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    city: str = Query(DEFAULT_CITY, description="City key: pune or mumbai"),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Classify a lat/lon coordinate against all known DGCA restricted sites.

    Returns zone color (RED/YELLOW/GREEN), the sites that drove the
    classification, the altitude ceiling at that point, and the
    permissions required to fly there.
    """
    return _classify_point_zones(lat, lon, city)


@router.get("/dgca-checklist", summary="DGCA document checklist by category")
async def dgca_checklist(
    category: str = Query("Small", description="Drone category: Nano/Micro/Small/Medium/Large"),
    bvlos: bool = Query(False, description="BVLOS operation"),
    in_yellow: bool = Query(False, description="Operation in Yellow zone"),
    in_red: bool = Query(False, description="Operation in Red zone"),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Return the full DGCA document checklist for the given drone category.

    Each item shows: document name, why it's required, the exact DGCA rule
    citation, and how to obtain it.
    """
    mock_plan = {"bvlos": bvlos, "in_yellow_zone": in_yellow, "in_red_zone": in_red}
    checklist = build_dgca_checklist(category, mock_plan)
    required_count = sum(1 for item in checklist if item["required"])
    return {
        "category": category,
        "bvlos": bvlos,
        "checklist": checklist,
        "total_items": len(checklist),
        "required_items": required_count,
        "regulatory_framework": "DGCA Drone Rules 2021 + CAR Section 3 Series X Part I 2018",
    }


@router.get("/rules", summary="List all applicable DGCA rules")
async def list_rules(
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Return all DGCA rules modeled in AeroFleet 2.0 with descriptions."""
    return {
        "framework": "DGCA Drone Rules 2021 (India)",
        "rules": [
            {"rule": "Rule 15(1)", "topic": "UIN Registration", "description": "Every drone (except Nano in Green zone) must have a Unique Identification Number registered on Digital Sky."},
            {"rule": "Rule 18", "topic": "Altitude Ceiling", "description": "Maximum altitude is 120m (400ft) AGL in Green zones, 60m in Yellow zones (near airports)."},
            {"rule": "Rule 19", "topic": "UAOP", "description": "Unmanned Aircraft Operator Permit required for Medium/Large drones and BVLOS operations."},
            {"rule": "Rule 20", "topic": "BVLOS", "description": "Beyond Visual Line of Sight requires filed flight plan (NPNT), safety pilot, ATC permission, and appropriate UAOP."},
            {"rule": "Rule 22", "topic": "Communication", "description": "Drone must have an adequate command link for the planned operation type and range."},
            {"rule": "Rule 24", "topic": "Airspace Zones", "description": "Red Zone = flight prohibited. Yellow Zone = ATC/ATS permission required. Green Zone = free flight within ceiling."},
            {"rule": "Rule 26", "topic": "Insurance", "description": "Third-party liability insurance mandatory for Medium and Large category drones."},
            {"rule": "Rule 36", "topic": "Remote Pilot Certificate", "description": "Pilot must hold a DGCA-issued Remote Pilot Certificate for all but Nano operations."},
        ],
        "weight_categories": [
            {"category": "Nano", "max_weight_kg": 0.25, "notes": "Fewest restrictions in Green zone"},
            {"category": "Micro", "max_weight_kg": 2.0, "notes": "UIN required"},
            {"category": "Small", "max_weight_kg": 25.0, "notes": "RPC + UIN required"},
            {"category": "Medium", "max_weight_kg": 150.0, "notes": "UAOP + Insurance + RPC + UIN"},
            {"category": "Large", "max_weight_kg": None, "notes": "Full regulatory suite"},
        ],
        "restricted_sites_modeled": {
            "pune": ["Pune Airport (Lohegaon)/AFS Pune", "Pune Cantonment (Southern Command HQ)"],
            "mumbai": ["CSIA International Airport", "Juhu Aerodrome", "Naval Dockyard Mumbai", "INS Hamla (Malad)", "BARC Trombay"],
        },
    }
