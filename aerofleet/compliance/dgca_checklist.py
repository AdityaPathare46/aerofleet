"""DGCA document checklist generator.

Given a drone weight category and the operator's stated document status,
returns the full list of required documents per DGCA Drone Rules 2021 and
CAR Section 3, with COMPLIANT/MISSING status per item.

Source: DGCA Drone Rules 2021, CAR Section 3 Series X Part I 2018.
"""
from __future__ import annotations

from typing import Any, Dict, List


# The UAOP (Unmanned Aircraft Operator Permit) is deliberately absent: the Drone Rules 2021 abolished it
# (Ministry of Civil Aviation / PIB release of 26 Aug 2021, PRID 1749154). It was required under the
# earlier UAS Rules 2021.


def build_dgca_checklist(drone_category: str, mission_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build a DGCA document checklist for the given drone category.

    Args:
        drone_category: One of Nano, Micro, Small, Medium, Large
        mission_plan: Dict with operator-supplied boolean flags for each document

    Returns:
        List of checklist items, each with:
            item, description, required, provided, rule_citation, how_to_obtain
    """
    cat = drone_category.capitalize()
    is_nano = cat == "Nano"
    is_micro = cat == "Micro"
    is_bvlos = bool(mission_plan.get("bvlos", False))
    in_yellow = bool(mission_plan.get("in_yellow_zone", False))
    in_red = bool(mission_plan.get("in_red_zone", False))

    checklist = []

    # UIN — required for all except Nano (<250g) for personal use in Green zones
    uin_required = not (is_nano and not in_yellow and not in_red)
    checklist.append({
        "item": "UIN (Unique Identification Number)",
        "description": "Digital Sky UIN registration for the drone.",
        "required": uin_required,
        "provided": bool(mission_plan.get("uin_registered", False)),
        "rule_citation": "DGCA Drone Rules 2021 — Rule 15(1)",
        "how_to_obtain": "Register on https://digitalsky.dgca.gov.in",
    })

    # Remote Pilot Certificate — required for all commercial ops
    checklist.append({
        "item": "Remote Pilot Certificate",
        "description": "DGCA-issued certificate for the operating pilot.",
        "required": not is_nano,
        "provided": bool(mission_plan.get("rpc_provided", False)),
        "rule_citation": "DGCA Drone Rules 2021 — Rule 36",
        "how_to_obtain": "Complete DGCA-approved remote pilot training",
    })

    # Insurance — third-party insurance is mandatory for every drone except nano (legal summaries of the
    # Drone Rules 2021; not checked against the Gazette text)
    checklist.append({
        "item": "Third-Party Insurance",
        "description": "Liability insurance covering third-party damage.",
        "required": not is_nano,
        "provided": bool(mission_plan.get("insurance_provided", False)),
        "rule_citation": "DGCA Drone Rules 2021 — Rule 26",
        "how_to_obtain": "Obtain from IRDAI-registered insurer",
    })

    # ATC/ATS permission — required for Yellow zone
    checklist.append({
        "item": "ATC/ATS Permission",
        "description": "Air Traffic Control clearance for Yellow/Red zone flight.",
        "required": in_yellow or in_red,
        "provided": bool(mission_plan.get("atc_permission", False)),
        "rule_citation": "DGCA Drone Rules 2021 — Rule 24(2)",
        "how_to_obtain": "Submit request via Digital Sky NPNT at least 24h before flight",
    })

    # Flight plan filing — required for BVLOS
    checklist.append({
        "item": "Flight Plan (NPNT-linked)",
        "description": "Filed flight plan with NPNT No Permission No Takeoff compliance.",
        "required": is_bvlos,
        "provided": bool(mission_plan.get("flight_plan_filed", False)),
        "rule_citation": "DGCA Drone Rules 2021 — Rule 20 (BVLOS)",
        "how_to_obtain": "File via Digital Sky NPNT before flight",
    })

    # Drone maintenance logbook
    checklist.append({
        "item": "Drone Maintenance Logbook",
        "description": "Up-to-date maintenance records for the drone.",
        "required": not is_nano,
        "provided": bool(mission_plan.get("maintenance_log_current", False)),
        "rule_citation": "DGCA CAR Section 3 Series X Part I 2018",
        "how_to_obtain": "Maintain per manufacturer schedule; log all repairs",
    })

    # Safety pilot (required for BVLOS)
    checklist.append({
        "item": "Safety Pilot / Visual Observer",
        "description": "Trained observer for BVLOS operations.",
        "required": is_bvlos,
        "provided": bool(mission_plan.get("safety_pilot_present", False)),
        "rule_citation": "DGCA Drone Rules 2021 — Rule 20(d) (BVLOS)",
        "how_to_obtain": "Assign a trained remote pilot as BVLOS observer",
    })

    # None of the rule numbers above has been checked against the Gazette text of the Drone Rules 2021.
    for item in checklist:
        item["citation_verified"] = False
    return checklist
