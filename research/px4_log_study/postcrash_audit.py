"""Post-crash flight audit: do the within-drone samples contain flights flown after the crash?

PRE-DECLARED (committed and pushed before this script is run). Status: exploratory (dagger), declared after the
Round 14 audit, not blind.

Why: the Round 14 GPS check (r14_audit.py) found that 47 of 95 crash-day exposure flights in the between-drone sample
were flown after the crash. The within-drone selection (within_drone.select) uses the same rule, "dated on or before
the crash day", so its earlier flights may include post-crash flights too. Those flights feed the within-drone rank
test (Q3b), the within-drone Group-CV model (Table 6 Step 6), the caliper analysis and the factorial audit's
same-aircraft (S) cells.

Prior knowledge, stated up front: the published values below (anchors) and the Round 14 between-drone counts. Nothing
about the ordering of the within-drone same-day flights has been looked at. Counted (not ordered or scored) while
writing this: 217 of the 475 selected earlier flights share the crash's date, spread over 67 crashes. The existing sensitivity in
within_drone.md drops every crash-day flight; this audit drops only those GPS shows were flown after the crash.

ORDERING: every earlier flight in within_drone_features.jsonl with same_day == "1" is compared with its crash log by
GPS UTC start time (r14_audit.utc_start: first vehicle_gps_position / sensor_gps sample with time_utc_usec > 0,
shifted back to the log start). precedes / follows / undeterminable (no valid GPS UTC in either log). Flights dated
before the crash day are taken as preceding (the index date is the only order available; stated limitation).
Report counts by flight and by crash.
Two filtered versions of every analysis: F = without "follows"; FU = without "follows" and "undeterminable".
A crash left with too few earlier flights for an analysis is dropped by that analysis's own rule (counted).

ANALYSES (each run as published first; that run is the anchor):
  A  Within-drone rank test (within_drone.rank_test, rng seed 0, vib_p95 then tune_rms, same source as the crash
     flight, >= 3 earlier flights). Anchors (within_drone.md): vib n 61, mean rank 0.48 +- 0.01; tune n 46, mean
     rank 0.50 +- 0.01.
  B  Within-drone Group-CV model (11 stored features, crash vs its earlier flights, folds by crash, seeds 42-46,
     clusters sorted; factorial_audit.cv_scores). Cluster bootstrap over drones, 2,000 resamples, seed 2029, on the
     seed-averaged out-of-fold scores. Anchor: 0.559 +- 0.01 (the reproducible value from factorial_audit A2).
  C  Caliper 0.25 (same construction as r14_audit Part A, earlier flights filtered before matching): lift_5 and its
     paired cluster CI for F11 and F8. Anchors: 36 airframes, F11 lift_5 +0.110 +- 0.005, F8 lift_5 +0.077 +- 0.005.
  D  Factorial same-aircraft cells (C2 vs S, factorial_audit constant subset and cached features), vehicle-grouped
     CV, for m in {0, 10} x W in {full, first30}; cluster bootstrap as B. Anchor: m10 full group 0.534 +- 0.005.
  ABORT: if any anchor fails, stop and report; compute no filtered values.

DECISION RULES (fixed now; a published conclusion is "changed" only by these):
  A  The published "no within-drone warning" changes if either primary feature has one-sided p < 0.025 in F.
  B  The published "no detectable signal" changes if the F cluster CI lower bound exceeds 0.50.
  C  The masking reading keeps support only if F8 lift_5 >= 0.05 and its CI excludes 0 in F (the Round 14 rule).
  D  "Same-aircraft comparison brings AUC to chance" changes if the F m10-full CI lower bound exceeds 0.50.
  FU results are descriptive. All values are reported whatever the outcome; the paper then uses F as primary for
  these samples and keeps the published values alongside.

Outputs: research/results/px4_log_study/postcrash_audit.md and .json.

    python research/px4_log_study/postcrash_audit.py DATA_ROOT
"""
import json
import math
import os
import sys
from collections import defaultdict
from itertools import product

import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)
import factorial_audit as fa
import r14_audit as r14
from within_drone import rank_test

