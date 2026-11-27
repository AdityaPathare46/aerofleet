"""SA1 + FA3: Joint Sensitivity & Vehicle-Clustered False-Alarm Evaluation of Today's Fleet.

DECLARED BEFORE RUNNING (committed and pushed before the first run; nothing below has been computed yet).

Background:
  * FA1 (measure.py, result 9375a6d) failed: 28.8% of good-or-great flights flagged.
  * FA2 (measure_fa2.py, result 85bf071) passed on held-out half H (11.1% [7.3, 16.3] of 190 good-or-great flights),
    but an audit identified three weaknesses:
      (1) FA1/FA2 reported flight-level Wilson CIs that ignore repeated flights per vehicle (violating the paper's
          own Checklist Item #2);
      (2) the unstratified D/H split left 109 good/great flights in D (34.9% baseline) vs 190 in H (25.3% baseline),
          so H's pre-change baseline must be stated alongside its post-change rate;
      (3) FA2 measured specificity only, without a declared sensitivity (SA1) pairing on known-fault or real-crash logs;
      (4) evidence.py used alt > 2.0 m single-envelope airborne detection (which misses low-altitude / downslope
          agricultural spraying passes) and stripped all battery < 10% warnings (hiding mid-air battery collapses).

What changed in the product before this declaration (Step 1 safety fixes):
  * evidence.py: contiguous airborne spans defined by height > 2.0 m OR horizontal speed >= 1.5 m/s.
  * evidence.py + readiness.py: battery < 10% occurring while airborne > 15 s before touchdown (`in_flight=True`)
    counts as a warning; battery < 10% near touchdown / on ground remains a pilot note.

DATA:
  1. FA3 (Specificity — held-out half H, plus D for comparison):
     The same 1,121 ordinary public PX4 flights of 401 vehicles from FA1/FA2 (split fixed at seed 2026: H = 572
     flights / 200 vehicles; D = 549 flights / 201 vehicles).
  2. SA1-A (Sensitivity — RflyMAD real injected faults, ground truth known by firmware injection):
     All readable .ulg logs in external/rflymad/{Real-Motor, Real-Sensors, Real-No_Fault}.
  3. SA1-B (Sensitivity — Expert-diagnosed PX4 forum crash logs, independent of uploader ratings):
     Downloadable .ulg logs in forum_logs/ matched against settled expert conclusions in
     research/results/px4_log_study/forum_expert_labels.csv (drone vs pilot).
  4. SA1-C (Sensitivity — Archive real-hardware crash flights vs prior flights of crashed drones):
     Readable .ulg logs in archive_crash/ (crash flight itself: would the drone be caught before its next flight?)
     compared with ordinary prior flights in within/ (expected low, consistent with the paper's within-drone null).

MEASURES & PASS MARKS (fixed in advance):
  * FA3 (primary specificity): share of held-out H good-or-great flights flagged, reported with BOTH flight-level
    Wilson 95% CI AND 2,000-resample vehicle-cluster bootstrap 95% CI (seed 2026), plus per-vehicle flag rate and
    unrated / all-H rates. PASS MARK: H good-or-great flight flag rate <= 20% (point estimate).
  * SA1-A (primary sensitivity on known ground truth): RflyMAD Real-Sensors sensitivity and Real-No_Fault false-alarm
    rate (Real-Motor reported descriptively, since 15-20% motor loss is mostly absorbed by the controller).
    PASS MARK: Real-Sensors flagged >= 50% AND Real-No_Fault flagged <= 5%.
  * SA1-B (forum expert crashes) and SA1-C (archive crashes vs prior flights): descriptive (no pass mark, reported
    with exact counts, Wilson CIs, and vehicle-cluster CIs where applicable).

OUTPUT: research/results/false_alarms/sa1_fa3_results.json and sa1_fa3_summary.md. Reported whatever it shows.

    python research/false_alarms/measure_sa1_fa3.py
"""
from __future__ import annotations

