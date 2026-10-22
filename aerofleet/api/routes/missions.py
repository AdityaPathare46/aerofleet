"""AeroFleet 2.0 — Mission Planning API routes.

Provides mission file generation — gated behind a compliance check.
The .waypoints file (QGC WPL 110) is only produced when compliance passes.

  POST /api/v1/missions/generate        — generate a compliance-gated mission file (stored and signed)
  GET  /api/v1/missions/{id}/waypoints  — download the .waypoints file
  POST /api/v1/missions/{id}/reconcile  — compare a flown log with it (the assurance flight review)
"""
from __future__ import annotations

import dataclasses
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, File
from sqlalchemy.orm import Session

from aerofleet.api.routes.auth import get_current_active_user, get_db
from aerofleet.api.routes.compliance import MissionPlanRequest, registry_facts, sign
from aerofleet.compliance.pre_flight import run_pre_flight_check
from aerofleet.data.models.models import MissionRecord, User
from aerofleet.integrations.mission_planner_v2 import build_multi_waypoint_file
from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()



class MissionGenerateRequest(MissionPlanRequest):
    """Same inputs as the pre-flight check. (It used to be a shorter copy that left out the pilot certificate,
    insurance and maintenance-log fields, so the document checklist could never pass and no file was ever made.)"""


@router.post("/generate", summary="Generate compliance-gated mission file")
async def generate_mission(
    body: MissionGenerateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
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
    drone_id = plan.pop("drone_id")
    facts = registry_facts(db, plan, drone_id)

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
            "inputs": facts,
            "compliance_report": dataclasses.asdict(report),
        }

    # Generate mission file
    mission_file = build_multi_waypoint_file(plan, city=body.city)
    if mission_file is None:
        raise HTTPException(status_code=500, detail="Mission file generation failed despite compliance passing")

    compliance = dataclasses.asdict(report)
    compliance.pop("attestation", None)
    signed = {"mission_id": mission_id, "drone_id": drone_id, "city": body.city, "inputs": facts,
              "wpl_content": mission_file["wpl_content"], "compliance_report": compliance}
    row = MissionRecord(mission_id=mission_id, drone_id=drone_id, city=body.city, plan=plan, mission_file=mission_file,
                        compliance_report=compliance, created_by=current_user.username)
    db.add(row)
    attestation = sign(db, "mission_generated", drone_id or mission_id, signed, current_user)
    row.ledger_seq = attestation["ledger_seq"]
    db.commit()

    return {
        "mission_id": mission_id,
        "mission_file_generated": True,
        "compliance_status": report.overall_status,
        "attestation": attestation,
        "inputs": facts,
        "waypoints": mission_file["waypoints"],
        "total_waypoints": mission_file["total_waypoints"],
        "warnings": mission_file["warnings"],
        "estimated_distance_km": plan["distance_km"],
        "download_url": f"/api/v1/missions/{mission_id}/waypoints",
        "compliance_report": compliance,
    }


@router.get("/{mission_id}/waypoints", summary="Download .waypoints file")
async def download_waypoints(
    mission_id: str,
    format: str = Query("wpl", description="Format: wpl (QGC WPL 110) or json (MAVLink JSON)"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Download the generated .waypoints file for a mission.

    Only available for missions that have passed compliance.
    Supports QGC WPL 110 (Mission Planner / QGroundControl) and JSON format.
    """
    mission = db.get(MissionRecord, mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found or not generated")

    file_data = mission.mission_file

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


@router.post("/{mission_id}/reconcile", summary="Planned vs flown, for a generated mission")
async def reconcile_flight(
    mission_id: str,
    log_file: UploadFile = File(...),
    drone_id: Optional[str] = Query(None, description="Drone that flew it (defaults to the mission's drone)"),
    fleet: str = Query("default"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Compare a flight log (.tlog / .bin) with this mission's .waypoints file.

    Uses the same reader, comparison, likely-cause rule and signed record as the assurance flight upload.
    """
    from aerofleet.api.routes.assurance import review_flight
    from aerofleet.assurance.flightlog import MAX_BYTES as LOG_MAX

    mission = db.get(MissionRecord, mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found")
    drone_id = drone_id or mission.drone_id
    if not drone_id:
        raise HTTPException(status_code=422, detail="Give drone_id: this mission was generated without one")
    out = review_flight(db, current_user, fleet, drone_id, mission.mission_file["wpl_content"], f"{mission_id}.waypoints",
                        await log_file.read(LOG_MAX + 1), log_file.filename or "", mission.city)
    out["mission_id"] = mission_id
    return out