RESULTS_DIR = os.path.join(SCRIPT_DIR, "..", "results", "px4_log_study")
CLUSTER_SEED = 2029


def within_rows():
    return [json.loads(line) for line in open(os.path.join(RESULTS_DIR, "within_drone_features.jsonl"))]


def ulg_paths(root):
    paths = {}
    for d, _, files in os.walk(root):
        for f in files:
            if f.endswith(".ulg") and not f.startswith("._"):
                paths.setdefault(f[:-4], os.path.join(d, f))
    return paths


def ordering(root, rows):
    """{earlier log_id: precedes | follows | undeterminable} for same-day earlier flights."""
    paths, cache, status = ulg_paths(root), {}, {}
    get = lambda lid: cache.setdefault(lid, r14.utc_start(paths[lid]) if lid in paths else None)
    for r in rows:
        if r["role"] != "earlier" or r["same_day"] != "1":
            continue
        try:
            a, b = get(r["log_id"]), get(r["crash_id"])
        except Exception:
            a = b = None
        status[r["log_id"]] = "undeterminable" if a is None or b is None else ("precedes" if a < b else "follows")
    return status


# ---------------------------------------------------------------- A: rank test

def part_a(rows, drop):
    by = defaultdict(list)
    for r in rows:
        by[r["crash_id"]].append(r)
    rng = np.random.default_rng(0)
    out = {}
    for feat in ("vib_p95", "tune_rms"):
        src = {"vib_p95": "src_vib", "tune_rms": "src_tune"}[feat]
        groups = []
        for cid, fl in by.items():
            crash = [r for r in fl if r["role"] == "crash"]
            if not crash or crash[0]["features"] is None:
                continue
            cf = crash[0]["features"]
            ev = [r["features"] for r in fl if r["role"] == "earlier" and r["log_id"] not in drop
                  and r["features"] is not None and r["features"].get(src) == cf.get(src)]
            groups.append((cf.get(feat), [e.get(feat) for e in ev]))
        n, mr, p, above = rank_test(groups, feat, rng)
        out[feat] = {"n": n, "mean_rank": mr, "p": p, "above_median": above}
    return out


# ---------------------------------------------------------------- B: within-drone Group-CV

def cluster_ci(y, s, clusters):
    rng = np.random.default_rng(CLUSTER_SEED)
    idx = defaultdict(list)
    for i, c in enumerate(clusters):
        idx[c].append(i)
    cids = np.array(sorted(idx))
    vals = []
    for _ in range(2000):
        pick = [i for c in rng.choice(cids, len(cids), replace=True) for i in idx[c]]
        v = fa.auc(y[pick], s[pick])
        if not np.isnan(v):
            vals.append(v)
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def part_b(rows, drop):
    by = defaultdict(list)
    for r in rows:
        if r["features"] is not None and r["log_id"] not in drop:
            by[r["crash_id"]].append(r)
    use = [r for cid in sorted(by) for r in by[cid]
           if any(x["role"] == "crash" for x in by[cid]) and any(x["role"] == "earlier" for x in by[cid])]
    X = np.array([[np.nan if r["features"].get(k) is None else r["features"][k] for k in fa.FEATURES] for r in use], float)
    y = np.array([1 if r["role"] == "crash" else 0 for r in use])
    cl = [r["crash_id"] for r in use]
    m, sd, s = fa.cv_scores(X, y, cl, "group")
    return {"drones": len(set(cl)), "earlier": int((y == 0).sum()), "auc": m, "sd_over_repeats": sd,
            "cluster_ci": cluster_ci(y, s, cl)}


# ---------------------------------------------------------------- C: caliper

