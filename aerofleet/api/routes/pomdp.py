"""Formal specification & patent-reference endpoints.

Serves the formal decision-process description and the patent novelty
claims for documentation, the report, and any provisional patent filing.
See docs/PATENT_NOVELTY.md for the full writeup.
"""
from fastapi import APIRouter

router = APIRouter()

FORMAL_DESCRIPTION = """
AeroFleet's dispatch decision process is formalised as
    A = <S, O, M, T, pi>
where:
  S (state)       — fleet state: drone positions, battery SoC, depot queues, active orders
  O (observation) — per-agent partial view: route telemetry, battery telemetry,
                     airspace/geofence telemetry, weather telemetry
  M (memory)      — council debate transcript + pheromone weights + CBF safety margins
  T (transition)  — CBF-gated: h_i(x) >= 0 for all i in {1..11} constraints
  pi (policy)     — Dispatcher synthesis over pheromone-weighted multi-agent consensus
"""


@router.get("/specification")
async def get_formal_specification():
    """Return the formal decision-process specification — for report/patent reference."""
    return {
        "formalism": "A = <S, O, M, T, pi>",
        "description": FORMAL_DESCRIPTION,
        "novel_contributions": [
            "Neuro-symbolic dispatch: LLM agents propose, a deterministic CBF-QP gate has final say",
            "Deterministic airspace pre-screen before LLM debate (compute-cost gated on real risk)",
            "Pheromone-decay weighted council convergence (ACO-inspired)",
            "3D altitude-banded corridor geofencing (vs flat 2D no-fly polygons)",
            "Full decision-provenance trace graph for DGCA-style regulatory auditability",
        ],
        "patent_claim_basis": "See docs/PATENT_NOVELTY.md",
    }


@router.get("/patent-claims")
async def get_patent_claims():
    """Return a structured summary of the patent novelty claims."""
    return {
        "claim_count": 5,
        "claim_1_title": "Hybrid LLM-Council + Formally-Verified CBF Safety Gate for Drone Dispatch",
        "claim_2_title": "Deterministic Airspace Pre-Screen Gating Full Multi-Agent Debate",
        "claim_3_title": "Pheromone-Weighted Iterative Council Convergence",
        "claim_4_title": "3D Altitude-Banded Corridor Geofence Representation",
        "claim_5_title": "End-to-End Decision-Provenance Trace Graph for Regulatory Audit",
        "strongest_claim": "Claim 1 — the LLM never has final say over a safety-critical action",
        "filing_recommendation": "Have a patent professional / your institution's TTO review before filing",
        "full_claims_document": "docs/PATENT_NOVELTY.md",
    }