import csv
import json
import os
import random
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from glob import glob
from typing import Dict, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import measure as fa1  # noqa: E402

DATA = fa1.DATA
OUT = fa1.OUT
GOOD = fa1.GOOD
FORUM_CSV = os.path.join(ROOT, "research", "results", "px4_log_study", "forum_expert_labels.csv")
BOOT_N = 2000
BOOT_SEED = 2026


def eval_one(args: Tuple[str, str]):
    key, path = args
    from aerofleet.assurance.evidence import timeline
    from aerofleet.assurance.flightlog import read_flight_log
    from aerofleet.assurance.readiness import last_flight_summary

    try:
        f = read_flight_log(path)
        ev = timeline({"episodes": []}, f.track, f.modes, f.battery, f.gps, f.param_changes, f.health)
        s = last_flight_summary(0, {"evidence_timeline": ev, "log": {"format": f.format}}, "")
        return {
            "id": key,
            "flagged": bool(s["warnings"] or s["critical_in_flight"]),
            "reasons": sorted({fa1.kind(w) for w in s["warnings"]}),
            "pilot_notes": bool(s["pilot_notes"]),
            "in_flight_battery": any(e.get("kind") == "battery" and e.get("in_flight") for e in ev),
            "vehicle_uuid": f.vehicle_uuid,
        }
    except Exception as e:  # noqa: BLE001
        return {"id": key, "error": str(e)[:120]}


def cluster_boot_ci(rows: List[Dict], cluster_key: str = "vehicle", n_boot: int = BOOT_N, seed: int = BOOT_SEED):
    """2,000-resample cluster bootstrap 95% CI on the flight-level flagged proportion, resampling clusters with replacement."""
    by_c: Dict[str, List[int]] = defaultdict(list)
    for r in rows:
        by_c[str(r.get(cluster_key) or r["id"])].append(1 if r["flagged"] else 0)
    clusters = list(by_c.values())
    if not clusters:
        return None
    rng = random.Random(seed)
    k = len(clusters)
    vals = []
    for _ in range(n_boot):
        num = den = 0
        for _ in range(k):
            c = clusters[rng.randrange(k)]
            num += sum(c)
            den += len(c)
        vals.append(num / den)
    vals.sort()
    p = sum(r["flagged"] for r in rows) / len(rows)
    return [round(p, 4), round(vals[int(0.025 * n_boot)], 4), round(vals[int(0.975 * n_boot)], 4)]


def summarise(rows: List[Dict], cluster_key: str = "vehicle") -> Dict:
    flagged = [r for r in rows if r["flagged"]]
    veh_all = {str(r.get(cluster_key) or r["id"]) for r in rows}
    veh_flag = {str(r.get(cluster_key) or r["id"]) for r in flagged}
    return {
        "flights": len(rows),
        "flagged": len(flagged),
        "wilson": fa1.wilson(len(flagged), len(rows)),
        "cluster_ci": cluster_boot_ci(rows, cluster_key),
        "vehicles": len(veh_all),
        "vehicles_flagged": len(veh_flag),
        "vehicle_share": fa1.wilson(len(veh_flag), len(veh_all)),
        "in_flight_battery_flights": sum(1 for r in rows if r["in_flight_battery"]),
        "pilot_notes": sum(1 for r in rows if r["pilot_notes"]),
        "by_reason": dict(Counter(reason for r in rows for reason in r["reasons"]).most_common(12)),
    }


def run_pool(todo: List[Tuple[str, str]]) -> Tuple[List[Dict], int]:
    ok, bad = [], 0
    with ProcessPoolExecutor(6) as ex:
        for fut in as_completed([ex.submit(eval_one, item) for item in todo]):
            r = fut.result()
            if "error" in r:
                bad += 1
            else:
                ok.append(r)
    return ok, bad