def part_c(rows, drop):
    dur = json.load(open(os.path.join(RESULTS_DIR, "feature_window_durations_372.json")))
    by = defaultdict(list)
    for r in rows:
        if r.get("features") is not None and r["log_id"] not in drop:
            by[r["crash_id"]].append(r)
    ok = lambda d: d is not None and not np.isnan(d) and d > 0
    matched, unmatched = [], []
    for cid in sorted(by):
        crash = [f for f in by[cid] if f["role"] == "crash"]
        earlier = [f for f in by[cid] if f["role"] == "earlier"]
        if not crash or not earlier or not ok(dur.get(crash[0]["log_id"])):
            continue
        dc = dur[crash[0]["log_id"]]
        near = [f for f in earlier if ok(dur.get(f["log_id"])) and abs(math.log(dc / dur[f["log_id"]])) <= r14.CALIPER]
        if near:
            matched += [crash[0]] + near
            unmatched += [crash[0]] + earlier
    out = {"airframes": len({r["crash_id"] for r in matched})}
    for name, feats in (("F11", r14.F11), ("F8", r14.F8)):
        Xm, ym, cm = r14.arrays(matched, feats)
        Xu, yu, cu = r14.arrays(unmatched, feats)
        m5, _, sm = fa.cv_scores(Xm, ym, cm, "group")
        u5, _, su = fa.cv_scores(Xu, yu, cu, "group")
        out[name] = {"matched_5": m5, "unmatched_5": u5, "lift_5": m5 - u5,
                     "ci_5": r14.paired_lift_ci(ym, sm, cm, yu, su, cu)}
    out["masking_supported"] = bool(out["F8"]["lift_5"] >= 0.05 and out["F8"]["ci_5"][0] > 0)
    return out


# ---------------------------------------------------------------- D: factorial same-aircraft cells

def part_d(root, drop):
    db = fa.load_index(root)
    sets, vehicle, _ = fa.build_sets(db)
    cache = {}
    for line in open(os.path.join(RESULTS_DIR, "factorial_audit_features.jsonl")):
        r = json.loads(line)
        cache[(r["log_id"], r["is_crash"])] = r["windows"]

    def complete(lid, is_crash):
        w = cache.get((lid, is_crash))
        return bool(w) and all(w.get(f"{m}_{x}") for m, x in product(fa.MARGINS, fa.WINDOWS))

    keep = {True: {x for k in ("C1", "C2") for x in sets[k] if complete(x, True)},
            False: {x for k in ("N1", "N2", "S") for x in sets[k] if complete(x, False) and x not in drop}}
    out = {}
    for m, w in product(fa.MARGINS, fa.WINDOWS):
        c = fa.run_cell(fa.cell_rows(sets, cache, "C2", "S", m, w, keep), vehicle, "group")
        out[f"m{m}_{w}"] = {"n_crash": c["n_crash"], "n_comp": c["n_comp"], "auc": c["auc"],
                           "cluster_ci": cluster_ci(c["_y"], c["_scores"], c["_clusters"])}
    return out


# ---------------------------------------------------------------- main

def run_all(root, rows, drop):
    return {"A": part_a(rows, drop), "B": part_b(rows, drop), "C": part_c(rows, drop), "D": part_d(root, drop)}


def anchors_ok(base):
    a, b, c, d = base["A"], base["B"], base["C"], base["D"]
    return all([a["vib_p95"]["n"] == 61, abs(a["vib_p95"]["mean_rank"] - 0.48) <= 0.01,
                a["tune_rms"]["n"] == 46, abs(a["tune_rms"]["mean_rank"] - 0.50) <= 0.01, abs(b["auc"] - 0.559) <= 0.01,
                c["airframes"] == 36, abs(c["F11"]["lift_5"] - 0.110) <= 0.005, abs(c["F8"]["lift_5"] - 0.077) <= 0.005,
                abs(d["m10_full"]["auc"] - 0.534) <= 0.005])


