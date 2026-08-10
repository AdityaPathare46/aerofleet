"""Labeled evaluation harness for the Fleet Incident Forensics Council —
Phase AF.

Mirrors the evaluation methodology of "UAV Accident Forensics via
HFACS-LLM Reasoning" (Drones 9(10):704, 2025): a labeled set of incidents
with known ground-truth contributing factors, scored per-category with
precision/recall/F1, macro-averaged across categories — not a single
aggregate accuracy number, which would hide a model that's great at one
factor and useless at another.

IMPORTANT — read before citing a number from this script's output: run
under USE_MOCK_AGENTS=true, this is a PIPELINE SANITY CHECK, not a
capability measurement. The mock backend's domain-assessment logic
(aerofleet/agents/mock_agent.py's _mock_incident_domain_response) is a
deterministic regex over CBF margin fields — it can only ever get
battery_energy, airspace_conflict, weather_environmental,
communications_link, and ops_scheduling_capacity right BY CONSTRUCTION,
and always returns UNCERTAIN for routing_navigation and
cross_check_anomaly regardless of input, because neither has a
corresponding CBF margin to regex for. A perfect mock-mode score proves
the plumbing works, nothing about reasoning quality. The number worth
citing anywhere is the one from re-running this against a real Ollama
backend (see docs/GPU_LIVE_DEMO_RUNBOOK.md) — that's where the actual
five-domain-plus-two-narrative-factor classification is genuinely being
tested against a language model's judgment, the way the precedent paper's
number is.

Run: python -m scenario_engine.incident_forensics_evaluation
Writes a JSON report to scenario_reports/incident_forensics_eval_<timestamp>.json
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from aerofleet.agents.incident_forensics_worker import IncidentForensicsWorker, IncidentJob, new_incident_id
from aerofleet.agents.incident_taxonomy import DOMAIN_FACTORS

FACTOR_NAMES = [f.factor_name for f in DOMAIN_FACTORS]


@dataclass
class LabeledIncident:
    label: str
    trigger_detail: Dict
    frozen_context: Dict
    # Ground truth per factor — only CONTRIBUTED/NOT_CONTRIBUTED, never
    # UNCERTAIN (this is synthetic data we constructed, so it's always
    # definite by design).
    ground_truth: Dict[str, str] = field(default_factory=dict)


def _cert(margins: Dict[str, float]) -> Dict:
    return {"cbf_certificate": {"passed": False, "safety_margins": margins},
            "dispatch_plan": {"payload_kg": 1.5, "priority": "STANDARD"}}


NEGATIVE_GROUND_TRUTH = {name: "NOT_CONTRIBUTED" for name in FACTOR_NAMES}


def _labeled(label: str, positive_factors: List[str], margins: Dict[str, float]) -> LabeledIncident:
    gt = dict(NEGATIVE_GROUND_TRUTH)
    for f in positive_factors:
        gt[f] = "CONTRIBUTED"
    # routing_navigation and cross_check_anomaly have no CBF-margin ground
    # truth signal in this synthetic dataset — excluded from scoring for
    # cases where they're not the intended positive, rather than silently
    # asserting a NOT_CONTRIBUTED ground truth this dataset can't actually
    # justify. See module docstring.
    for narrative_only in ("routing_navigation", "cross_check_anomaly"):
        if narrative_only not in positive_factors:
            gt.pop(narrative_only, None)
    return LabeledIncident(label=label, trigger_detail={}, frozen_context=_cert(margins), ground_truth=gt)


LABELED_DATASET: List[LabeledIncident] = [
    _labeled("pure_battery", ["battery_energy"], {"battery_reserve_margin": -12.0}),
    _labeled("pure_airspace_separation", ["airspace_conflict"], {"min_separation": -3.0}),
    _labeled("pure_airspace_geofence", ["airspace_conflict"], {"geofence_exclusion": -1.0}),
    _labeled("pure_weather_wind", ["weather_environmental"], {"wind_limit": -2.5}),
    _labeled("pure_weather_visibility", ["weather_environmental"], {"weather_visibility": -500.0}),
    _labeled("pure_comms", ["communications_link"], {"comms_link_margin": -1.5}),
    _labeled("pure_ops_capacity", ["ops_scheduling_capacity"], {"depot_capacity": -1.0}),
    _labeled("battery_and_airspace", ["battery_energy", "airspace_conflict"],
             {"battery_reserve_margin": -8.0, "min_separation": -2.0}),
    _labeled("weather_and_comms", ["weather_environmental", "communications_link"],
             {"wind_limit": -1.0, "comms_link_margin": -0.5}),
    _labeled("battery_airspace_weather_triple", ["battery_energy", "airspace_conflict", "weather_environmental"],
             {"battery_reserve_margin": -20.0, "min_separation": -5.0, "wind_limit": -3.0}),
    _labeled("no_real_violation_control", [], {}),
    _labeled("small_battery_margin_only", ["battery_energy"], {"battery_reserve_margin": -0.5}),
]


def _score_factor(factor_name: str, predictions: List[str], ground_truths: List[str]) -> Dict[str, float]:
    tp = sum(1 for p, g in zip(predictions, ground_truths) if p == "CONTRIBUTED" and g == "CONTRIBUTED")
    fp = sum(1 for p, g in zip(predictions, ground_truths) if p == "CONTRIBUTED" and g == "NOT_CONTRIBUTED")
    fn = sum(1 for p, g in zip(predictions, ground_truths) if p != "CONTRIBUTED" and g == "CONTRIBUTED")
    tn = sum(1 for p, g in zip(predictions, ground_truths) if p != "CONTRIBUTED" and g == "NOT_CONTRIBUTED")

    precision = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if fn == 0 else 0.0)
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": round(precision, 3),
            "recall": round(recall, 3), "f1": round(f1, 3), "n": len(predictions)}


def run_evaluation() -> Dict:
    worker = IncidentForensicsWorker()
    per_factor_predictions: Dict[str, List[str]] = {name: [] for name in FACTOR_NAMES}
    per_factor_ground_truths: Dict[str, List[str]] = {name: [] for name in FACTOR_NAMES}
    per_incident_results = []

    for case in LABELED_DATASET:
        job = IncidentJob(
            incident_id=new_incident_id(), city="pune", trigger_type="CBF_REJECTION",
            trigger_detail=case.trigger_detail, frozen_context=case.frozen_context,
        )
        factors, _regulatory, _transcript = worker._investigate(job)
        predicted = {f["factor"]: f["contributed"] for f in factors}

        case_row = {"label": case.label, "predictions": {}, "ground_truth": case.ground_truth}
        for factor_name, gt in case.ground_truth.items():
            pred = predicted.get(factor_name, "UNCERTAIN")
            per_factor_predictions[factor_name].append(pred)
            per_factor_ground_truths[factor_name].append(gt)
            case_row["predictions"][factor_name] = pred
        per_incident_results.append(case_row)

    per_factor_scores = {}
    for factor_name in FACTOR_NAMES:
        preds, gts = per_factor_predictions[factor_name], per_factor_ground_truths[factor_name]
        if not preds:
            per_factor_scores[factor_name] = {"note": "no labeled cases target this factor in this dataset"}
            continue
        per_factor_scores[factor_name] = _score_factor(factor_name, preds, gts)

    scored = [s for s in per_factor_scores.values() if "f1" in s]
    macro_f1 = round(sum(s["f1"] for s in scored) / len(scored), 4) if scored else None
    macro_precision = round(sum(s["precision"] for s in scored) / len(scored), 4) if scored else None
    macro_recall = round(sum(s["recall"] for s in scored) / len(scored), 4) if scored else None

    return {
        "study": "Fleet Incident Forensics Council — labeled evaluation (Phase AF)",
        "methodology_precedent": "UAV Accident Forensics via HFACS-LLM Reasoning, Drones 9(10):704, 2025 — macro-F1 across categories",
        "generated_at": datetime.utcnow().isoformat(),
        "mock_mode": os.environ.get("USE_MOCK_AGENTS", "false").lower() in ("1", "true", "yes"),
        "n_labeled_incidents": len(LABELED_DATASET),
        "n_categories_scored": len(scored),
        "n_categories_total": len(FACTOR_NAMES),
        "macro_f1": macro_f1,
        "macro_precision": macro_precision,
        "macro_recall": macro_recall,
        "per_factor_scores": per_factor_scores,
        "per_incident_results": per_incident_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.parse_args()

    report = run_evaluation()
    print(json.dumps({k: v for k, v in report.items() if k != "per_incident_results"}, indent=2))
    if report["mock_mode"]:
        print("\n*** MOCK MODE — this is a pipeline sanity check, not a capability measurement. ***")
        print("*** Re-run with USE_MOCK_AGENTS unset against a real Ollama backend for a citable number. ***")

    out_dir = Path(__file__).resolve().parent.parent / "scenario_reports"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"incident_forensics_eval_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(report, indent=2))
    print(f"\nReport written to {out_path}")


if __name__ == "__main__":
    main()
