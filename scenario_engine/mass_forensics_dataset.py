"""Generates the 5,000-incident manifest for the mass forensics evaluation
study (scenario_engine/mass_forensics_evaluation.py).

Scales scenario_engine/incident_forensics_evaluation.py's existing,
precedent-matched approach (ground truth derived directly from real CBF
margins via `_labeled()`/`_cert()`, not hand-guessed) from 12 hand-built
cases to 5,000 systematically generated ones — reusing those exact
functions by import, so the CONTRIBUTED/NOT_CONTRIBUTED derivation and the
routing_navigation/cross_check_anomaly exclusion behave identically at
scale to how they already behave in the 12-case script.

Stays within the 5 factors that already have a real CBF-margin mapping
(battery_energy, airspace_conflict, weather_environmental,
communications_link, ops_scheduling_capacity) — the other 4 real CBF
constraints (altitude_ceiling, payload_weight_limit, noise_limit,
collision_probability) have no forensics-factor mapping in the existing
taxonomy (a payload/noise/altitude rejection is a trivial pre-flight
rejection, not incident-forensics material) and deliberately aren't
force-fit into one here either.

Full combinatorial coverage across those 5 factors, arity 1-4, each
drawing a magnitude from a real range (not one hardcoded value repeated),
plus two control categories — see CATEGORY_PLAN below for exact counts.

The manifest is deterministic given a seed, but written to disk once and
loaded from disk on every subsequent run (see load_or_generate_manifest)
so a later edit to this generator's code can never reshuffle case_ids
partway through a multi-day study.
"""
from __future__ import annotations

import itertools
import json
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from scenario_engine.incident_forensics_evaluation import LabeledIncident, _cert, _labeled

# The 5 real, margin-grounded forensics factors (confirmed via the
# existing _labeled() call sites in incident_forensics_evaluation.py —
# this is the only mapping with real ground-truth grounding).
CORE_FACTORS: List[str] = [
    "battery_energy", "airspace_conflict", "weather_environmental",
    "communications_link", "ops_scheduling_capacity",
]

# Single-factor subcategories — finer-grained than CORE_FACTORS since
# airspace and weather each cover two independent CBF margins.
# range = (extreme_value, borderline_value), both negative; extreme is
# the deepest violation, borderline is barely-negative. None = no
# continuous margin exists (geofence is boolean in cbf_gate.py).
SINGLE_FACTOR_SUBCATEGORIES: Dict[str, Dict[str, object]] = {
    "battery_energy": {"factor": "battery_energy", "margin_key": "battery_reserve_margin", "range": (-80.0, -0.1)},
    "airspace_separation": {"factor": "airspace_conflict", "margin_key": "min_separation", "range": (-15.0, -0.1)},
    "airspace_geofence": {"factor": "airspace_conflict", "margin_key": "geofence_exclusion", "range": None},
    "weather_wind": {"factor": "weather_environmental", "margin_key": "wind_limit", "range": (-15.0, -0.1)},
    "weather_visibility": {"factor": "weather_environmental", "margin_key": "weather_visibility", "range": (-1500.0, -10.0)},
    "comms": {"factor": "communications_link", "margin_key": "comms_link_margin", "range": (-10.0, -0.1)},
    "ops_capacity": {"factor": "ops_scheduling_capacity", "margin_key": "depot_capacity", "range": (-8.0, -1.0)},
}

# Representative margin key + range used for each core factor at arity>=2
# (per the plan: keep the combinatorics clean rather than also sweeping
# the airspace/weather sub-variant at every combo).
COMBO_MARGIN: Dict[str, Dict[str, object]] = {
    "battery_energy": {"margin_key": "battery_reserve_margin", "range": (-80.0, -0.1)},
    "airspace_conflict": {"margin_key": "min_separation", "range": (-15.0, -0.1)},
    "weather_environmental": {"margin_key": "wind_limit", "range": (-15.0, -0.1)},
    "communications_link": {"margin_key": "comms_link_margin", "range": (-10.0, -0.1)},
    "ops_scheduling_capacity": {"margin_key": "depot_capacity", "range": (-8.0, -1.0)},
}

# All 11 real CBF constraints (aerofleet/safety/cbf_gate.py's
# safety_margin_summary keys) — used only by the near_zero_positive
# control category, which needs every real key present and positive
# (safe) so the LLM sees a fully-populated, genuinely non-violating
# certificate rather than an empty one.
ALL_REAL_CBF_KEYS: List[str] = [
    "min_separation", "geofence_exclusion", "battery_reserve_margin", "altitude_ceiling",
    "wind_limit", "payload_weight_limit", "noise_limit", "collision_probability",
    "comms_link_margin", "depot_capacity", "weather_visibility",
]

