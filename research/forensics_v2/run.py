"""Run one experimental condition on one dataset against a real local model (Ollama).

  python -m research.forensics_v2.run --condition C2 --dataset eval --n 120
  python -m research.forensics_v2.run --condition C0 C1 C2 C3 C4 --dataset eval hard --n 60

Resumable (cases already in the output file are skipped), one JSON row per case, and — unlike the
original study — every agent's raw text is saved, so any future parser change can be re-scored
without re-running the model. Output: research/results/forensics_v2/<dataset>/<condition>.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

RESULTS = Path("research/results/forensics_v2")
AGENT_IDS = ("BATTERY", "AIRSPACE_SAFETY", "WEATHER", "COMMS", "ROUTE", "OPS", "AI_VALIDATOR", "COMPLIANCE")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--condition", nargs="+", default=["C0", "C1", "C2", "C3", "C4"])
    ap.add_argument("--dataset", nargs="+", default=["eval"])
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--model", default="phi4-mini-reasoning", help="Ollama model for every agent")
    ap.add_argument("--limit", type=int, default=None, help="stop after this many new cases (smoke runs)")
    a = ap.parse_args()

    # Real backend, one model for every agent — set before the agent modules read them.
    os.environ["USE_MOCK_AGENTS"] = "false"
    for agent_id in AGENT_IDS:
        os.environ[f"AGENT_MODEL_{agent_id}"] = a.model

    from aerofleet.agents.incident_forensics_worker import IncidentForensicsWorker, IncidentJob, new_incident_id
    from research.forensics_v2.conditions import conditions
    from research.forensics_v2.datasets import dataset

    all_conditions = conditions()
    for ds in a.dataset:
        cases = dataset(ds, a.n)
        for cname in a.condition:
            strategy = all_conditions[cname]
            out = RESULTS / ds / f"{cname}.jsonl"
            out.parent.mkdir(parents=True, exist_ok=True)
            done = set()
            if out.exists():
                done = {json.loads(l)["case_id"] for l in out.read_text().splitlines() if l.strip()}
            worker = IncidentForensicsWorker(strategy)
            todo = [c for c in cases if c.case_id not in done][: a.limit]
            print(f"[{ds}/{cname}] {len(done)} done, {len(todo)} to run · {strategy.to_dict()}", flush=True)
            for i, case in enumerate(todo, 1):
                job = IncidentJob(incident_id=new_incident_id(), city="pune", trigger_type="CBF_REJECTION",
                                  trigger_detail=case.trigger_detail, frozen_context=case.frozen_context())
                t0 = time.perf_counter()
                row = {"case_id": case.case_id, "category": case.category, "subcategory": case.subcategory,
                       "margins": case.margins, "positive_factors": case.positive_factors,
                       "condition": cname, "strategy": strategy.to_dict(), "model": a.model}
                try:
                    factors, _regulatory, transcript = worker._investigate(job)
                    row.update(
                        predictions={f.get("factor"): f.get("contributed", "UNCERTAIN") for f in factors if f.get("factor")},
                        confidence={f.get("factor"): f.get("confidence") for f in factors if f.get("factor")},
                        evidence={f.get("factor"): f.get("evidence") for f in factors if f.get("factor")},
                        transcript=[{"agent_id": t["agent_id"], "text": t["text"]} for t in transcript],
                        error=None,
                    )
                except Exception as exc:  # noqa: BLE001 — one bad case must not stop a long run
                    row.update(predictions=None, error=str(exc))
                row["latency_s"] = round(time.perf_counter() - t0, 2)
                with out.open("a") as f:
                    f.write(json.dumps(row) + "\n")
                print(f"  {i}/{len(todo)} {case.case_id} {row['latency_s']}s"
                      + (f" ERROR {row['error'][:80]}" if row.get("error") else ""), flush=True)


if __name__ == "__main__":
    main()
