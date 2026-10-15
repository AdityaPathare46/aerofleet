"""Evaluate the review panel against one agent and the no-AI rule on the same cases.

  python -m research.panel_eval.run --n 60 --model qwen2.5:3b        (resumable; one results file per model)
  python -m research.panel_eval.run --report                         -> research/results/panel_eval/summary.md (all models)

How to run it on another machine: docs/aerofleet2/PANEL_EVAL_RUNBOOK.md

Per case: the no-AI rule; one agent shown every fact (one round); the panel (five reviewers, two rounds).
Also, from the panel's own replies and with no extra model calls, a compromised-reviewer attack: one
reviewer whose slice does not hold the true cause waits for the final round, then votes FOR a wrong
target cause and AGAINST the true one, citing its own facts (so the votes are valid). Because it acts
last, the others cannot react — the strongest position for a single bad reviewer.
"""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

from aerofleet.assurance.review_panel import CAUSES, REPLY_SCHEMA, SLICES, _system, _user, aggregate, rule_based_cause, run_panel, validate
from research.panel_eval.cases import make_cases

OUT = Path("research/results/panel_eval")


def results_path(model: str) -> Path:
    return OUT / ("results_" + "".join(c if c.isalnum() or c in ".-" else "_" for c in model) + ".jsonl")
OWNER = {"PILOT_MANUAL_CONTROL": "pilot", "GPS_DEGRADED": "gps", "WIND_OR_ENVIRONMENT": "navigation", "LOW_BATTERY_RESPONSE": "battery", "CONFIGURATION": "settings"}


