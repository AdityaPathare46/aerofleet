"""Operator clustering for the between-drone vibration test (review item open since Round 6).

PRE-DECLARED (committed and pushed before this script is run). Status: exploratory (dagger). Known before declaring:
the published clustered result (two-stage bootstrap over airframes, r15_audit B3: mean rank 0.66, p 0.012, Holm 0.08).

WHY: controls from the same operator are not independent, and a case and its controls may share an operator. The
archive records no operator, so we use a proxy: where the aircraft flies. Each airframe's home location is the first
3D GPS fix (vehicle_gps_position, fix_type >= 3, lat/lon not zero) in any of its analysed logs, in log order.
Airframes are linked if their home locations are within R = 2 km (haversine); operator clusters are the connected
components (single linkage). An airframe with no GPS fix is its own cluster. Coordinates are used in memory only and
never written to any output; outputs contain cluster sizes and counts only.

DATA: the analysed matched sets exactly as r15_audit.set_table (60 sets, vib_p95, same measurement source).

O1 Description: number of clusters; airframes per cluster (case, control); airframes without a fix; sets in which the
   case shares a cluster with at least one of its controls; clusters holding more than one case airframe.
O2 Operator-clustered two-stage bootstrap (2,000 resamples, seed 2110): resample case clusters with replacement (each
   brings all sets of all its case airframes) and control clusters with replacement (a control cluster drawn k times
   gives weight k to every control airframe in it, in every set); mean scaled rank as r15_audit B3; null-shifted
   one-sided p = share of resamples with (b - rbar + 0.5) >= rbar; percentile 95% interval. Holm-adjusted p over the
   same seven tests as r15_audit B5, with this p in place of the airframe-clustered one.
O3 Sets where the case shares a cluster with a control removed: mean rank and exact-null p (sensitivity.null_p,
   10,000 draws, seed 2111), number of sets.
O4 One set per case cluster: 1,000 random choices (seed 2112); median mean rank, median exact p, share p < 0.025.
O5 Sensitivity of O2 to the radius: R = 0.5 km and R = 10 km (seeds 2113, 2114).
WORDING RULE (fixed now): the paper says the between-drone result "survives operator clustering" if O2 p < 0.025, and
"weakens under operator clustering" otherwise; the Holm-adjusted value is reported either way, and the overall
description (suggestive, not supported) changes only if O2's Holm-adjusted p < 0.05 (to "supported") or O2 p >= 0.05
(to "not supported once operators are clustered").
Limits stated in the output: location is a proxy; one operator can fly at several sites and several operators at one
site; logs without GPS (indoor or older firmware) cannot be placed.

    python research/px4_log_study/operator_cluster.py DATA_ROOT
"""
import json
import math
import os
import sys
from collections import Counter, defaultdict

import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)
import postcrash_audit as pca
import r15_audit as r15
import sensitivity

RESULTS_DIR = os.path.join(SCRIPT_DIR, "..", "results", "px4_log_study")


def home(path):
    from pyulog import ULog
    try:
        u = ULog(path, message_name_filter_list=["vehicle_gps_position", "sensor_gps"])
    except Exception:
        return None
    for d in u.data_list:
        g = d.data
        lat, lon = g.get("lat"), g.get("lon")
        fix = g.get("fix_type")
        if lat is None or lon is None:
            continue
        ok = (lat != 0) & (lon != 0) & ((fix >= 3) if fix is not None else True)
        if ok.any():
            i = int(np.argmax(ok))
            scale = 1e7 if abs(lat[i]) > 1000 else 1.0
            return float(lat[i]) / scale, float(lon[i]) / scale
    return None


def dist_km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 12742.0 * math.asin(math.sqrt(h))


def clusters(loc, R):
    ids = sorted(loc)
    parent = {i: i for i in ids}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    placed = [i for i in ids if loc[i] is not None]
    for a in range(len(placed)):
        for b in range(a + 1, len(placed)):
            if dist_km(loc[placed[a]], loc[placed[b]]) <= R:
                parent[find(placed[a])] = find(placed[b])
    return {i: find(i) for i in ids}


def rank(t, w=None):
    return (sum((w.get(c, 0) if w else 1) for c, x in t["ctrl"] if x < t["val"]) /
            sum((w.get(c, 0) if w else 1) for c, _ in t["ctrl"]))