# Cosmetic-only zone names for airspace_geofence's textual variety (that
# subcategory's margin is always exactly -1.0 — see module docstring on
# geofence_exclusion being boolean-only).
_GEOFENCE_ZONE_NAMES = [
    "Pune Airport Red Zone", "Lohegaon Military Exclusion", "Hadapsar No-Fly Corridor",
    "Kondhwa Restricted Perimeter", "Yerwada Prison Buffer", "Khadki Cantonment Zone",
]

CATEGORY_PLAN: Dict[str, int] = {
    "single_factor": 2800,
    "pair_factor": 1000,
    "triple_factor": 500,
    "quad_factor": 200,
    "control": 500,
}
assert sum(CATEGORY_PLAN.values()) == 5000


@dataclass
class GeneratedIncident:
    """Raw ingredients for one incident, not the derived LabeledIncident
    itself — ground truth is always (re)computed fresh via the existing
    `_labeled()` on demand (see to_labeled_incident), so there is no
    separately-persisted ground-truth copy that could ever drift from the
    canonical derivation."""

    case_id: str
    category: str       # "single_factor" | "pair_factor" | "triple_factor" | "quad_factor" | "control"
    subcategory: str
    severity_band: str
    label: str
    positive_factors: List[str]
    margins: Dict[str, float] = field(default_factory=dict)
    trigger_detail: Dict[str, object] = field(default_factory=dict)

    def to_labeled_incident(self) -> LabeledIncident:
        incident = _labeled(self.label, self.positive_factors, self.margins)
        if self.trigger_detail:
            incident.trigger_detail = dict(self.trigger_detail)
        return incident

    def frozen_context(self) -> Dict:
        return _cert(self.margins)


def _severity_band(value: Optional[float], value_range: Optional[Tuple[float, float]]) -> str:
    if value is None or value_range is None:
        return "boundary"  # e.g. geofence's fixed -1.0 — not a swept magnitude
    extreme, borderline = value_range
    span = extreme - borderline
    frac = (value - borderline) / span if span else 0.0
    if frac < 0.15:
        return "borderline"
    if frac < 0.35:
        return "mild"
    if frac < 0.65:
        return "moderate"
    if frac < 0.85:
        return "severe"
    return "extreme"


def _next_id(counter: List[int]) -> str:
    counter[0] += 1
    return f"MFI-{counter[0]:05d}"


def _generate_single_factor(rng: random.Random, counter: List[int], count_per_subcat: int) -> List[GeneratedIncident]:
    cases: List[GeneratedIncident] = []
    for subcat, spec in SINGLE_FACTOR_SUBCATEGORIES.items():
        factor = spec["factor"]
        margin_key = spec["margin_key"]
        value_range = spec["range"]
        for i in range(count_per_subcat):
            case_id = _next_id(counter)
            trigger_detail: Dict[str, object] = {}
            if value_range is None:
                # geofence_exclusion: boolean-only, no continuous margin —
                # fixed violation value, cosmetic zone-name variety only.
                margins = {margin_key: -1.0}
                trigger_detail["zone_name"] = _GEOFENCE_ZONE_NAMES[i % len(_GEOFENCE_ZONE_NAMES)]
                band = _severity_band(None, None)
            else:
                value = round(rng.uniform(*value_range), 2)
                margins = {margin_key: value}
                band = _severity_band(value, value_range)
            cases.append(GeneratedIncident(
                case_id=case_id, category="single_factor", subcategory=subcat, severity_band=band,
                label=f"{subcat}_{i:04d}", positive_factors=[factor], margins=margins,
                trigger_detail=trigger_detail,
            ))
    return cases


def _generate_combo(rng: random.Random, counter: List[int], arity: int, category: str, count_per_combo: int) -> List[GeneratedIncident]:
    cases: List[GeneratedIncident] = []
    for combo in itertools.combinations(CORE_FACTORS, arity):
        subcat = "+".join(combo)
        for i in range(count_per_combo):
            case_id = _next_id(counter)
            margins: Dict[str, float] = {}
            bands: List[str] = []
            for factor in combo:
                spec = COMBO_MARGIN[factor]
                value = round(rng.uniform(*spec["range"]), 2)
                margins[spec["margin_key"]] = value
                bands.append(_severity_band(value, spec["range"]))
            # A multi-factor incident is only as easy to fully detect as
            # its most borderline contributing factor — the LLM has to
            # catch every one of them, so the weakest signal dominates
            # difficulty, not the average.
            band_order = ["borderline", "mild", "moderate", "severe", "extreme"]
            overall_band = min(bands, key=band_order.index)
            cases.append(GeneratedIncident(
                case_id=case_id, category=category, subcategory=subcat, severity_band=overall_band,
                label=f"{subcat}_{i:03d}", positive_factors=list(combo), margins=margins,
            ))
    return cases


