"""RF & link-security threat assessment for drone missions.

Grounded in the UAV vulnerability taxonomy from Breda et al. 2023
('Security Vulnerabilities in Unmanned Aerial Vehicles', IEEE Access),
this module assesses three threat domains:
  1. RF C2 Link Security — encryption, link budget, frequency band
  2. GNSS Spoofing Risk  — receiver type, anti-spoofing capability
  3. Data Link Exposure  — telemetry encryption, authentication

All assessments are deterministic. The LLM council's CyberSecurityAuditorAgent
may produce a narrative threat report asynchronously after this, but this
module is the authoritative pre-flight security gate.

References:
  - Breda et al. 2023 (IEEE Access): UAV vulnerability taxonomy
  - DGCA Drone Rules 2021 — Rule 22 (communication requirements)
  - STANAG 4586 (UAV control system interoperability)
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List

from aerofleet.agents.compliance_report import DomainStatus
from aerofleet.agents.tools import AgentTools
from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RFSecurityDomain:
    name: str
    status: str
    issues: List[str] = field(default_factory=list)
    rule_citations: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


def assess_rf_security(mission_plan: Dict[str, Any]) -> RFSecurityDomain:
    """Run the full RF/link-security assessment for a mission plan.

    Checks three sub-domains and returns the worst aggregate status.
    """
    issues: List[str] = []
    citations: List[str] = []
    details: Dict[str, Any] = {}

    # ── Sub-domain 1: C2 Link Budget ─────────────────────────────────────
    link_result = AgentTools.comms_link_budget(
        distance_km=float(mission_plan.get("distance_km", 3.0)),
        tx_power_w=float(mission_plan.get("tx_power_w", 0.1)),
        data_rate_mbps=float(mission_plan.get("data_rate_mbps", 1.0)),
    )
    details["link_budget"] = link_result
    if link_result.get("status") == "FAIL":
        issues.append(
            f"C2 link margin negative ({link_result.get('margin_db', '?')} dB) — "
            f"command reliability at this range not guaranteed"
        )
        citations.append("DGCA Drone Rules 2021 — Rule 22: adequate command link required")
        citations.append("Breda et al. 2023 §IV: RF jamming vulnerability at low link margin")
    elif link_result.get("status") == "WARNING":
        issues.append(f"C2 link margin low ({link_result.get('margin_db', '?')} dB) — monitor closely")

    # ── Sub-domain 2: C2 Encryption / MAVLink Signing ────────────────────
    mavlink_signing = bool(mission_plan.get("mavlink_signing_enabled", False))
    encryption_type = str(mission_plan.get("c2_encryption", "none")).lower()
    if not mavlink_signing and encryption_type in ("none", ""):
        issues.append(
            "C2 link has no encryption or MAVLink 2 message signing — "
            "unencrypted command links are a documented BVLOS attack vector "
            "(Breda et al. 2023 §III: C2 interception)"
        )
        citations.append("Breda et al. 2023 §III: Unencrypted C2 link interception vulnerability")
    details["c2_encryption"] = {"mavlink_signing": mavlink_signing, "encryption_type": encryption_type}

    # ── Sub-domain 3: GNSS Anti-Spoofing ─────────────────────────────────
    dual_freq_gnss = bool(mission_plan.get("dual_frequency_gnss", False))
    anti_spoofing = bool(mission_plan.get("gnss_anti_spoofing", False))
    is_bvlos = bool(mission_plan.get("bvlos", False))
    altitude_m = float(mission_plan.get("altitude_m", 60.0))

    gnss_issues = []
    if not dual_freq_gnss and is_bvlos:
        gnss_issues.append(
            "Single-frequency GNSS on a BVLOS mission — spoofing risk elevated "
            "(Breda et al. 2023 §III: GNSS spoofing vector)"
        )
        citations.append("Breda et al. 2023 §III: GNSS spoofing — elevated risk without dual-frequency receiver")
    if not anti_spoofing and altitude_m > 60:
        gnss_issues.append("No GNSS anti-spoofing capability above 60m AGL")
        citations.append("Best practice: dual-frequency L1/L5 receiver for altitudes >60m AGL")

    issues.extend(gnss_issues)
    details["gnss"] = {
        "dual_frequency": dual_freq_gnss,
        "anti_spoofing": anti_spoofing,
        "bvlos": is_bvlos,
    }

    # ── Aggregate ─────────────────────────────────────────────────────────
    if not issues:
        status = DomainStatus.COMPLIANT.value
    elif any("negative" in i or "no encryption" in i or "interception" in i for i in issues):
        status = DomainStatus.NON_COMPLIANT.value
    else:
        status = DomainStatus.AT_RISK.value

    if not citations:
        citations = ["DGCA Drone Rules 2021 — Rule 22: Communication system requirements"]

    return RFSecurityDomain(
        name="RF & Link Security",
        status=status,
        issues=issues,
        rule_citations=citations,
        details=details,
    )
