"""The experimental conditions — each adds one intervention to the previous one, so the analysis
can attribute a change in F1 to a specific fix (see aerofleet/agents/forensics_strategy.py).

  C0  v1 prompt + regex extractor (the 1,000-case study's configuration)
  C1  v2 prompt, robust extractor, factor pinning
  C2  C1 + JSON-schema constrained decoding
  C3  C2 + constraint-ownership map in the context
  C4  C3 + few-shot examples built from the TRAIN split
All at temperature 0 so a re-run reproduces the same verdicts.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from aerofleet.agents.forensics_strategy import FewShotExample, ForensicsStrategy
from aerofleet.agents.incident_taxonomy import CONSTRAINT_TO_FACTOR
from research.forensics_v2.datasets import train_cases

CORE_FACTORS = ["battery_energy", "airspace_conflict", "weather_environmental", "communications_link",
                "ops_scheduling_capacity"]


def build_few_shot() -> Tuple[FewShotExample, ...]:
    """Per factor, three examples from the TRAIN split, chosen to target the measured failure modes:
    its own constraint violated (CONTRIBUTED); only another factor's constraint violated
    (NOT_CONTRIBUTED — the cross-attribution counterexample); nothing violated (NOT_CONTRIBUTED)."""
    cases = train_cases()
    singles = [c for c in cases if c.category == "single_factor" and len(c.margins) == 1]
    controls = [c for c in cases if c.subcategory == "near_zero_positive_control"]
    out: List[FewShotExample] = []
    for i, factor in enumerate(CORE_FACTORS):
        own = next(c for c in singles if c.positive_factors == [factor])
        other = next(c for c in singles[i * 7:] if c.positive_factors != [factor])
        ctrl = controls[i]
        (k_own, v_own), = own.margins.items()
        (k_oth, v_oth), = other.margins.items()
        out += [
            FewShotExample(factor, dict(own.margins), "CONTRIBUTED",
                           f"{k_own} = {v_own} is violated and belongs to {factor}."),
            FewShotExample(factor, dict(other.margins), "NOT_CONTRIBUTED",
                           f"The only violation is {k_oth} = {v_oth}, which belongs to "
                           f"{CONSTRAINT_TO_FACTOR.get(k_oth, 'another factor')}, not {factor}."),
            FewShotExample(factor, {k: v for k, v in list(ctrl.margins.items())[:6]}, "NOT_CONTRIBUTED",
                           "Every margin is positive — nothing is violated, including this factor's."),
        ]
    return tuple(out)


def conditions() -> Dict[str, ForensicsStrategy]:
    c0 = ForensicsStrategy(name="C0", prompt_version="v1", temperature=0.0)
    c1 = ForensicsStrategy(name="C1", prompt_version="v2", temperature=0.0)
    c2 = c1.with_(name="C2", structured_output=True)
    c3 = c2.with_(name="C3", evidence_ownership=True)
    c4 = c3.with_(name="C4", few_shot=build_few_shot())
    return {s.name: s for s in (c0, c1, c2, c3, c4)}