def _generate_controls(rng: random.Random, counter: List[int], count_per_subtype: int) -> List[GeneratedIncident]:
    cases: List[GeneratedIncident] = []
    for i in range(count_per_subtype):
        case_id = _next_id(counter)
        cases.append(GeneratedIncident(
            case_id=case_id, category="control", subcategory="no_margins_control", severity_band="control",
            label=f"no_margins_control_{i:04d}", positive_factors=[], margins={},
        ))
    for i in range(count_per_subtype):
        case_id = _next_id(counter)
        # Small POSITIVE (safe) margins across every real CBF key — stress
        # tests false-positive robustness right at the safe boundary, not
        # just "nothing populated at all" like no_margins_control.
        margins = {key: round(rng.uniform(0.1, 5.0), 2) for key in ALL_REAL_CBF_KEYS}
        margins["geofence_exclusion"] = 1.0  # boolean convention: +1.0 = not in a red zone
        cases.append(GeneratedIncident(
            case_id=case_id, category="control", subcategory="near_zero_positive_control", severity_band="control",
            label=f"near_zero_positive_control_{i:04d}", positive_factors=[], margins=margins,
        ))
    return cases


def _generate_full_5000(seed: int) -> List[GeneratedIncident]:
    rng = random.Random(seed)
    counter = [0]
    cases: List[GeneratedIncident] = []
    cases += _generate_single_factor(rng, counter, CATEGORY_PLAN["single_factor"] // len(SINGLE_FACTOR_SUBCATEGORIES))
    cases += _generate_combo(rng, counter, 2, "pair_factor", CATEGORY_PLAN["pair_factor"] // len(list(itertools.combinations(CORE_FACTORS, 2))))
    cases += _generate_combo(rng, counter, 3, "triple_factor", CATEGORY_PLAN["triple_factor"] // len(list(itertools.combinations(CORE_FACTORS, 3))))
    cases += _generate_combo(rng, counter, 4, "quad_factor", CATEGORY_PLAN["quad_factor"] // len(list(itertools.combinations(CORE_FACTORS, 4))))
    cases += _generate_controls(rng, counter, CATEGORY_PLAN["control"] // 2)
    expected = sum(CATEGORY_PLAN.values())
    assert len(cases) == expected, f"generator produced {len(cases)} cases, expected {expected} — CATEGORY_PLAN/combinatorics mismatch"
    return cases


def generate_dataset(target: int = 5000, seed: int = 20260826) -> List[GeneratedIncident]:
    """target must be <= 5,000. The full 5,000-case plan is always
    generated deterministically first (fixed category proportions, per
    CATEGORY_PLAN); a smaller target takes a deterministic prefix of it
    rather than a separately-designed small taxonomy — used by --dry-run
    to exercise the exact same generation logic and manifest shape as a
    real study, just fewer cases, so the pipeline check is representative
    rather than a different code path."""
    full = _generate_full_5000(seed)
    if target > len(full):
        raise ValueError(f"target={target} exceeds the fixed 5,000-case plan; adjust CATEGORY_PLAN instead.")
    return full[:target]


def _to_dict(case: GeneratedIncident) -> Dict:
    return asdict(case)


def _from_dict(d: Dict) -> GeneratedIncident:
    return GeneratedIncident(
        case_id=d["case_id"], category=d["category"], subcategory=d["subcategory"],
        severity_band=d["severity_band"], label=d["label"], positive_factors=list(d["positive_factors"]),
        margins=dict(d["margins"]), trigger_detail=dict(d.get("trigger_detail") or {}),
    )


def save_manifest(cases: List[GeneratedIncident], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([_to_dict(c) for c in cases], f, indent=2)


def load_manifest(path: Path) -> List[GeneratedIncident]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [_from_dict(d) for d in data]


def load_or_generate_manifest(path: Path, target: int = 5000, seed: int = 20260826) -> List[GeneratedIncident]:
    if path.exists():
        return load_manifest(path)
    cases = generate_dataset(target=target, seed=seed)
    save_manifest(cases, path)
    return cases
