"""Merge multiple mass-forensics study directories (each covering a disjoint
--only-batches range, produced on separate machines that don't share a
filesystem — e.g. Kaggle, Colab, a friend's PC) back into one pooled study
directory for a single, citable --report-only run.

Verifies the sources actually share one dataset (same target/batch_size/seed,
so the same manifest and case_ids) before merging — pooling two studies that
silently used different seeds would produce a nonsense report, not just a
messy one.

Usage:
    python -m research.merge_batched_results \
        --source /path/to/kaggle_study \
        --source /path/to/colab_study \
        --source /path/to/friend_study \
        --output /path/to/merged_study

Then finish the report with the existing harness, no new LLM calls:
    python -m scenario_engine.mass_forensics_evaluation --study-dir /path/to/merged_study --report-only
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def _read_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def merge(sources: list[Path], output: Path) -> None:
    if not sources:
        raise SystemExit("Need at least one --source")

    # Compare only target/batch_size/seed — the fields that actually determine the
    # manifest. created_at legitimately differs between independently-created studies.
    KEYS = ("target", "batch_size", "seed")
    run_configs = [_read_json(s / "run_config.json") for s in sources]
    first = {k: run_configs[0][k] for k in KEYS}
    for src, cfg in zip(sources[1:], run_configs[1:]):
        cfg_keys = {k: cfg[k] for k in KEYS}
        if cfg_keys != first:
            raise SystemExit(
                f"Refusing to merge: {sources[0]}'s run_config is {first}, but "
                f"{src}'s is {cfg_keys}. These studies weren't generated with the same "
                "--target/--batch-size/--seed, so they don't share a manifest — "
                "pooling them would silently corrupt the case_id -> ground_truth mapping."
            )

    output.mkdir(parents=True, exist_ok=True)
    shutil.copy(sources[0] / "run_config.json", output / "run_config.json")
    shutil.copy(sources[0] / "dataset_manifest.json", output / "dataset_manifest.json")

    seen_case_ids: dict[str, Path] = {}
    n_rows = 0
    with open(output / "results.jsonl", "w", encoding="utf-8") as out_f:
        for src in sources:
            results_path = src / "results.jsonl"
            if not results_path.exists():
                print(f"warning: {results_path} does not exist, skipping (no results from this source yet)")
                continue
            with open(results_path, "r", encoding="utf-8") as in_f:
                for line in in_f:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    prior_source = seen_case_ids.get(row["case_id"])
                    if prior_source is not None and prior_source != src:
                        print(
                            f"warning: {row['case_id']} appears in both {prior_source} and {src} — "
                            "these were supposed to be disjoint --only-batches ranges. Keeping both "
                            "rows (last one wins on scoring, per the harness's own append-order rule), "
                            "but double-check your batch-range assignment didn't overlap."
                        )
                    seen_case_ids[row["case_id"]] = src
                    out_f.write(json.dumps(row) + "\n")
                    n_rows += 1

    print(f"Merged {n_rows} result rows from {len(sources)} sources into {output}")
    print(f"Unique case_ids covered: {len(seen_case_ids)}")
    print(f"Next: python -m scenario_engine.mass_forensics_evaluation --study-dir {output} --report-only")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", action="append", required=True, dest="sources",
                         help="a study directory to merge in (repeatable)")
    parser.add_argument("--output", required=True, help="directory to write the merged study into")
    args = parser.parse_args()
    merge([Path(s) for s in args.sources], Path(args.output))


if __name__ == "__main__":
    main()