def main(root):
    rows = within_rows()
    rep = {"declared_in": "research/px4_log_study/postcrash_audit.py docstring"}
    base = run_all(root, rows, set())
    rep["published"] = base
    rep["anchors_pass"] = anchors_ok(base)
    if rep["anchors_pass"]:
        status = ordering(root, rows)
        follows = {k for k, v in status.items() if v == "follows"}
        undet = {k for k, v in status.items() if v == "undeterminable"}
        crash_of = {r["log_id"]: r["crash_id"] for r in rows if r["role"] == "earlier"}
        rep["ordering"] = {"same_day_flights": len(status),
                           "counts": {k: sum(v == k for v in status.values()) for k in ("precedes", "follows", "undeterminable")},
                           "crashes_with_following": len({crash_of[k] for k in follows})}
        rep["F"] = run_all(root, rows, follows)
        rep["FU"] = run_all(root, rows, follows | undet)
        F = rep["F"]
        rep["changed"] = {
            "A_within_drone_warning": bool(min(F["A"]["vib_p95"]["p"], F["A"]["tune_rms"]["p"]) < 0.025),
            "B_signal_detected": bool(F["B"]["cluster_ci"][0] > 0.50),
            "C_masking_supported": F["C"]["masking_supported"],
            "D_same_aircraft_above_chance": bool(F["D"]["m10_full"]["cluster_ci"][0] > 0.50)}
    with open(os.path.join(RESULTS_DIR, "postcrash_audit.json"), "w") as f:
        json.dump(rep, f, indent=1, default=float)
    write_md(rep)


def write_md(rep):
    L = ["# Post-crash flight audit (within-drone samples)", "",
         "Declared in `research/px4_log_study/postcrash_audit.py` (docstring). Exploratory (dagger).", "",
         f"Anchors pass: **{rep['anchors_pass']}**.", ""]
    if rep["anchors_pass"]:
        o = rep["ordering"]
        L += [f"Same-day earlier flights: {o['same_day_flights']}; {o['counts']}; crashes with >= 1 following flight: "
              f"{o['crashes_with_following']}.", "",
              "F = without flights flown after the crash; FU = also without flights with no GPS time.", ""]
    versions = [("Published", rep["published"])] + ([("F", rep["F"]), ("FU", rep["FU"])] if rep["anchors_pass"] else [])
    L += ["## A. Within-drone rank test", "", "| Version | Feature | Drones | Mean rank | One-sided p |", "|---|---|---|---|---|"]
    for name, v in versions:
        for f in ("vib_p95", "tune_rms"):
            a = v["A"][f]
            L.append(f"| {name} | {f} | {a['n']} | {a['mean_rank']:.3f} | {a['p']:.4f} |")
    L += ["", "## B. Within-drone Group-CV model", "", "| Version | Drones | Earlier flights | AUC | Cluster 95% CI |", "|---|---|---|---|---|"]
    for name, v in versions:
        b = v["B"]
        L.append(f"| {name} | {b['drones']} | {b['earlier']} | {b['auc']:.3f} | [{b['cluster_ci'][0]:.3f}, {b['cluster_ci'][1]:.3f}] |")
    L += ["", "## C. Caliper 0.25 lift", "", "| Version | Airframes | Features | Matched | Unmatched | Lift | Paired 95% CI |", "|---|---|---|---|---|---|---|"]
    for name, v in versions:
        c = v["C"]
        for k in ("F11", "F8"):
            L.append(f"| {name} | {c['airframes']} | {k} | {c[k]['matched_5']:.3f} | {c[k]['unmatched_5']:.3f} | "
                     f"{c[k]['lift_5']:+.3f} | [{c[k]['ci_5'][0]:+.3f}, {c[k]['ci_5'][1]:+.3f}] |")
    L += ["", "## D. Factorial same-aircraft cells (grouped CV, constant subset)", "",
          "| Version | Cell | Crashes | Earlier flights | AUC | Cluster 95% CI |", "|---|---|---|---|---|---|"]
    for name, v in versions:
        for k, d in v["D"].items():
            L.append(f"| {name} | {k} | {d['n_crash']} | {d['n_comp']} | {d['auc']:.3f} | [{d['cluster_ci'][0]:.3f}, {d['cluster_ci'][1]:.3f}] |")
    if rep["anchors_pass"]:
        L += ["", "## Declared decisions (F version)", "", *[f"- {k}: **{v}**" for k, v in rep["changed"].items()]]
    open(os.path.join(RESULTS_DIR, "postcrash_audit.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/Volumes/One Touch/AeroFleet_px4_data")