def clustered_boot(T, cl, seed):
    rbar = float(np.mean([rank(t) for t in T]))
    case_cl, ctrl_cl = defaultdict(list), defaultdict(set)
    for t in T:
        case_cl[cl[t["case"]]].append(t)
        for c, _ in t["ctrl"]:
            ctrl_cl[cl[c]].add(c)
    ck, kk = sorted(case_cl), sorted(ctrl_cl)
    rng = np.random.default_rng(seed)
    b = []
    for _ in range(2000):
        w = defaultdict(int)
        for k in rng.choice(kk, len(kk)):
            for c in ctrl_cl[k]:
                w[c] += 1
        rk = [rank(t, w) for k in rng.choice(ck, len(ck)) for t in case_cl[k] if sum(w.get(c, 0) for c, _ in t["ctrl"])]
        if rk:
            b.append(np.mean(rk))
    b = np.array(b)
    return {"rbar": rbar, "mean": float(b.mean()), "ci": [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))],
            "p": float(np.mean(b - rbar + 0.5 >= rbar)), "case_clusters": len(ck), "control_clusters": len(kk)}


def main(root):
    T = r15.set_table()
    sets, _ = sensitivity.load_between()
    paths = pca.ulg_paths(root)
    logs = defaultdict(list)
    for sid in sets:
        for v, rs in sets[sid].items():
            logs[v] += [r["log_id"] for r in rs]
    airframes = sorted({t["case"] for t in T} | {c for t in T for c, _ in t["ctrl"]})
    loc = {}
    for v in airframes:
        loc[v] = None
        for lid in dict.fromkeys(logs[v]):
            if lid in paths:
                loc[v] = home(paths[lid])
                if loc[v] is not None:
                    break
    out = {"declared_in": "research/px4_log_study/operator_cluster.py docstring", "n_sets": len(T),
           "n_airframes": len(airframes), "no_gps_fix": sum(loc[v] is None for v in airframes)}
    cl = clusters(loc, 2.0)
    cases = {t["case"] for t in T}
    members = defaultdict(lambda: [0, 0])
    for v in airframes:
        members[cl[v]][0 if v in cases else 1] += 1
    shared = [t for t in T if any(cl[c] == cl[t["case"]] for c, _ in t["ctrl"])]
    out["O1"] = {"clusters": len(members), "size_hist": dict(sorted(Counter(sum(m) for m in members.values()).items())),
                 "clusters_with_2plus_cases": sum(m[0] >= 2 for m in members.values()),
                 "sets_case_shares_cluster_with_control": len(shared)}
    out["O2"] = clustered_boot(T, cl, 2110)
    p = out["O2"]["p"]
    pv = {"between_vib": p, "protections": 0.63, "clipping": 0.045, "manual": 0.165, "within_vib": 0.67,
          "within_track": 0.47, "between_track": 0.15}
    order, holm, run = sorted(pv, key=pv.get), {}, 0.0
    for i, k in enumerate(order):
        run = max(run, min(1.0, (len(order) - i) * pv[k]))
        holm[k] = run
    out["O2"]["holm"] = holm["between_vib"]
    keep = [t for t in T if t not in shared]
    if keep:
        o, pk, _ = sensitivity.null_p([rank(t) for t in keep], [len(t["ctrl"]) for t in keep], draws=10_000, seed=2111)
        out["O3"] = {"sets": len(keep), "mean_rank": o, "p": pk}
    by = defaultdict(list)
    for t in T:
        by[cl[t["case"]]].append(t)
    rng = np.random.default_rng(2112)
    mr, ps = [], []
    for _ in range(1000):
        pick = [by[k][rng.integers(len(by[k]))] for k in sorted(by)]
        o, pk, _ = sensitivity.null_p([rank(t) for t in pick], [len(t["ctrl"]) for t in pick], draws=10_000,
                                      seed=int(rng.integers(1 << 31)))
        mr.append(o)
        ps.append(pk)
    out["O4"] = {"sets": len(by), "median_mean_rank": float(np.median(mr)), "median_p": float(np.median(ps)),
                 "share_p_below_0025": float(np.mean(np.array(ps) < 0.025))}
    out["O5"] = {f"R{R}km": clustered_boot(T, clusters(loc, R), s) for R, s in ((0.5, 2113), (10.0, 2114))}
    out["wording"] = {"survives_operator_clustering": p < 0.025,
                      "overall": ("supported" if holm["between_vib"] < 0.05 else
                                  "not supported once operators are clustered" if p >= 0.05 else "suggestive")}
    out["limits"] = ("location is a proxy for operator; one operator may fly at several sites and several operators at "
                     "one site; airframes without a GPS fix are their own cluster")
    json.dump(out, open(os.path.join(RESULTS_DIR, "operator_cluster.json"), "w"), indent=1, default=float)
    open(os.path.join(RESULTS_DIR, "operator_cluster.md"), "w").write(
        "# Operator clustering (location proxy)\n\nDeclared in `research/px4_log_study/operator_cluster.py`.\n\n```\n"
        + json.dumps(out, indent=1, default=float) + "\n```\n")
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/Volumes/One Touch/AeroFleet_px4_data")