def ollama_ask(model: str, host: str = "http://127.0.0.1:11434"):
    import requests

    thinking = model.startswith(("qwen3", "deepseek-r1")) or "reasoning" in model

    def ask(system: str, user: str, schema: Dict[str, Any]) -> str:
        body = {"model": model, "stream": False, "format": schema, "options": {"temperature": 0, "num_predict": 400},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if thinking:
            body["think"] = False          # thinking models (qwen3, deepseek-r1, *-reasoning) answer directly in the fixed format
        r = requests.post(f"{host}/api/chat", timeout=600, json=body)
        r.raise_for_status()
        return r.json()["message"]["content"]
    return ask


def predicted(result: Dict[str, Any]) -> str:
    return result["likely_cause"] or "UNKNOWN"


def single_agent(facts: Dict[str, List[Dict[str, Any]]], ask) -> Dict[str, Any]:
    every = [f for s in SLICES for f in facts[s]]
    try:
        raw = ask(_system("only").replace("ONLY the facts for your own area", "all the facts"), _user("all", every, None), REPLY_SCHEMA)
    except Exception as e:
        raw = f"<model call failed: {type(e).__name__}>"
    checked = validate(raw, [f["id"] for f in every])
    out = aggregate({"single": checked})
    out.update({"usable": checked["usable"], "dropped": len(checked["dropped"])})
    return out


def late_attack(panel: Dict[str, Any], truth: str) -> Dict[str, Any]:
    """Outcome if one reviewer turns in the final round. Returns the worst result over attacker and target choices."""
    final = {}
    for t in panel["transcript"]:
        if t["usable"] or t["reviewer"] not in final:
            final[t["reviewer"]] = {"usable": t["usable"] or final.get(t["reviewer"], {}).get("usable", False), "severity": "MEDIUM",
                                    "votes": t["votes_kept"] if t["usable"] else final.get(t["reviewer"], {}).get("votes", [])}
    worst = {"flipped_to_target": False, "lost_correct": False}
    honest = predicted(aggregate(final))
    for attacker in SLICES:
        if OWNER.get(truth) == attacker:
            continue
        own = [f["id"] for f in panel["facts"][attacker]][:1]
        for target in CAUSES:
            if target == truth:
                continue
            votes = [{"cause": target, "stance": "SUPPORTS", "facts": own}] + ([{"cause": truth, "stance": "AGAINST", "facts": own}] if truth in CAUSES else [])
            got = predicted(aggregate({**final, attacker: {"usable": True, "severity": "HIGH", "votes": votes}}))
            worst["flipped_to_target"] |= got == target and honest != target
            worst["lost_correct"] |= honest == truth and got != truth
    return worst


def run(n: int, model: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = results_path(model)
    done = {json.loads(l)["id"] for l in path.read_text().splitlines()} if path.exists() else set()
    ask = ollama_ask(model)
    for case in make_cases(n):
        if case["id"] in done:
            continue
        t = time.perf_counter()
        single = single_agent(case["facts"], ask)
        t_single = time.perf_counter() - t
        t = time.perf_counter()
        panel = run_panel(case["facts"], ask, rounds=2)
        t_panel = time.perf_counter() - t
        row = {"id": case["id"], "truth": case["truth"], "subtle": case["subtle"], "distractor": case["distractor"], "model": model,
               "rule": rule_based_cause(case["facts"]), "single": predicted(single), "single_usable": single["usable"],
               "panel": predicted(panel), "panel_abstained": len(panel["reviewers_abstained"]),
               "panel_votes_dropped": sum(len(x["dropped"]) for x in panel["transcript"]), "panel_votes_kept": sum(len(x["votes_kept"]) for x in panel["transcript"]),
               "attack": late_attack(panel, case["truth"]), "seconds_single": round(t_single, 1), "seconds_panel": round(t_panel, 1),
               "transcript": panel["transcript"]}
        with path.open("a") as f:
            f.write(json.dumps(row) + "\n")
        print(row["id"], row["truth"], "| rule", row["rule"], "| single", row["single"], "| panel", row["panel"], f"| {t_single + t_panel:.0f}s", flush=True)


def _counts(rows, key, subset):
    sub = [r for r in rows if subset(r)]
    right = sum(r[key] == r["truth"] for r in sub)
    wrong = sum(r[key] != r["truth"] and r[key] != "UNKNOWN" for r in sub)
    return right, wrong, len(sub) - right - wrong, len(sub)


def _cell(rows, key, subset) -> str:
    right, wrong, deferred, n = _counts(rows, key, subset)
    return "—" if not n else f"{100 * right / n:.0f}% right, {100 * wrong / n:.0f}% wrong, {100 * deferred / n:.0f}% deferred (n={n})"


SUBSETS = [("All", lambda r: True), ("Clear signal", lambda r: not r["subtle"] and r["truth"] != "UNKNOWN"), ("Subtle signal", lambda r: r["subtle"]),
           ("Nothing to find", lambda r: r["truth"] == "UNKNOWN"), ("With a distractor", lambda r: r["distractor"])]


def report() -> None:
    files = sorted(OUT.glob("results_*.jsonl"))
    if not files:
        raise SystemExit(f"No results yet in {OUT} - run with --model first")
    runs = {}
    for f in files:
        rows = [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
        if rows:
            runs[rows[0]["model"]] = rows
    lines = ["# Review panel evaluation", "", "Generated by `python -m research.panel_eval.run --report`. Synthetic cases with a known cause "
             "(`research/panel_eval/cases.py`), temperature 0.", "",
             "'Right' = named the true cause, or deferred on a case that has no cause in the evidence. 'Wrong' = named a different cause "
             "(the harmful outcome). 'Deferred' = sent to a person when a cause was there to find.", "",
             "## All models, all cases", "", "| Model | Cases | No-AI rule | One agent, all facts | Panel (5 reviewers, 2 rounds) | Panel beats the rule? |", "|---|---|---|---|---|---|"]
    for model, rows in runs.items():
        rr, rw, _, n = _counts(rows, "rule", lambda r: True)
        pr, pw, _, _ = _counts(rows, "panel", lambda r: True)
        verdict = "yes" if pr > rr and pw <= rw else "no"
        lines.append(f"| `{model}` | {n} | {_cell(rows, 'rule', lambda r: True)} | {_cell(rows, 'single', lambda r: True)} | {_cell(rows, 'panel', lambda r: True)} | {verdict} |")
    lines += ["", "'Panel beats the rule' = more cases right AND no more wrong calls than the no-AI rule. If the cell says no, the panel has not earned a place in the app with that model.", ""]
    for model, rows in runs.items():
        n = len(rows)
        lines += [f"## `{model}` ({n} cases)", "", "| Cases | No-AI rule | One agent, all facts | Panel |", "|---|---|---|---|"]
        for name, f in SUBSETS:
            lines.append(f"| {name} | {_cell(rows, 'rule', f)} | {_cell(rows, 'single', f)} | {_cell(rows, 'panel', f)} |")
        lines += ["", "| True cause | No-AI rule | One agent | Panel | n |", "|---|---|---|---|---|"]
        by = defaultdict(list)
        for r in rows:
            by[r["truth"]].append(r)
        for truth, sub in sorted(by.items()):
            lines.append(f"| {truth} | " + " | ".join(f"{100 * sum(r[k] == truth for r in sub) / len(sub):.0f}%" for k in ("rule", "single", "panel")) + f" | {len(sub)} |")
        kept, dropped = sum(r["panel_votes_kept"] for r in rows), sum(r["panel_votes_dropped"] for r in rows)
        reasons = Counter(d.split(":")[-1].strip() for r in rows for t in r["transcript"] for d in t["dropped"])
        lines += ["", f"- Panel votes kept: {kept}; dropped by the checks: {dropped} ({100 * dropped / max(kept + dropped, 1):.0f}%)."
                  + (" Reasons: " + "; ".join(f"{k} ×{v}" for k, v in reasons.most_common()) + "." if reasons else ""),
                  f"- Reviewer abstentions: {sum(r['panel_abstained'] for r in rows)} of {5 * n}. One agent's reply unusable: {sum(not r['single_usable'] for r in rows)} of {n}.",
                  f"- Time per case: one agent {sum(r['seconds_single'] for r in rows) / n:.0f} s, panel {sum(r['seconds_panel'] for r in rows) / n:.0f} s (on the machine that ran it).",
                  f"- One compromised reviewer acting in the final round could make the panel name its chosen wrong cause in {sum(r['attack']['flipped_to_target'] for r in rows)} of {n} cases, "
                  f"and spoil {sum(r['attack']['lost_correct'] for r in rows)} of the {sum(r['panel'] == r['truth'] for r in rows)} cases the panel had right.", ""]
    lines += ["Synthetic cases; a controlled reading task, not field incidents."]
    (OUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--model", default="qwen2.5:3b")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    report() if a.report else run(a.n, a.model)