def main() -> None:
    # 1. FA3: Ordinary public PX4 flights (H and D)
    features = {r["log_id"]: r["vehicle"] for r in (json.loads(l) for l in open(fa1.FEATURES))}
    per = {p["log_id"]: p for p in (json.loads(l) for l in open(os.path.join(OUT, "per_flight.jsonl")))}
    paths: Dict[str, str] = {}
    for dirpath, _, files in os.walk(DATA):
        if "/external" in dirpath or "/sitl" in dirpath:
            continue
        for n in files:
            if n.endswith(".ulg") and not n.startswith("._") and n[:-4] in per:
                paths.setdefault(n[:-4], os.path.join(dirpath, n))

    fa_ok, fa_bad = run_pool([(lid, paths[lid]) for lid in per if lid in paths])
    for r in fa_ok:
        meta = per[r["id"]]
        r["half"] = meta["half"]
        r["rating"] = meta["rating"]
        r["vehicle"] = features.get(r["id"], r["vehicle_uuid"] or r["id"])

    # Baseline FA1 numbers on D/H good-or-great for honest comparison
    fa1_h_good = [p for p in per.values() if p["half"] == "H" and p["rating"] in GOOD]
    fa1_d_good = [p for p in per.values() if p["half"] == "D" and p["rating"] in GOOD]
    fa1_baselines = {
        "H_good_or_great_FA1": fa1.wilson(sum(1 for p in fa1_h_good if p["warnings"]), len(fa1_h_good)),
        "D_good_or_great_FA1": fa1.wilson(sum(1 for p in fa1_d_good if p["warnings"]), len(fa1_d_good)),
        "H_good_n": len(fa1_h_good),
        "D_good_n": len(fa1_d_good),
    }

    H = [r for r in fa_ok if r["half"] == "H"]
    D = [r for r in fa_ok if r["half"] == "D"]
    fa3 = {
        "read": len(fa_ok),
        "unreadable": fa_bad,
        "fa1_baselines": fa1_baselines,
        "H_good_or_great": summarise([r for r in H if r["rating"] in GOOD]),
        "H_unrated": summarise([r for r in H if r["rating"] not in GOOD]),
        "H_all": summarise(H),
        "D_good_or_great": summarise([r for r in D if r["rating"] in GOOD]),
        "D_all": summarise(D),
        "pass_mark": "H good-or-great flight flag rate <= 20% (point estimate)",
    }
    fa3["FA3_met"] = bool(fa3["H_good_or_great"]["wilson"] and fa3["H_good_or_great"]["wilson"][0] <= 0.20)

    # 2. SA1-A: RflyMAD real injected faults
    sa1_rfly = {}
    for split in ("Real-Motor", "Real-Sensors", "Real-No_Fault"):
        files = sorted(p for p in glob(f"{DATA}/external/rflymad/{split}/**/*.ulg", recursive=True) if "/._" not in p)
        ok, bad = run_pool([(os.path.basename(p), p) for p in files])
        for r in ok:
            r["vehicle"] = r["vehicle_uuid"] or r["id"]
        sa1_rfly[split] = {**summarise(ok), "unreadable": bad}
    sa1_rfly_met = bool(
        sa1_rfly["Real-Sensors"]["wilson"] and sa1_rfly["Real-Sensors"]["wilson"][0] >= 0.50
        and sa1_rfly["Real-No_Fault"]["wilson"] and sa1_rfly["Real-No_Fault"]["wilson"][0] <= 0.05
    )

    # 3. SA1-B: Expert-diagnosed forum crash logs
    forum_label: Dict[str, Tuple[str, str]] = {}
    if os.path.exists(FORUM_CSV):
        with open(FORUM_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("is_crash") != "yes":
                    continue
                concl = (row.get("expert_conclusion") or "").strip()
                cause = (row.get("cause") or "").strip()
                for lid in (row.get("log_ids") or "").split():
                    forum_label[lid.strip()] = (concl, cause)
    forum_files = sorted(p for p in glob(f"{DATA}/forum_logs/*.ulg") if "/._" not in p)
    f_ok, f_bad = run_pool([(os.path.basename(p)[:-4], p) for p in forum_files])
    for r in f_ok:
        r["vehicle"] = r["vehicle_uuid"] or r["id"]
        r["expert_conclusion"], r["cause"] = forum_label.get(r["id"], ("unmatched", ""))
    sa1_forum = {
        "read": len(f_ok),
        "unreadable": f_bad,
        "expert_drone": summarise([r for r in f_ok if r["expert_conclusion"] == "drone"]),
        "expert_pilot": summarise([r for r in f_ok if r["expert_conclusion"] == "pilot"]),
        "all_forum_logs": summarise(f_ok),
    }

    # 4. SA1-C: Archive real-hardware crash logs vs prior flights in within/
    crash_files = sorted(p for p in glob(f"{DATA}/archive_crash/*.ulg") if "/._" not in p)
    c_ok, c_bad = run_pool([(os.path.basename(p)[:-4], p) for p in crash_files])
    for r in c_ok:
        r["vehicle"] = r["vehicle_uuid"] or r["id"]
    within_files = sorted(p for p in glob(f"{DATA}/within/*.ulg") if "/._" not in p)
    w_ok, w_bad = run_pool([(os.path.basename(p)[:-4], p) for p in within_files])
    for r in w_ok:
        r["vehicle"] = r["vehicle_uuid"] or r["id"]
    sa1_archive = {
        "archive_crash_flights": {**summarise(c_ok), "unreadable": c_bad},
        "within_prior_flights": {**summarise(w_ok), "unreadable": w_bad},
    }

    res = {
        "declared": "research/false_alarms/measure_sa1_fa3.py",
        "FA3": fa3,
        "SA1_RflyMAD": {**sa1_rfly, "pass_mark": "Real-Sensors >= 50% AND Real-No_Fault <= 5%", "SA1_RflyMAD_met": sa1_rfly_met},
        "SA1_Forum": sa1_forum,
        "SA1_Archive": sa1_archive,
    }
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "sa1_fa3_results.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)

    def fmt_ci(ci):
        return f"{100 * ci[0]:.1f}% [{100 * ci[1]:.1f}, {100 * ci[2]:.1f}]" if ci else "n/a"

    hg = fa3["H_good_or_great"]
    hu = fa3["H_unrated"]
    ha = fa3["H_all"]
    dg = fa3["D_good_or_great"]
    lines = [
        "# SA1 + FA3: Sensitivity and Vehicle-Clustered False Alarms of Today's Fleet",
        "",
        "Declared in `research/false_alarms/measure_sa1_fa3.py`. Full JSON in `sa1_fa3_results.json`.",
        "",
        "## FA3: False-alarm rate on ordinary public PX4 flights (vehicle-clustered)",
        "",
        f"FA1 pre-change baseline (same split): H good/great {fmt_ci(fa1_baselines['H_good_or_great_FA1'])} (n={fa1_baselines['H_good_n']}), "
        f"D good/great {fmt_ci(fa1_baselines['D_good_or_great_FA1'])} (n={fa1_baselines['D_good_n']}).",
        "",
        "| Cohort | Flights | Flagged | Flight Wilson 95% CI | Vehicle-Cluster 95% CI | Vehicles flagged | Mid-air batt <10% |",
        "|---|---:|---:|---|---|---|---:|",
        f"| H good/great (primary) | {hg['flights']} | {hg['flagged']} | {fmt_ci(hg['wilson'])} | {fmt_ci(hg['cluster_ci'])} | {hg['vehicles_flagged']}/{hg['vehicles']} ({fmt_ci(hg['vehicle_share'])}) | {hg['in_flight_battery_flights']} |",
        f"| H unrated ordinary | {hu['flights']} | {hu['flagged']} | {fmt_ci(hu['wilson'])} | {fmt_ci(hu['cluster_ci'])} | {hu['vehicles_flagged']}/{hu['vehicles']} ({fmt_ci(hu['vehicle_share'])}) | {hu['in_flight_battery_flights']} |",
        f"| H all ordinary | {ha['flights']} | {ha['flagged']} | {fmt_ci(ha['wilson'])} | {fmt_ci(ha['cluster_ci'])} | {ha['vehicles_flagged']}/{ha['vehicles']} ({fmt_ci(ha['vehicle_share'])}) | {ha['in_flight_battery_flights']} |",
        f"| D good/great (ref) | {dg['flights']} | {dg['flagged']} | {fmt_ci(dg['wilson'])} | {fmt_ci(dg['cluster_ci'])} | {dg['vehicles_flagged']}/{dg['vehicles']} ({fmt_ci(dg['vehicle_share'])}) | {dg['in_flight_battery_flights']} |",
        "",
        f"FA3 pass mark (<= 20% of H good/great): **{'Met' if fa3['FA3_met'] else 'Not met'}**.",
        "",
        "## SA1: Sensitivity on known faults, expert-diagnosed crashes, and archive crashes",
        "",
        "| Stratum | Flights | Flagged | Flight Wilson 95% CI | Vehicle-Cluster 95% CI |",
        "|---|---:|---:|---|---|",
        f"| RflyMAD sensor faults | {sa1_rfly['Real-Sensors']['flights']} | {sa1_rfly['Real-Sensors']['flagged']} | {fmt_ci(sa1_rfly['Real-Sensors']['wilson'])} | {fmt_ci(sa1_rfly['Real-Sensors']['cluster_ci'])} |",
        f"| RflyMAD motor faults | {sa1_rfly['Real-Motor']['flights']} | {sa1_rfly['Real-Motor']['flagged']} | {fmt_ci(sa1_rfly['Real-Motor']['wilson'])} | {fmt_ci(sa1_rfly['Real-Motor']['cluster_ci'])} |",
        f"| RflyMAD fault-free (control) | {sa1_rfly['Real-No_Fault']['flights']} | {sa1_rfly['Real-No_Fault']['flagged']} | {fmt_ci(sa1_rfly['Real-No_Fault']['wilson'])} | {fmt_ci(sa1_rfly['Real-No_Fault']['cluster_ci'])} |",
        f"| Forum expert: aircraft-caused | {sa1_forum['expert_drone']['flights']} | {sa1_forum['expert_drone']['flagged']} | {fmt_ci(sa1_forum['expert_drone']['wilson'])} | {fmt_ci(sa1_forum['expert_drone']['cluster_ci'])} |",
        f"| Forum expert: pilot-caused | {sa1_forum['expert_pilot']['flights']} | {sa1_forum['expert_pilot']['flagged']} | {fmt_ci(sa1_forum['expert_pilot']['wilson'])} | {fmt_ci(sa1_forum['expert_pilot']['cluster_ci'])} |",
        f"| Archive real-hardware crashes | {sa1_archive['archive_crash_flights']['flights']} | {sa1_archive['archive_crash_flights']['flagged']} | {fmt_ci(sa1_archive['archive_crash_flights']['wilson'])} | {fmt_ci(sa1_archive['archive_crash_flights']['cluster_ci'])} |",
        f"| Crashed drones' prior flights (`within/`) | {sa1_archive['within_prior_flights']['flights']} | {sa1_archive['within_prior_flights']['flagged']} | {fmt_ci(sa1_archive['within_prior_flights']['wilson'])} | {fmt_ci(sa1_archive['within_prior_flights']['cluster_ci'])} |",
        "",
        f"SA1-RflyMAD pass mark (Real-Sensors >= 50% and Real-No_Fault <= 5%): **{'Met' if sa1_rfly_met else 'Not met'}**.",
    ]
    md = "\n".join(lines) + "\n"
    with open(os.path.join(OUT, "sa1_fa3_summary.md"), "w", encoding="utf-8") as f:
        f.write(md)
    print(md)


if __name__ == "__main__":
    main()
