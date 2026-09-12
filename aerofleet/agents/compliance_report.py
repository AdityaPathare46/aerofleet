"""Deterministic, multi-domain compliance report — computed synchronously
alongside the CBF verdict in aerofleet/api/routes/orders.py's
dispatch_order, never a second gate. docs/PATENT_NOVELTY.md's Claim 1
asserts the LLM layer is "architecturally excluded... not just outranked"
from the dispatch decision path; this module doesn't touch that path
either — it only summarizes real, already-computed facts (the CBF gate's
own safety margins, the real DGCA check that already existed but was
never exposed as its own report, real battery/energy accounting) into a
structured, citable shape.

Modeled on a real report-SHAPE precedent found in this project's own,
superseded pre-pivot product: docs/PATENT_CLAIMS.md's dead "five
structured compliance domains... COMPLIANT/AT_RISK/NON_COMPLIANT...
machine-readable compliance report" claim, written for space law (OST/ITU/
IADC). Only the report *shape* transfers here — the domain names below are
genuinely drone/DGCA-specific, not a relabeling of the old space-law ones.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from aerofleet.agents.tools import AgentTools

# No financial/cost modeling exists anywhere else in this codebase to
# derive these from — real, reasonable placeholders (a representative
# fixed per-delivery operational cost and a commercial electricity rate),
# not precisely sourced figures. Same honesty standard as this codebase's
# other unsourced-but-reasonable defaults (e.g. fleet/models.py's
# Battery.capacity_wh=500.0).
FIXED_OPERATIONAL_COST = 25.0
COST_PER_WH = 0.015
DEFAULT_BUDGET_CEILING = 150.0

# DGCA CAR Section 3/X/Part I 2018 weight-category boundaries, in kg
# (see aerofleet_data/regulatory_docs/dgca_car_s3_x_part1_2018.pdf).
_WEIGHT_CATEGORY_BOUNDARIES = (0.25, 2.0, 25.0, 150.0)


class DomainStatus(str, Enum):
    COMPLIANT = "COMPLIANT"
    AT_RISK = "AT_RISK"
    NON_COMPLIANT = "NON_COMPLIANT"


_STATUS_SEVERITY = {DomainStatus.COMPLIANT.value: 0, DomainStatus.AT_RISK.value: 1, DomainStatus.NON_COMPLIANT.value: 2}

# Resolved directly from AgentTools.dgca_compliance_check()'s exact 4
# possible issue strings (aerofleet/agents/tools.py:189-196) — absolute
# rule violations vs. administrative gaps resolvable without changing the
# flight plan. If any hard-violation issue is present, NON_COMPLIANT
# dominates regardless of any soft issues also present.
_HARD_VIOLATION_MARKERS = ("Red Zone", "exceeds the 120m")
_SOFT_VIOLATION_MARKERS = ("UIN", "ATC/ATS permission")


def _classify_dgca_issues(issues: List[str]) -> DomainStatus:
    if not issues:
        return DomainStatus.COMPLIANT
    if any(any(marker in issue for marker in _HARD_VIOLATION_MARKERS) for issue in issues):
        return DomainStatus.NON_COMPLIANT
    return DomainStatus.AT_RISK


def _regulatory_domain(dispatch_plan: Dict[str, Any]) -> Dict[str, Any]:
    """Wraps the real, already-existing AgentTools.dgca_compliance_check()
    — reused directly, not reimplemented. dispatch_plan carries
    in_red_zone/in_yellow_zone booleans (aerofleet/api/routes/orders.py),
    not the zone_color string this function expects, so derive it here."""
    zone_color = "RED" if dispatch_plan.get("in_red_zone") else ("YELLOW" if dispatch_plan.get("in_yellow_zone") else "GREEN")
    result = AgentTools.dgca_compliance_check(
        zone_color=zone_color,
        uin_registered=bool(dispatch_plan.get("uin_registered", True)),
        atc_permission=bool(dispatch_plan.get("atc_permission", False)),
        altitude_m=float(dispatch_plan.get("altitude_m", 60.0)),
    )
    issues = result.get("issues", [])
    return {"status": _classify_dgca_issues(issues).value, "issues": issues, "raw": result}


def _airworthiness_domain(drone_weight_kg: Optional[float], payload_kg: float) -> Dict[str, Any]:
    if drone_weight_kg is None:
        return {"status": DomainStatus.AT_RISK.value, "reason": "drone weight unknown"}
    total_kg = drone_weight_kg + payload_kg
    nano, micro, small, medium = _WEIGHT_CATEGORY_BOUNDARIES
    if total_kg < nano:
        category = "Nano"
    elif total_kg < micro:
        category = "Micro"
    elif total_kg < small:
        category = "Small"
    elif total_kg < medium:
        category = "Medium"
    else:
        category = "Large"
    # AT_RISK if within 10% of a category boundary — a real, if
    # approximate, "close to the line" signal worth surfacing rather than
    # a silent pass right up to the edge.
    near_boundary = any(abs(total_kg - b) / b < 0.10 for b in _WEIGHT_CATEGORY_BOUNDARIES)
    status = DomainStatus.AT_RISK if near_boundary else DomainStatus.COMPLIANT
    return {"status": status.value, "category": category, "total_weight_kg": round(total_kg, 2)}


def _energy_domain(battery_margin_wh: float, reserve_wh: float) -> Dict[str, Any]:
    """Reuses fleet/models.py's Battery accounting — battery_margin_wh and
    reserve_wh are both real, already-computed numbers by the time this
    runs, not recomputed here."""
    if battery_margin_wh < 0:
        status = DomainStatus.NON_COMPLIANT
    elif battery_margin_wh < reserve_wh:
        status = DomainStatus.AT_RISK
    else:
        status = DomainStatus.COMPLIANT
    return {"status": status.value, "battery_margin_wh": round(battery_margin_wh, 1)}


def _airspace_safety_domain(safety_margin_summary: Dict[str, float]) -> Dict[str, Any]:
    """Wraps the CBF gate's own safety_margin_summary directly — the same
    margins the gate itself already computed and used to decide, just
    re-expressed as a domain status rather than re-derived.

    Deliberately binary (COMPLIANT/NON_COMPLIANT only, no AT_RISK tier)
    rather than inventing a "close to violating" threshold: the 11
    constraints' margins live on wildly different natural scales — metres,
    Wh, dB, a probability capped at 1e-4 — so a single flat "< X" cutoff
    applied uniformly across all of them is meaningless (a collision-
    probability margin of 0.0001 can be that constraint's real maximum,
    the safest possible value, while a battery margin of 0.0001 Wh would
    be a genuine razor's edge). A real per-constraint AT_RISK threshold
    would need its own reference scale for each of the 11 — worth doing
    later, not worth faking with one number that's wrong for most of them.
    This mirrors the CBF gate's own actual semantics exactly:
    h_i(x) >= 0 passes, h_i(x) < 0 doesn't, nothing in between."""
    negative = {k: v for k, v in safety_margin_summary.items() if v < 0}
    status = DomainStatus.NON_COMPLIANT if negative else DomainStatus.COMPLIANT
    return {"status": status.value, "margins": safety_margin_summary, "violated_constraints": list(negative.keys())}


def _financial_domain(energy_wh: float, budget_ceiling: float) -> Dict[str, Any]:
    """Fully new — no financial modeling exists anywhere else in this
    codebase. A simple, honestly-labeled estimate, not a real costing
    system."""
    cost = FIXED_OPERATIONAL_COST + energy_wh * COST_PER_WH
    if cost > budget_ceiling:
        status = DomainStatus.NON_COMPLIANT
    elif cost > budget_ceiling * 0.85:
        status = DomainStatus.AT_RISK
    else:
        status = DomainStatus.COMPLIANT
    return {"status": status.value, "cost_estimate_usd": round(cost, 2), "budget_ceiling_usd": budget_ceiling}


def compute_compliance_report(
    dispatch_plan: Dict[str, Any],
    safety_margin_summary: Dict[str, float],
    drone_weight_kg: Optional[float] = None,
    battery_reserve_wh: float = 0.0,
    budget_ceiling: float = DEFAULT_BUDGET_CEILING,
) -> Dict[str, Any]:
    """Pure, synchronous, deterministic — every domain is computed from
    data already in memory by the time dispatch_order calls this. No I/O,
    no LLM call, never on the decision path. overall_status is the worst
    (highest-severity) status across all five domains."""
    domains = {
        "regulatory": _regulatory_domain(dispatch_plan),
        "airworthiness": _airworthiness_domain(drone_weight_kg, float(dispatch_plan.get("payload_kg", 0.0))),
        "energy": _energy_domain(float(dispatch_plan.get("battery_margin_wh", 0.0)), battery_reserve_wh),
        "airspace_safety": _airspace_safety_domain(safety_margin_summary),
        "financial": _financial_domain(float(dispatch_plan.get("energy_wh_required", 0.0)), budget_ceiling),
    }
    overall_status = max((d["status"] for d in domains.values()), key=lambda s: _STATUS_SEVERITY[s])
    return {"domains": domains, "overall_status": overall_status}
