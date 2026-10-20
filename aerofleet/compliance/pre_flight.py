"""Pre-flight compliance report — the single authoritative pre-flight check.

AeroFleet 2.0 pivots from runtime drone dispatch to ground-based pre-flight
compliance. This module is the central entry point: given a mission plan
(origin, destination, altitude, payload, drone details, city), it runs all
compliance domains deterministically and returns a unified report.

Domains:
  1. DGCA Regulatory       — zone, altitude, UIN/UAOP, ATC permission
  2. Airworthiness         — weight category, payload limit, FC params
  3. Energy / Battery      — round-trip margin vs. reserve
  4. Airspace Safety       — CBF constraint pre-check on planned trajectory
  5. RF / Link Security    — link budget, C2 encryption, GNSS risk
  6. Document Checklist    — required paperwork by drone category
  7. Mission File Readiness— whether a compliant .waypoints file can be generated

The API writes every report to the per-install signed record (aerofleet/assurance/ledger.py): tamper-
evident, no trusted hardware involved.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional

from aerofleet.agents.compliance_report import compute_compliance_report, DomainStatus
from aerofleet.agents.tools import AgentTools
from aerofleet.city.airspace import AirspaceModel
from aerofleet.city.registry import get_city_config
from aerofleet.city.restricted_sites import PUNE_RESTRICTED_SITES, MUMBAI_RESTRICTED_SITES
from aerofleet.compliance.dgca_checklist import build_dgca_checklist
from aerofleet.compliance.rf_security import assess_rf_security
from aerofleet.safety.cbf_gate import build_cbf_gate, build_trajectory_points_from_plan
from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)

class OverallStatus(str, Enum):
    COMPLIANT = "COMPLIANT"
    AT_RISK = "AT_RISK"
    NON_COMPLIANT = "NON_COMPLIANT"


@dataclass
class ComplianceDomain:
    name: str
    status: str          # COMPLIANT | AT_RISK | NON_COMPLIANT
    issues: List[str] = field(default_factory=list)
    rule_citations: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PreFlightReport:
    """The full pre-flight compliance report for a mission plan."""
    mission_id: str
    city: str
    timestamp_utc: str
    overall_status: str
    domains: Dict[str, Dict[str, Any]]
    document_checklist: List[Dict[str, Any]]
    cbf_certificate: Dict[str, Any]
    mission_file_ready: bool
    # Filled in by the API from the signed record (aerofleet/assurance/ledger.py): a per-install Ed25519
    # key, hash-chained. Earlier this was an HMAC with a key written in the source, which anyone could forge.
    attestation: Dict[str, Any] = field(default_factory=dict)


# ── Status severity ordering
_SEVERITY = {DomainStatus.COMPLIANT.value: 0, DomainStatus.AT_RISK.value: 1, DomainStatus.NON_COMPLIANT.value: 2}


def _worst_status(*statuses: str) -> str:
    return max(statuses, key=lambda s: _SEVERITY.get(s, 0))


def run_pre_flight_check(
    mission_plan: Dict[str, Any],
    city: str = "pune",
    mission_id: Optional[str] = None,
) -> PreFlightReport:
    """Run the full pre-flight compliance check for a mission plan.

    Args:
        mission_plan: Dict with keys:
            origin_lat, origin_lon, dest_lat, dest_lon, altitude_m,
            payload_kg, drone_weight_kg, battery_soc, battery_capacity_wh,
            distance_km, wind_speed_mps, visibility_m, precipitation,
            tx_power_w, data_rate_mbps, uin_registered, atc_permission,
            drone_category (Nano/Micro/Small/Medium/Large),
            deadline_minutes, priority
        city: City key ("pune" or "mumbai")
        mission_id: Optional external ID; auto-generated if not provided

    Returns:
        PreFlightReport with all domain results and attestation signature
    """
    import uuid
    from datetime import datetime, timezone

    mission_id = mission_id or f"MIS-{uuid.uuid4().hex[:8].upper()}"
    logger.info(f"Running pre-flight check: {mission_id} (city={city})")
    start_ts = time.time()

    # ── 1. DGCA Regulatory Domain ─────────────────────────────────────────
    in_red = bool(mission_plan.get("in_red_zone", False))
    in_yellow = bool(mission_plan.get("in_yellow_zone", False))
    zone_color = "RED" if in_red else ("YELLOW" if in_yellow else "GREEN")
    dgca_result = AgentTools.dgca_compliance_check(
        zone_color=zone_color,
        uin_registered=bool(mission_plan.get("uin_registered", False)),
        atc_permission=bool(mission_plan.get("atc_permission", False)),
        altitude_m=float(mission_plan.get("altitude_m", 60.0)),
    )
    dgca_issues = dgca_result.get("issues", [])
    dgca_citations = _dgca_citations(zone_color, mission_plan)
    dgca_domain = ComplianceDomain(
        name="DGCA Regulatory",
        status=_dgca_status(dgca_result, dgca_issues),
        issues=dgca_issues,
        rule_citations=dgca_citations,
        details=dgca_result,
    )

    # ── 2. Airworthiness Domain ───────────────────────────────────────────
    drone_weight = float(mission_plan.get("drone_weight_kg", 0.0)) or None
    payload_kg = float(mission_plan.get("payload_kg", 0.0))
    airworthiness_domain = _check_airworthiness(drone_weight, payload_kg)

    # ── 3. Energy / Battery Domain ────────────────────────────────────────
    battery_domain = _check_battery(mission_plan)

    # ── 4. Airspace Safety (CBF pre-check) Domain ─────────────────────────
    cbf_domain, cbf_certificate = _check_cbf(mission_plan)

    # ── 5. RF / Link Security Domain ─────────────────────────────────────
    rf_domain = assess_rf_security(mission_plan)

    # ── 6. Document Checklist ─────────────────────────────────────────────
    drone_category = mission_plan.get("drone_category", "Small")
    checklist = build_dgca_checklist(drone_category, mission_plan)
    checklist_issues = [item["item"] for item in checklist if item.get("required") and not item.get("provided")]
    checklist_status = DomainStatus.NON_COMPLIANT.value if checklist_issues else DomainStatus.COMPLIANT.value
    checklist_domain = ComplianceDomain(
        name="Document Checklist",
        status=checklist_status,
        issues=[f"Missing: {i}" for i in checklist_issues],
        rule_citations=["DGCA Drone Rules 2021 — Rule 15 (documentation requirements)"],
        details={"items_total": len(checklist), "items_missing": len(checklist_issues)},
    )

    # ── Aggregate ─────────────────────────────────────────────────────────
    all_domains = {
        "dgca_regulatory": asdict(dgca_domain),
        "airworthiness": asdict(airworthiness_domain),
        "energy_battery": asdict(battery_domain),
        "airspace_safety_cbf": asdict(cbf_domain),
        "rf_link_security": asdict(rf_domain),
        "document_checklist": asdict(checklist_domain),
    }
    overall = _worst_status(*[d["status"] for d in all_domains.values()])
    mission_file_ready = (overall != DomainStatus.NON_COMPLIANT.value)

    elapsed_ms = round((time.time() - start_ts) * 1000, 1)
    logger.info(
        f"Pre-flight check complete: {mission_id} → {overall} in {elapsed_ms}ms"
    )

    return PreFlightReport(
        mission_id=mission_id,
        city=city,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        overall_status=overall,
        domains=all_domains,
        document_checklist=checklist,
        cbf_certificate=cbf_certificate,
        mission_file_ready=mission_file_ready,
        attestation={},
    )


# ── Domain helper functions ───────────────────────────────────────────────────

def _dgca_status(result: Dict, issues: List[str]) -> str:
    if result.get("status") == "PASS":
        return DomainStatus.COMPLIANT.value
    hard_markers = ("Red Zone", "exceeds the 120m")
    if any(any(m in i for m in hard_markers) for i in issues):
        return DomainStatus.NON_COMPLIANT.value
    return DomainStatus.AT_RISK.value


def _dgca_citations(zone_color: str, plan: Dict) -> List[str]:
    citations = []
    if zone_color == "RED":
        citations.append("DGCA Drone Rules 2021 — Rule 24: Red Zone flight prohibited")
    elif zone_color == "YELLOW":
        if not plan.get("atc_permission"):
            citations.append("DGCA Drone Rules 2021 — Rule 24: Yellow Zone requires ATC/ATS permission")
    if not plan.get("uin_registered"):
        citations.append("DGCA Drone Rules 2021 — Rule 15: UIN (Unique Identification Number) registration mandatory")
    if float(plan.get("altitude_m", 60)) > 120:
        citations.append("DGCA Drone Rules 2021 — Rule 18: Maximum altitude 120m (400ft) AGL")
    return citations or ["DGCA Drone Rules 2021 — Baseline requirements met"]


_WEIGHT_BOUNDARIES = (0.25, 2.0, 25.0, 150.0)
_WEIGHT_CATEGORIES = ("Nano", "Micro", "Small", "Medium", "Large")


def _check_airworthiness(drone_weight_kg: Optional[float], payload_kg: float) -> ComplianceDomain:
    if drone_weight_kg is None:
        return ComplianceDomain(
            name="Airworthiness",
            status=DomainStatus.AT_RISK.value,
            issues=["Drone weight unknown — cannot classify weight category"],
            rule_citations=["DGCA CAR Section 3 Series X Part I 2018 — weight category classification"],
        )
    total = drone_weight_kg + payload_kg
    category = "Large"
    for i, boundary in enumerate(_WEIGHT_BOUNDARIES):
        if total < boundary:
            category = _WEIGHT_CATEGORIES[i]
            break
    near_boundary = any(abs(total - b) / b < 0.10 for b in _WEIGHT_BOUNDARIES)
    status = DomainStatus.AT_RISK.value if near_boundary else DomainStatus.COMPLIANT.value
    return ComplianceDomain(
        name="Airworthiness",
        status=status,
        issues=["Within 10% of weight-category boundary — verify category assignment"] if near_boundary else [],
        rule_citations=["DGCA CAR Section 3 Series X Part I 2018 — weight category: " + category],
        details={"category": category, "total_weight_kg": round(total, 3), "drone_kg": drone_weight_kg, "payload_kg": payload_kg},
    )


def _check_battery(plan: Dict) -> ComplianceDomain:
    result = AgentTools.battery_margin_check(
        distance_km=float(plan.get("distance_km", 3.0)),
        payload_kg=float(plan.get("payload_kg", 0.5)),
        battery_soc=float(plan.get("battery_soc", 0.8)),
        battery_capacity_wh=float(plan.get("battery_capacity_wh", 500.0)),
    )
    if result.get("status") == "FAIL":
        status = DomainStatus.NON_COMPLIANT.value
        issues = [result.get("reason", "Battery margin insufficient")]
    elif result.get("status") == "WARNING":
        status = DomainStatus.AT_RISK.value
        issues = [result.get("reason", "Low battery margin")]
    else:
        status = DomainStatus.COMPLIANT.value
        issues = []
    return ComplianceDomain(
        name="Energy & Battery",
        status=status,
        issues=issues,
        rule_citations=["DGCA Drone Rules 2021 — Operational safety: battery reserve margin"],
        details=result,
    )


def _check_cbf(plan: Dict):
    """Run CBF gate as a pre-flight trajectory validator (not in-flight authority)."""
    try:
        gate = build_cbf_gate(plan)
        route_points = build_trajectory_points_from_plan(plan)
        result = gate.evaluate_trajectory(route_points)
        violations = [
            {
                "constraint": v.constraint_name,
                "margin": round(v.margin_value, 4),
                "rule": v.rule_citation,
            }
            for v in (result.violations or [])
        ]
        status = DomainStatus.COMPLIANT.value if result.passed else DomainStatus.NON_COMPLIANT.value
        certificate = {
            "passed": result.passed,
            "constraints_checked": 11,
            "violations": violations,
            "safety_margins": result.safety_margins if hasattr(result, "safety_margins") else {},
        }
        return ComplianceDomain(
            name="Airspace Safety (CBF)",
            status=status,
            issues=[f"CBF violation: {v['constraint']} (margin={v['margin']})" for v in violations],
            rule_citations=["AeroFleet CBF Gate — 11 formally-defined safety constraints, h_i(x) ≥ 0"],
            details={"constraints_checked": 11, "violations_count": len(violations)},
        ), certificate
    except Exception as exc:
        logger.warning(f"CBF pre-check failed: {exc}")
        return ComplianceDomain(
            name="Airspace Safety (CBF)",
            status=DomainStatus.AT_RISK.value,
            issues=[f"CBF evaluation unavailable: {exc}"],
            rule_citations=["AeroFleet CBF Gate — evaluation required before mission approval"],
        ), {"passed": False, "error": str(exc)}
