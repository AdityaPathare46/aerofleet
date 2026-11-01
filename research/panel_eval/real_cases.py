"""Blind real-log case set for the review-panel evaluation (review item open since the early rounds).

PRE-DECLARED (committed and pushed before any model is run on these cases). Status: exploratory (dagger).
Known before declaring: the synthetic-case results (research/results/panel_eval/summary.md; no panel beat the no-AI
rule), the forum expert labels, and the independent reviewer's relabelling (relabel_scores.json).

WHY: the synthetic cases were written by the authors of the rule, so the rule's score there is close to a training
score. Here no author writes a case: each case is a real PX4 crash log, its facts are extracted by the tool's own code
(aerofleet.assurance.flightlog.read_flight_log + review_panel.episode_facts, unchanged), and its label comes from
people who never saw the rule:
  F  forum crashes: every log in forum_logs/ that belongs to a thread recorded as a crash (is_crash = yes) with a
     cause, label = the forum experts' cause (forum_expert_labels.csv), one log per thread (the first listed);
  R  the 72 crashes relabelled blind by the non-author reviewer (relabel_pack/returned/relabel_workbook.xlsx), label =
     the reviewer's main cause; cases the reviewer marked "can't tell" are excluded.
LABEL MAPPING to the panel's causes (fixed now): pilot input / handling, wrong mode or mode switch, flew into obstacle /
ground -> PILOT_MANUAL_CONTROL; GPS / compass / estimator -> GPS_DEGRADED; wind / environment -> WIND_OR_ENVIRONMENT;
battery / power -> LOW_BATTERY_RESPONSE; tuning / configuration -> CONFIGURATION; every other cause (motor, vibration,
software, airframe, radio, not stated, no crash visible, not enough data) -> OUTSIDE: none of the panel's causes, so
the right answer is to defer to a person (UNKNOWN), as for the synthetic "nothing to find" cases.
EPISODE: the last 20 s of the log's position track (start = track end - 20 s, or track start if shorter), kind
"end_of_log" (built with an accepted kind, then that fact's value replaced). The fact "worst distance from the plan" has no plan to compare with and is set to "not measured" (None).
No settings baseline (drift_changes None); in-flight parameter changes from the log.

RUN: research/panel_eval/run.py machinery unchanged (rule_based_cause; one agent shown every fact; the five-reviewer
panel, two rounds; temperature 0) for gemma3:4b, phi4-mini, qwen2.5:3b and qwen3:4b via Ollama. Logs the parser cannot
read, or with fewer than 2 track points, are counted and skipped.
REPORTED per model and method (rule / one agent / panel): right, wrong (named a different cause: the harmful outcome),
deferred, with Wilson 95% intervals; separately for in-scope (truth is a panel cause) and OUTSIDE cases, and for F and R.
WORDING RULE (fixed now): the paper's statement that language-model panels are "not recommended" stands unless, for some
model, the panel has more right answers AND no more wrong answers than the rule on all real cases; in that case the
paper reports it as an exploratory exception for that model.
AMENDMENT 1 (1 Nov 2026, before any result was read): runs moved to a second machine with an NVIDIA RTX GPU because
the Mac took about 110 s per case. All four models are run there on all 97 cases, with the same Ollama tags and
model IDs (gemma3:4b 68ceab7e468a, phi4-mini 78fad5d182a7, qwen2.5:3b 357c53fb659c, qwen3:4b 359d7dd4bcda); a run
with a different ID is reported as such. The 33 gemma3:4b cases first run on the Mac are kept only as a
cross-machine check (mac_partial_real_gemma3_4b.jsonl: share of identical rule/single/panel answers), not pooled.
Instructions: docs/aerofleet2/RTX_PANEL_RUN.md.
Limits stated in the output: forum labels are community diagnoses; the R labels come from one reviewer working from
plots; the 20 s window may miss a cause that began earlier; small local models only.

    python -m research.panel_eval.real_cases build          (writes the case file; no model calls)
    python -m research.panel_eval.real_cases run --model gemma3:4b
    python -m research.panel_eval.real_cases report
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import time
from collections import Counter
from pathlib import Path

from aerofleet.assurance.flightlog import read_flight_log
from aerofleet.assurance.review_panel import episode_facts, rule_based_cause, run_panel
from research.panel_eval.run import late_attack, ollama_ask, predicted, single_agent

DATA = Path(os.environ.get("AEROFLEET_PX4_DATA", "/Volumes/One Touch/AeroFleet_px4_data"))
RES = Path("research/results/px4_log_study")
OUT = Path("research/results/panel_eval")
CASES = OUT / "real_cases.jsonl"
PACK = Path("research/px4_log_study/relabel_pack")
MAP = {"pilot input / handling": "PILOT_MANUAL_CONTROL", "wrong mode or mode switch": "PILOT_MANUAL_CONTROL",
       "flew into obstacle / ground": "PILOT_MANUAL_CONTROL", "gps / compass / estimator": "GPS_DEGRADED",
       "wind / environment": "WIND_OR_ENVIRONMENT", "battery / power": "LOW_BATTERY_RESPONSE",
       "tuning / configuration": "CONFIGURATION"}


def truth_of(cause: str) -> str:
    return MAP.get((cause or "").strip().lower(), "UNKNOWN")


def facts_for(path: str):
    log = read_flight_log(path)
    if len(log.track) < 2:
        return None
    dur = log.track[-1][0] - log.track[0][0]
    start = max(0.0, dur - 20.0)
    ep = {"kind": "off_route", "start_s": start, "duration_s": dur - start, "max_m": 0.0}   # kind/max_m replaced below
    facts = episode_facts(ep, log.track, list(log.modes), battery=log.battery, gps=log.gps, drift_changes=None,
                          param_changes=log.param_changes)
    for f in facts["navigation"]:
        if f["id"] == "nav.max_m":
            f["value"] = None                      # no plan to compare with: not measured
        if f["id"] == "nav.kind":
            f["value"] = "end_of_log"              # the tool's builder only accepts its own episode kinds
    return facts


def _all_paths():
    out = {}
    for d, _, fs in os.walk(DATA):
        for f in fs:
            if f.endswith(".ulg") and not f.startswith("._"):
                out.setdefault(f[:-4], os.path.join(d, f))
    return out


def build() -> None:
    from openpyxl import load_workbook

    paths = _all_paths()
    forum = {p.stem for p in (DATA / "forum_logs").glob("*.ulg") if not p.name.startswith("._")}
    rows, skipped = [], Counter()
    for t in csv.DictReader(open(RES / "forum_expert_labels.csv")):
        if t["is_crash"] != "yes":
            continue
        lid = next((l for l in t["log_ids"].split() if l in forum), None)
        if lid:
            rows.append({"id": f"F{t['topic_id']}", "set": "F", "log_id": lid, "label": t["cause"] or "not stated"})
    key = {int(r["case"]): r["log_id"] for r in csv.DictReader(open(PACK / "key_DO_NOT_OPEN.csv"))}
    ws = load_workbook(PACK / "returned" / "relabel_workbook.xlsx", data_only=True)["Review"]
    for r in ws.iter_rows(min_row=2, values_only=True):
        if r[0] and str(r[4] or "").strip().lower() not in ("", "can't tell"):
            rows.append({"id": f"R{int(r[0]):02d}", "set": "R", "log_id": key[int(r[0])], "label": str(r[5] or "")})
    OUT.mkdir(parents=True, exist_ok=True)
    with CASES.open("w") as f:
        for r in rows:
            try:
                facts = facts_for(paths[r["log_id"]]) if r["log_id"] in paths else None
            except Exception as e:
                skipped[f"parse: {type(e).__name__}"] += 1
                continue
            if facts is None:
                skipped["no log or < 2 track points"] += 1
                continue
            f.write(json.dumps({**r, "truth": truth_of(r["label"]), "facts": facts}, default=str) + "\n")
    n = sum(1 for _ in CASES.open())
    print(f"{n} cases written; skipped {dict(skipped)}")


def run(model: str) -> None:
    path = OUT / ("real_" + "".join(c if c.isalnum() or c in ".-" else "_" for c in model) + ".jsonl")
    done = {json.loads(l)["id"] for l in path.read_text().splitlines()} if path.exists() else set()
    ask = ollama_ask(model)
    for line in CASES.open():
        case = json.loads(line)
        if case["id"] in done:
            continue
        t = time.perf_counter()
        single = single_agent(case["facts"], ask)
        panel = run_panel(case["facts"], ask, rounds=2)
        row = {"id": case["id"], "set": case["set"], "truth": case["truth"], "label": case["label"], "model": model,
               "rule": rule_based_cause(case["facts"]), "single": predicted(single), "panel": predicted(panel),
               "attack": late_attack(panel, case["truth"]), "seconds": round(time.perf_counter() - t, 1)}
        with path.open("a") as f:
            f.write(json.dumps(row) + "\n")
        print(row["id"], row["truth"], "| rule", row["rule"], "| single", row["single"], "| panel", row["panel"], flush=True)


def wilson(k: int, n: int):
    if not n:
        return [None, None]
    z, p = 1.96, k / n
    d = 1 + z * z / n
    c, h = (p + z * z / (2 * n)) / d, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 3), round(c + h, 3)]


def report() -> None:
    out = {"declared_in": "research/panel_eval/real_cases.py docstring",
           "cases": dict(Counter((json.loads(l)["set"], json.loads(l)["truth"]) for l in CASES.open()).most_common())}
    out["cases"] = {f"{a}|{b}": n for (a, b), n in out["cases"].items()}
    subsets = {"all": lambda r: True, "in_scope": lambda r: r["truth"] != "UNKNOWN", "outside": lambda r: r["truth"] == "UNKNOWN",
               "forum": lambda r: r["set"] == "F", "reviewer": lambda r: r["set"] == "R"}
    beats = {}
    for f in sorted(OUT.glob("real_*.jsonl")):
        if f.name == CASES.name:
            continue
        rows = [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
        if not rows:
            continue
        m = rows[0]["model"]
        res = {}
        for name, keep in subsets.items():
            sub = [r for r in rows if keep(r)]
            for k in ("rule", "single", "panel"):
                right = sum(r[k] == r["truth"] for r in sub)
                wrong = sum(r[k] != r["truth"] and r[k] != "UNKNOWN" for r in sub)
                res[f"{name}|{k}"] = {"n": len(sub), "right": right, "wrong": wrong, "deferred": len(sub) - right - wrong,
                                      "right_ci": wilson(right, len(sub)), "wrong_ci": wilson(wrong, len(sub))}
        a = res["all|panel"], res["all|rule"]
        beats[m] = bool(a[0]["right"] > a[1]["right"] and a[0]["wrong"] <= a[1]["wrong"])
        res["attack_flipped"] = sum(r["attack"]["flipped_to_target"] for r in rows)
        out[m] = res
    out["panel_beats_rule"] = beats
    out["wording"] = "exception: " + ", ".join(k for k, v in beats.items() if v) if any(beats.values()) else "not recommended stands"
    out["limits"] = ("forum labels are community diagnoses; R labels from one reviewer working from plots; 20 s window; "
                     "small local models")
    (OUT / "real_cases_summary.json").write_text(json.dumps(out, indent=1))
    (OUT / "real_cases_summary.md").write_text("# Review panel on real labelled crash logs\n\nDeclared in "
                                               "`research/panel_eval/real_cases.py`.\n\n```\n" + json.dumps(out, indent=1) + "\n```\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "run", "report"])
    ap.add_argument("--model")
    a = ap.parse_args()
    {"build": build, "run": lambda: run(a.model), "report": report}[a.cmd]()
