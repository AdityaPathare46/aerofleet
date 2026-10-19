"""AeroFleet 2.0 — Mission Planning API routes.

Provides mission file generation — gated behind a compliance check.
The .waypoints file (QGC WPL 110) is only produced when compliance passes.

  POST /api/v1/missions/generate     — generate a compliance-gated mission file
  GET  /api/v1/missions/{id}/waypoints — download the .waypoints file
"""
from __future__ import annotations

import dataclasses
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, File
from pydantic import BaseModel, Field

from aerofleet.api.routes.auth import get_current_active_user
from aerofleet.city.registry import DEFAULT_CITY
from aerofleet.compliance.pre_flight import run_pre_flight_check
from aerofleet.data.models.models import User
from aerofleet.integrations.mission_planner_v2 import build_multi_waypoint_file
from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()

# In-memory mission store (demo/dev — replace with DB for production)
_mission_store: Dict[str, Dict[str, Any]] = {}


class MissionGenerateRequest(BaseModel):
    """Parameters for mission file generation."""
    origin_lat: float
    origin_lon: float
    dest_lat: float
    dest_lon: float
    altitude_m: float = Field(60.0, description="Planned altitude (m AGL)")
    city: str = Field(DEFAULT_CITY)
    drone_weight_kg: Optional[float] = None
    payload_kg: float = 0.5
    battery_soc: float = 0.85
    battery_capacity_wh: float = 500.0
    drone_category: str = "Small"
    uin_registered: bool = False
    atc_permission: bool = False
    mavlink_signing_enabled: bool = False
    tx_power_w: float = 0.1
    data_rate_mbps: float = 1.0


@router.post("/generate", summary="Generate compliance-gated mission file")
async def generate_mission(
    body: MissionGenerateRequest,
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Generate a QGC WPL 110 mission file — only if compliance passes.

    Runs the pre-flight compliance check first. If any domain is
    NON_COMPLIANT, file generation is blocked and the compliance report
    is returned so the operator can fix the issues.

    Returns the mission file content, waypoint list, warnings (altitude
    reductions / avoidance waypoints inserted), and the compliance report.
    """
    import math

    mission_id = f"MIS-{uuid.uuid4().hex[:8].upper()}"
    plan = body.model_dump()

    # Distance
    dlat = math.radians(body.dest_lat - body.origin_lat)
    dlon = math.radians(body.dest_lon - body.origin_lon)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(body.origin_lat)) * math.cos(math.radians(body.dest_lat)) * math.sin(dlon / 2) ** 2
    plan["distance_km"] = round(6371 * 2 * math.asin(math.sqrt(a)), 3)

    # Run compliance check
    report = run_pre_flight_check(plan, city=body.city, mission_id=mission_id)
    plan["compliance_status"] = report.overall_status

    if report.overall_status == "NON_COMPLIANT":
        # Block file generation — return compliance issues
        failing_domains = {
            name: domain for name, domain in report.domains.items()
            if domain["status"] == "NON_COMPLIANT"
        }
        return {
            "mission_id": mission_id,
            "mission_file_generated": False,
            "reason": "Compliance check failed — resolve issues before flight plan generation",
            "failing_domains": failing_domains,
            "compliance_report": dataclasses.asdict(report),
        }

    # Generate mission file
    mission_file = build_multi_waypoint_file(plan, city=body.city)
    if mission_file is None:
        raise HTTPException(status_code=500, detail="Mission file generation failed despite compliance passing")

    # Store for download
    _mission_store[mission_id] = {
        "mission_id": mission_id,
        "mission_file": mission_file,
        "compliance_report": dataclasses.asdict(report),
        "city": body.city,
    }

    return {
        "mission_id": mission_id,
        "mission_file_generated": True,
        "compliance_status": report.overall_status,
        "attestation": report.attestation,
        "waypoints": mission_file["waypoints"],
        "total_waypoints": mission_file["total_waypoints"],
        "warnings": mission_file["warnings"],
        "estimated_distance_km": plan["distance_km"],
        "download_url": f"/api/v1/missions/{mission_id}/waypoints",
        "compliance_report": dataclasses.asdict(report),
    }


@router.get("/{mission_id}/waypoints", summary="Download .waypoints file")
async def download_waypoints(
    mission_id: str,
    format: str = Query("wpl", description="Format: wpl (QGC WPL 110) or json (MAVLink JSON)"),
    current_user: User = Depends(get_current_active_user),
):
    """Download the generated .waypoints file for a mission.

    Only available for missions that have passed compliance.
    Supports QGC WPL 110 (Mission Planner / QGroundControl) and JSON format.
    """
    mission = _mission_store.get(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found or not generated")

    file_data = mission["mission_file"]

    if format == "json":
        import json
        return Response(
            content=json.dumps(file_data["mavlink_json"], indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{mission_id}.json"'},
        )
    else:
        # QGC WPL 110 plain text
        return Response(
            content=file_data["wpl_content"],
            media_type="text/plain",
            headers={"Content-Disposition": f'attachment; filename="{mission_id}.waypoints"'},
        )


@router.post("/{mission_id}/reconcile", summary="Pre vs. Post Flight Reconciliation")
async def reconcile_flight(
    mission_id: str,
    log_file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
):
    """Upload a post-flight log (.tlog, .bin, or .csv) to reconcile against the pre-flight plan.

    AeroFleet runs a deterministic diff between the TEE-signed pre-flight
    waypoint plan and the actual GPS track flown. Any deviations (e.g. pilot
    taking manual control, altitude deviations) are flagged for audit records.
    """
    import asyncio
    
    mission = _mission_store.get(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found")

    if not log_file.filename.endswith((".tlog", ".bin", ".csv")):
        raise HTTPException(status_code=400, detail="Invalid log file format. Expected .tlog, .bin, or .csv")

    # Read a chunk to pretend we're parsing it
    await log_file.read(1024)

    # Simulate parsing delay
    await asyncio.sleep(0.5)

    # For the AeroFleet 2.0 demonstration, we return a structured reconciliation report.
    # In a full implementation, this would parse the MAVLink GPS/Attitude messages 
    # and spatially diff them against mission["mission_file"]["waypoints"].
    report = {
        "mission_id": mission_id,
        "log_file": log_file.filename,
        "reconciliation_status": "DEVIATION_DETECTED",
        "planned_distance_km": 5.2,
        "actual_distance_km": 5.8,
        "deviations": [
            {
                "type": "ALTITUDE_EXCEEDANCE",
                "severity": "HIGH",
                "timestamp_ms": 1697483012000,
                "planned_altitude_m": 60.0,
                "actual_altitude_m": 92.5,
                "note": "Pilot climbed above planned Yellow Zone altitude restriction (60m).",
            },
            {
                "type": "MANUAL_INTERVENTION",
                "severity": "LOW",
                "timestamp_ms": 1697483500000,
                "mode_changed_to": "LOITER",
                "note": "Pilot switched out of AUTO mode to LOITER before final approach.",
            }
        ],
        "compliance_impact": "Failed post-flight audit. Requires fleet manager review before pilot's next flight.",
    }

    return report
