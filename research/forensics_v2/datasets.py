"""Datasets for the forensics-v2 experiments — kept strictly apart so nothing learned from the
1,000-case study leaks into what it is evaluated on.

  train  the original study's manifest (seed 20260826). Only used to build few-shot examples.
  eval   a freshly generated plan with a different seed (20260927): same category mix, new margins,
         stratified sample. Never seen by any prompt.
  hard   the eval sample with *near-miss distractors*: every core CBF key the case doesn't violate
         is set to a small positive margin (0.1–3 in its own units). Labels are unchanged — a margin
         that is close to its limit but not violated did not contribute. This is where an agent that
         pattern-matches "number near zero" rather than "my constraint violated" gets caught.
"""
from __future__ import annotations

import random
from dataclasses import replace
from pathlib import Path
from typing import Dict, List

from scenario_engine.mass_forensics_dataset import GeneratedIncident, generate_dataset, load_manifest

TRAIN_MANIFEST = Path("scenario_reports/mass_forensics_final/dataset_manifest.json")
EVAL_SEED = 20260927

# Core CBF keys the generator uses for positives, and the near-miss range for each (own units).
CORE_KEYS = ("battery_reserve_margin", "min_separation", "wind_limit", "comms_link_margin", "depot_capacity")
NEAR_MISS = {"battery_reserve_margin": (0.5, 3.0), "min_separation": (0.2, 2.0), "wind_limit": (0.1, 1.0),
             "comms_link_margin": (0.1, 1.0), "depot_capacity": (1.0, 1.0)}

# Proportional to the study's plan (560/200/100/40/100 of 1,000).
STRATA = {"single_factor": 0.56, "pair_factor": 0.20, "triple_factor": 0.10, "quad_factor": 0.04, "control": 0.10}


def train_cases() -> List[GeneratedIncident]:
    return load_manifest(TRAIN_MANIFEST)


def eval_cases(n: int = 120, seed: int = EVAL_SEED) -> List[GeneratedIncident]:
    """Stratified, deterministic sample of a freshly generated plan."""
    full = generate_dataset(1000, seed=seed)
    rng = random.Random(seed)
    by_cat: Dict[str, List[GeneratedIncident]] = {}
    for c in full:
        by_cat.setdefault(c.category, []).append(c)
    out: List[GeneratedIncident] = []
    for cat, frac in STRATA.items():
        pool = by_cat.get(cat, [])
        k = max(1, round(n * frac))
        out.extend(rng.sample(pool, min(k, len(pool))))
    return sorted(out, key=lambda c: c.case_id)[:n] if len(out) > n else sorted(out, key=lambda c: c.case_id)


def hard_cases(n: int = 120, seed: int = EVAL_SEED) -> List[GeneratedIncident]:
    rng = random.Random(seed + 1)
    out = []
    for c in eval_cases(n, seed):
        margins = dict(c.margins)
        for key in CORE_KEYS:
            if key not in margins:
                lo, hi = NEAR_MISS[key]
                margins[key] = round(rng.uniform(lo, hi), 2)
        out.append(replace(c, case_id=c.case_id.replace("MFI", "HARD"), subcategory=c.subcategory + "+near_miss",
                           margins=margins))
    return out


def dataset(name: str, n: int) -> List[GeneratedIncident]:
    if name == "eval":
        return eval_cases(n)
    if name == "hard":
        return hard_cases(n)
    raise ValueError(f"unknown dataset {name!r} (eval | hard)")
