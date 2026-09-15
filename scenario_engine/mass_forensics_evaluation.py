"""Mass forensics evaluation — batched, resumable, 1,000-incident scale-up
of scenario_engine/incident_forensics_evaluation.py's 12-case methodology.

Publication-quality accuracy measurement for the Fleet Incident Forensics
Council: real ground truth derived directly from synthesized CBF safety
margins (via the existing `_labeled()`/`_cert()`, imported not copied),
scored as precision/recall/F1 per factor via the existing `_score_factor`,
pooled across every completed case — never averaged per-batch, matching
how the 12-case script already scores.

1,000 is a deliberate choice, not just "as many as fits": 5x the 200-case
precedent this methodology is modeled on (the same HFACS-LLM Reasoning
dataset in aerofleet_data/), comfortably above the ~384-per-category
threshold for a stable 95%-CI precision/recall estimate. A 5,000-case
target was tried first and dropped — each incident costs 8 sequential
Ollama calls across 4 models (measured directly against
IncidentForensicsWorker._investigate()), so 5,000 incidents would have
been ~40,000 calls, tens of GPU-hours even on a high-end card; 1,000 is
~8,000 calls, roughly 11-22 GPU-hours. Still built to run across multiple
sessions if needed: every individual result is flushed to `results.jsonl`
immediately, so killing this process at any point loses at most one
in-flight incident, and re-running resumes automatically from whatever's
already on disk (never rewrites `dataset_manifest.json` once it exists, so
case_ids stay stable even if this file's generator logic is edited
in between runs).

Run (real, on a machine with Ollama + the model roster pulled):
    python -m scenario_engine.mass_forensics_evaluation

No-GPU pipeline sanity check (this Mac, or anywhere without Ollama):
    USE_MOCK_AGENTS=true python -m scenario_engine.mass_forensics_evaluation --dry-run

Rebuild reports only, no new LLM calls:
    python -m scenario_engine.mass_forensics_evaluation --report-only
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from aerofleet.agents.incident_forensics_worker import IncidentForensicsWorker, IncidentJob, new_incident_id
from scenario_engine.forensics_report_html import render_aggregate_index, render_batch_report
from scenario_engine.incident_forensics_evaluation import FACTOR_NAMES, _score_factor
from scenario_engine.mass_forensics_dataset import GeneratedIncident, load_or_generate_manifest

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STUDY_DIR = REPO_ROOT / "scenario_reports" / "mass_forensics"
DEFAULT_MOCKCHECK_DIR = REPO_ROOT / "scenario_reports" / "mass_forensics_mockcheck"
DEFAULT_TARGET = 1000
DEFAULT_BATCH_SIZE = 250
DEFAULT_SEED = 20260826
DEFAULT_RETRY_MAX = 3


def _is_mock_mode() -> bool:
    return os.environ.get("USE_MOCK_AGENTS", "false").lower() in ("1", "true", "yes")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, obj: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


# ── run_config: written once per study, defines target/batch_size/seed ──

def _load_run_config(study_dir: Path) -> Optional[Dict]:
    path = study_dir / "run_config.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _resolve_run_config(study_dir: Path, target: Optional[int], batch_size: Optional[int], seed: Optional[int]) -> Dict:
    existing = _load_run_config(study_dir)
    if existing is not None:
        for name, requested, stored in (("target", target, existing["target"]),
                                         ("batch_size", batch_size, existing["batch_size"]),
                                         ("seed", seed, existing["seed"])):
            if requested is not None and requested != stored:
                raise SystemExit(
                    f"This study ({study_dir}) was created with {name}={stored}, but this invocation "
                    f"passed --{name.replace('_', '-')} {requested}. Refusing to re-slice an in-progress "
                    f"study's batch boundaries — start a fresh --study-dir instead if you want a different {name}."
                )
        return existing
    config = {
        "target": target or DEFAULT_TARGET, "batch_size": batch_size or DEFAULT_BATCH_SIZE,
        "seed": seed or DEFAULT_SEED, "created_at": _now_iso(),
    }
    _write_json(study_dir / "run_config.json", config)
    return config


# ── results.jsonl: append-only checkpoint, one line per attempt ──

def _results_path(study_dir: Path) -> Path:
    return study_dir / "results.jsonl"


def _load_results(study_dir: Path) -> List[Dict]:
    path = _results_path(study_dir)
    if not path.exists():
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _append_result(study_dir: Path, row: Dict) -> None:
    path = _results_path(study_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
        f.flush()
        os.fsync(f.fileno())


def _refresh_state(rows: List[Dict], retry_max: int) -> Tuple[Dict[str, Dict], Dict[str, int], set, set]:
    latest: Dict[str, Dict] = {}
    counts: Dict[str, int] = {}
    for r in rows:
        counts[r["case_id"]] = counts.get(r["case_id"], 0) + 1
        latest[r["case_id"]] = r  # last occurrence wins — rows are append-ordered
    completed_ids = {cid for cid, r in latest.items() if r["error"] is None}
    excluded_ids = {cid for cid, r in latest.items() if r["error"] is not None and counts[cid] >= retry_max}
    return latest, counts, completed_ids, excluded_ids


# ── running one incident through the real (unmodified) worker ──

def _run_one_case(worker: IncidentForensicsWorker, case: GeneratedIncident, attempt: int, mock_mode: bool) -> Dict:
    job = IncidentJob(
        incident_id=new_incident_id(), city="pune", trigger_type="CBF_REJECTION",
        trigger_detail=case.trigger_detail, frozen_context=case.frozen_context(),
    )
    started_at = _now_iso()
    t0 = time.perf_counter()
    try:
        factors, regulatory, _transcript = worker._investigate(job)
        latency_s = time.perf_counter() - t0
        predictions = {f.get("factor"): f.get("contributed", "UNCERTAIN") for f in factors if f.get("factor")}
        confidence = {f.get("factor"): f.get("confidence") for f in factors if f.get("factor")}
        evidence = {f.get("factor"): f.get("evidence") for f in factors if f.get("factor")}
        return {
            "case_id": case.case_id, "attempt": attempt, "started_at": started_at, "completed_at": _now_iso(),
            "latency_s": latency_s, "mock_mode": mock_mode, "predictions": predictions,
            "confidence": confidence, "evidence": evidence, "regulatory": regulatory, "error": None,
        }
    except Exception as exc:  # noqa: BLE001 — any failure here must become a retryable row, never crash the batch
        latency_s = time.perf_counter() - t0
        return {
            "case_id": case.case_id, "attempt": attempt, "started_at": started_at, "completed_at": _now_iso(),
            "latency_s": latency_s, "mock_mode": mock_mode, "predictions": None,
            "confidence": None, "evidence": None, "regulatory": None, "error": str(exc),
        }


# ── scoring: pools raw counts and reuses the existing _score_factor ──

def aggregate_scores(completed_rows: List[Dict], manifest_by_id: Dict[str, GeneratedIncident]) -> Dict:
    per_factor_predictions: Dict[str, List[str]] = {name: [] for name in FACTOR_NAMES}
    per_factor_ground_truths: Dict[str, List[str]] = {name: [] for name in FACTOR_NAMES}
    per_factor_uncertain: Dict[str, int] = {name: 0 for name in FACTOR_NAMES}
    category_rows: Dict[str, List[Dict]] = {}
    latencies: List[float] = []
    failure_candidates: Dict[str, List[Dict]] = {name: [] for name in FACTOR_NAMES}

    for row in completed_rows:
        case = manifest_by_id.get(row["case_id"])
        if case is None:
            continue
        incident = case.to_labeled_incident()
        latencies.append(row["latency_s"])
        category_rows.setdefault(case.category, []).append(row)
        for factor_name, gt in incident.ground_truth.items():
            pred = (row["predictions"] or {}).get(factor_name, "UNCERTAIN")
            per_factor_predictions[factor_name].append(pred)
            per_factor_ground_truths[factor_name].append(gt)
            if pred == "UNCERTAIN":
                per_factor_uncertain[factor_name] += 1
            if pred != gt:
                failure_candidates[factor_name].append({
                    "case_id": case.case_id, "label": case.label, "predicted": pred, "ground_truth": gt,
                    "evidence": (row.get("evidence") or {}).get(factor_name),
                    "confidence": (row.get("confidence") or {}).get(factor_name),
                })

    per_factor_scores: Dict[str, Dict] = {}
    for factor_name in FACTOR_NAMES:
        preds, gts = per_factor_predictions[factor_name], per_factor_ground_truths[factor_name]
        if not preds:
            per_factor_scores[factor_name] = {"note": "no cases in this pool target this factor"}
            continue
        scored = _score_factor(factor_name, preds, gts)
        scored["uncertain_rate"] = per_factor_uncertain[factor_name] / len(preds)
        per_factor_scores[factor_name] = scored

    scored_only = [s for s in per_factor_scores.values() if "f1" in s]
    macro_f1 = round(sum(s["f1"] for s in scored_only) / len(scored_only), 4) if scored_only else 0.0
    macro_precision = round(sum(s["precision"] for s in scored_only) / len(scored_only), 4) if scored_only else 0.0
    macro_recall = round(sum(s["recall"] for s in scored_only) / len(scored_only), 4) if scored_only else 0.0

    category_breakdown: Dict[str, Dict] = {}
    for category, rows in category_rows.items():
        # Computed directly (not via a recursive aggregate_scores call) —
        # only the per-factor confusion counts are needed per category,
        # not a full nested report.
        cat_preds: Dict[str, List[str]] = {name: [] for name in FACTOR_NAMES}
        cat_gts: Dict[str, List[str]] = {name: [] for name in FACTOR_NAMES}
        for row in rows:
            case = manifest_by_id.get(row["case_id"])
            if case is None:
                continue
            incident = case.to_labeled_incident()
            for factor_name, gt in incident.ground_truth.items():
                cat_preds[factor_name].append((row["predictions"] or {}).get(factor_name, "UNCERTAIN"))
                cat_gts[factor_name].append(gt)
        cat_scored = [_score_factor(f, cat_preds[f], cat_gts[f]) for f in FACTOR_NAMES if cat_preds[f]]
        cat_macro_f1 = round(sum(s["f1"] for s in cat_scored) / len(cat_scored), 4) if cat_scored else None
        category_breakdown[category] = {"n": len(rows), "macro_f1": cat_macro_f1}

    latency_stats = {}
    if latencies:
        sorted_lat = sorted(latencies)
        p95_idx = min(int(len(sorted_lat) * 0.95), len(sorted_lat) - 1)
        latency_stats = {
            "n": len(latencies), "mean": statistics.mean(latencies), "median": statistics.median(latencies),
            "p95": sorted_lat[p95_idx], "max": max(latencies),
        }

    failure_examples: Dict[str, List[Dict]] = {}
    for factor_name, candidates in failure_candidates.items():
        # most genuinely uncertain misses first — a low-confidence wrong
        # answer is more informative to review than a confidently wrong one
        ranked = sorted(candidates, key=lambda c: c["confidence"] if c["confidence"] is not None else -1.0)
        failure_examples[factor_name] = ranked[:5]

    return {
        "per_factor": per_factor_scores, "macro_f1": macro_f1, "macro_precision": macro_precision,
        "macro_recall": macro_recall, "category_breakdown": category_breakdown,
        "latency": latency_stats, "failure_examples": failure_examples,
    }


# ── batch orchestration ──

def _batch_slice(manifest: List[GeneratedIncident], batch_number: int, batch_size: int, target: int) -> List[GeneratedIncident]:
    start = (batch_number - 1) * batch_size
    end = min(batch_number * batch_size, target)
    return manifest[start:end]


def run_study(
    study_dir: Path, target: int, batch_size: int, seed: int, mock_mode: bool,
    max_batches: Optional[int], retry_max: int, allow_mixed_mode: bool, report_only: bool,
    only_batches: Optional[Tuple[int, int]] = None,
) -> None:
    manifest = load_or_generate_manifest(study_dir / "dataset_manifest.json", target=target, seed=seed)
    manifest_by_id = {c.case_id: c for c in manifest}
    n_batches_total = (target + batch_size - 1) // batch_size

    rows_all = _load_results(study_dir)
    if rows_all and not allow_mixed_mode:
        recorded_modes = {r["mock_mode"] for r in rows_all}
        if len(recorded_modes) > 1 or mock_mode not in recorded_modes:
            raise SystemExit(
                f"This study's ledger ({_results_path(study_dir)}) contains results recorded under "
                f"mock_mode={sorted(recorded_modes)}, but this invocation is running with mock_mode={mock_mode}. "
                "Refusing to mix mock and real results into one citable pool. Use a different --study-dir, "
                "or pass --allow-mixed-mode-report if you specifically intend to mix them."
            )

    # ── Phase A: do the work (skipped entirely under --report-only) ──
    if not report_only:
        worker = IncidentForensicsWorker()
        batches_run_this_invocation = 0
        for batch_number in range(1, n_batches_total + 1):
            if only_batches is not None and not (only_batches[0] <= batch_number <= only_batches[1]):
                continue
            batch_cases = _batch_slice(manifest, batch_number, batch_size, target)
            _, counts, completed_ids, excluded_ids = _refresh_state(rows_all, retry_max)
            todo = [c for c in batch_cases if c.case_id not in completed_ids and c.case_id not in excluded_ids]
            if not todo:
                continue
            if max_batches is not None and batches_run_this_invocation >= max_batches:
                print(f"Reached --max-batches {max_batches}; stopping before batch {batch_number:04d} "
                      f"({len(todo)} cases still pending in it). Re-run to continue.")
                break
            print(f"Batch {batch_number:04d}: running {len(todo)} of {len(batch_cases)} incidents "
                  f"({'MOCK' if mock_mode else 'REAL'} mode)...")
            for i, case in enumerate(todo, start=1):
                attempt = counts.get(case.case_id, 0) + 1
                row = _run_one_case(worker, case, attempt, mock_mode)
                _append_result(study_dir, row)
                rows_all.append(row)
                counts[case.case_id] = attempt
                status = "ok" if row["error"] is None else f"ERROR: {row['error']}"
                print(f"  [{i}/{len(todo)}] {case.case_id} ({row['latency_s']:.1f}s) — {status}")
            batches_run_this_invocation += 1

    # ── Phase B: rebuild reports from whatever's on disk (cheap, no LLM calls) ──
    _, _, completed_ids, excluded_ids = _refresh_state(rows_all, retry_max)
    latest, _, _, _ = _refresh_state(rows_all, retry_max)

    batches_meta: List[Dict] = []
    for batch_number in range(1, n_batches_total + 1):
        batch_cases = _batch_slice(manifest, batch_number, batch_size, target)
        batch_ids = [c.case_id for c in batch_cases]
        batch_rows = [latest[cid] for cid in batch_ids if cid in latest]
        if not batch_rows:
            continue
        completed_batch_rows = [r for r in batch_rows if r["error"] is None]
        scores = aggregate_scores(completed_batch_rows, manifest_by_id)
        n_already_complete = sum(1 for cid in batch_ids if cid in completed_ids)
        n_excl = sum(1 for cid in batch_ids if cid in excluded_ids)
        batch_meta = {
            "batch_number": batch_number, "first_case_id": batch_ids[0], "last_case_id": batch_ids[-1],
            "n_in_batch": len(batch_cases), "n_attempted": len(completed_batch_rows), "n_skipped": n_already_complete,
            "n_excluded": n_excl, "macro_f1": scores["macro_f1"],
            "macro_precision": scores["macro_precision"], "macro_recall": scores["macro_recall"],
        }
        report_path = study_dir / "reports" / f"batch_{batch_number:04d}.html"
        _write_text(report_path, render_batch_report(batch_meta, scores, mock_mode))
        _write_json(study_dir / "reports" / f"batch_{batch_number:04d}.json", {"meta": batch_meta, "scores": scores})
        batches_meta.append(batch_meta)

    all_completed_rows = [latest[cid] for cid in completed_ids]
    overall_scores = aggregate_scores(all_completed_rows, manifest_by_id)
    overall_scores["n_completed"] = len(completed_ids)
    overall_scores["n_excluded"] = len(excluded_ids)
    run_config = {"target": target, "batch_size": batch_size, "seed": seed}
    _write_text(study_dir / "index.html", render_aggregate_index(run_config, batches_meta, overall_scores, mock_mode))
    _write_json(study_dir / "index.json", {"run_config": run_config, "batches": batches_meta, "scores": overall_scores})

    print(f"\n{len(completed_ids):,}/{target:,} complete, {len(excluded_ids)} excluded after repeated failures.")
    print(f"Report: {study_dir / 'index.html'}")
    if mock_mode:
        print("*** MOCK MODE — pipeline sanity check only, not a capability measurement. ***")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", type=int, default=None, help="total incidents in the study (default 1000, or 50 under --dry-run)")
    parser.add_argument("--batch-size", type=int, default=None, help="incidents per batch (default 250, or 10 under --dry-run)")
    parser.add_argument("--seed", type=int, default=None, help="dataset generation seed (default 20260826)")
    parser.add_argument("--study-dir", type=str, default=None, help="study output directory")
    parser.add_argument("--max-batches", type=int, default=None, help="stop after running this many NEW batches this invocation (default: run until target or interrupted)")
    parser.add_argument("--retry-failed-max", type=int, default=DEFAULT_RETRY_MAX, help="attempts before permanently excluding a case")
    parser.add_argument("--dry-run", action="store_true", help="small no-GPU pipeline check; requires USE_MOCK_AGENTS to be set")
    parser.add_argument("--report-only", action="store_true", help="rebuild reports from existing results.jsonl without any new LLM calls")
    parser.add_argument("--allow-mixed-mode-report", action="store_true", help="allow pooling mock- and real-mode results into one report (not recommended)")
    parser.add_argument("--only-batches", type=str, default=None,
                         help="restrict this invocation to 1-indexed batch numbers START-END, inclusive "
                              "(e.g. '1-14') — for splitting one study across independent machines/sessions "
                              "that don't share a filesystem. Each machine needs the same --target/--batch-size/"
                              "--seed (so they generate an identical manifest) and the same model config, and "
                              "its local results.jsonl only covers its assigned range until the separate "
                              "results.jsonl files are concatenated back together for a pooled --report-only run.")
    args = parser.parse_args()

    only_batches = None
    if args.only_batches is not None:
        try:
            start_s, end_s = args.only_batches.split("-", 1)
            only_batches = (int(start_s), int(end_s))
        except ValueError:
            raise SystemExit(f"--only-batches must look like 'START-END' (e.g. '1-14'), got {args.only_batches!r}")
        if only_batches[0] < 1 or only_batches[1] < only_batches[0]:
            raise SystemExit(f"--only-batches range is invalid: {only_batches[0]}-{only_batches[1]}")

    mock_mode = _is_mock_mode()
    if args.dry_run and not mock_mode:
        raise SystemExit("--dry-run requires USE_MOCK_AGENTS=true to be set — this is the no-GPU pipeline check, "
                          "not a way to run a small real study. Set the env var, or drop --dry-run for a real run.")

    target = args.target if args.target is not None else (50 if args.dry_run else DEFAULT_TARGET)
    batch_size = args.batch_size if args.batch_size is not None else (10 if args.dry_run else DEFAULT_BATCH_SIZE)
    study_dir = Path(args.study_dir) if args.study_dir else (DEFAULT_MOCKCHECK_DIR if args.dry_run else DEFAULT_STUDY_DIR)

    run_config = _resolve_run_config(study_dir, target, batch_size, args.seed)
    run_study(
        study_dir=study_dir, target=run_config["target"], batch_size=run_config["batch_size"],
        seed=run_config["seed"], mock_mode=mock_mode, max_batches=args.max_batches,
        retry_max=args.retry_failed_max, allow_mixed_mode=args.allow_mixed_mode_report,
        report_only=args.report_only, only_batches=only_batches,
    )


if __name__ == "__main__":
    main()
