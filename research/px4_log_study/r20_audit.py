"""Round 20 audit: grouped folds for the injected-fault control, attribution on multicopters only, a site-weighted
between-drone test, a check of the screening flag rates, and a pseudo crash moment for normal flights.

PRE-DECLARED (committed and pushed before this script is run). Status: exploratory (dagger), declared after the
twentieth internal review; not blind: every earlier result is known, including the undeclared one-set-per-site check
(median p 0.14) and the four-day RflyMAD check (0.82).

PART A - Injected-fault control with grouped folds (review problem 2)
  Data: rflymad_scores.jsonl exactly as rflymad_eval.analyze (488 flights; same pseudo-onsets; 11 features; windows
  pre / fault / whole). Model: factorial_audit.fit_predict, seeds 42-46. Folds grouped (factorial_audit.cv_scores
  scheme "group") by (A1) flight date, from the log file name, and (A2) flight pattern (acce, circling, hover, velocity,
  waypoint). For each: AUC per window, 200 refitting label permutations with the same grouping (seed 2130) for p, and
  the paired bootstrap of fault - pre (2,000, seed 2131).
  Wording rule: the paper says the pre-fault separation "survives grouping by day" if the A1 pre-window permutation
  p < 0.05, otherwise that it "may reflect session identity". Either way the abstract states that the separation is
  specific to flight-style features (FlightMD's score did not show it).

PART B - Pilot or aircraft on multicopters only (review problem 3)
  B1 The declared rule (pilot_vs_drone verdicts as stored; "unknown" counted wrong) on multicopter crashes (index
     mav_type Quadrotor/Hexarotor/Octorotor): balanced accuracy on the held-out crashes (holdout.jsonl) and on the
     modelled multicopter crashes, bootstrap intervals (2,000, seed 2132).
  B2 Task B models exactly as r15_audit.part_a (logistic and depth-3 tree, stratified 5-fold x seeds 0-4, 200 refitting
     permutations, seed 2133) on the 108 modelled multicopter crashes at every margin; per cell AUC, null SD, p, and
     approximate bounds; detectable AUC at 80% power = 0.5 + 2.80 x null SD (logistic, m = 0).
  Wording rule: the abstract's "near chance" is kept for multicopters if no B2 cell has p < 0.05 after Holm over the
  12 cells and the B1 held-out balanced accuracy is below 0.70; otherwise the abstract reports the multicopter result
  separately.

PART C - Site-weighted between-drone test (review problem 4)
  Sets and ranks as r15_audit.set_table; sites as operator_cluster (first 3D GPS fix, 2 km, airframes without a fix are
  their own site). Statistic: average the scaled ranks of the sets of each case site, then average over case sites
  (each site weight 1). Null: each set's rank drawn uniformly from its exact discrete null (k/(n) for k = 0..n with n
  controls), same site averaging; 100,000 draws, seed 2134; one-sided p. Also the airframe-level p (r15 B3, 0.012) for
  reference.
  Wording rule (fixed now): this site-weighted test is the primary dependence-aware test. The between-drone result is
  "supported" if p < 0.025 and the Holm-adjusted p (same seven tests as r15 B5) < 0.05; "suggestive" if p < 0.10;
  otherwise "not supported once sites are weighted equally". The abstract reports the airframe-level and the
  site-weighted p.

PART D - Screening flag rates (review problem 4)
  On screening_reference_features.jsonl with the same strata, halves and thresholds as screening_reference.analyze:
  D1 the in-sample flag rate (thresholds applied to the half that set them) beside the out-of-sample one, per nominal
     rate; D2 the bootstrap distribution of the out-of-sample 10% flag rate (median, 2.5 and 97.5 percentiles) next to
     the point estimate; D3 leave-one-out thresholds (each reference drone flagged against the other drones of its
     stratum, pooled by source if < 4 others; cases against all drones of their stratum): flag rate, sensitivity and
     lift at the nominal 10%, with a bootstrap interval (2,000, seed 2135). Descriptive; no wording rule beyond
     reporting D3 beside the half-split result.

PART E - Pseudo crash moment for normal flights (review problem 8)
  Normal flights (leak_curve_features.jsonl, group normal) get t_c = touchdown: the first land-detector "landed" sample
  after the last airborne sample of the armed period (end of armed period if none). Their 11 features are recomputed
  (leak_curve.window_features, older-firmware fallbacks as factorial_audit.window_set) on [take-off, t_c - m] for
  m = 0 and 10 s; crash rows are unchanged. Then r19_audit.leak_with_drop on the constant cohort for all crashes and the
  tilt-defined multicopter crashes (seed 2136). A normal flight whose new window is shorter than 10 s leaves the cohort
  (counted). Reported beside the published drops (0.035 and 0.114).

Outputs: research/results/px4_log_study/r20_audit.md and .json.

    python research/px4_log_study/r20_audit.py DATA_ROOT
"""
import gzip
import json
import os
import re
import sys
from collections import Counter, defaultdict

import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)
import factorial_audit as fa
import operator_cluster as oc
import postcrash_audit as pca
import r15_audit as r15
import r19_audit as r19
import sensitivity
from r16_audit import crash_status

RESULTS_DIR = os.path.join(SCRIPT_DIR, "..", "results", "px4_log_study")
MULTI = ("Quadrotor", "Hexarotor", "Octorotor")
MARGINS = (0, 2, 5, 10, 20, 30)


def jsonl(name):
    return [json.loads(l) for l in open(os.path.join(RESULTS_DIR, name))]


def boot(n, stat, seed, B=2000):
    rng = np.random.default_rng(seed)
    v = [stat(rng.integers(0, n, n)) for _ in range(B)]
    v = [x for x in v if x == x]
    return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]


def ba(y, v):
    y, v = np.asarray(y), np.asarray(v)
    if not ((y == 0).any() and (y == 1).any()):
        return np.nan
    return float((np.mean(v[y == 1] == 1) + np.mean(v[y == 0] == 0)) / 2)


# ---------------------------------------------------------------- A

def part_a():
    R = [json.loads(l) for l in open(os.path.join(RESULTS_DIR, "rflymad_scores.jsonl"))]
    keep = [r for r in R if "error" not in r and not (r["cls"] != "no_fault" and r["t_f"] is None)
            and not (r["cls"] == "no_fault" and r["t_f"] is not None)]
    off = defaultdict(list)
    for r in keep:
        if r["t_f"] is not None:
            off[r["status"]].append((r["t_f"] - r["t0"]) / 1e6)
    allo = [x for v in off.values() for x in v]
    for r in keep:
        if r["t_f"] is None:
            s = min(max(int(round(np.median(off.get(r["status"]) or allo))), 10), 120)
            for w, g in (("pre", s), ("fault", min(s + 10, 120))):
                if f"g{g}" in r["feat"]:
                    r["feat"][w] = r["feat"][f"g{g}"]
    rs = [r for r in keep if all(w in r["feat"] for w in ("pre", "fault", "whole"))]
    y = np.array([0 if r["cls"] == "no_fault" else 1 for r in rs])
    date = lambda r: re.search(r"log_\d+_(\d{4}-\d+-\d+)", r["path"]).group(1)
    out = {"n": len(rs), "n_fault": int(y.sum())}
    for gname, gfn in (("date", date), ("pattern", lambda r: r["status"])):
        groups = [gfn(r) for r in rs]
        res, sc = {"n_groups": len(set(groups)), "groups_with_nofault": len({g for g, t in zip(groups, y) if t == 0})}, {}
        for w in ("pre", "fault", "whole"):
            X = np.array([[np.nan if r["feat"][w][f] is None else r["feat"][w][f] for f in fa.FEATURES] for r in rs], float)
            a, sd, s = fa.cv_scores(X, y, groups, "group")
            sc[w] = s
            rng = np.random.default_rng(2130)
            null = [fa.cv_scores(X, rng.permutation(y), groups, "group", seeds=(42,))[0] for _ in range(200)]
            res[w] = {"auc": a, "perm_p": float((np.sum(np.array(null) >= a) + 1) / 201), "null_sd": float(np.std(null))}
        res["fault_minus_pre"] = res["fault"]["auc"] - res["pre"]["auc"]
        res["fault_minus_pre_ci"] = boot(len(y), lambda b: fa.auc(y[b], sc["fault"][b]) - fa.auc(y[b], sc["pre"][b]), 2131)
        out[gname] = res
        print("A", gname, res["pre"], flush=True)
    out["wording"] = "survives grouping by day" if out["date"]["pre"]["perm_p"] < 0.05 else "may reflect session identity"
    return out


# ---------------------------------------------------------------- B

def part_b(db):
    mc = lambda lid: db.get(lid, {}).get("mav_type") in MULTI
    out = {}
    for name in ("holdout.jsonl", "pilot_vs_drone.jsonl"):
        rows = [r for r in jsonl(name) if r.get("label") in ("pilot", "drone") and mc(r["log_id"])]
        y = np.array([1 if r["label"] == "drone" else 0 for r in rows])
        v = np.array([1 if r["verdict"] == "drone" else (0 if r["verdict"] == "pilot" else -1) for r in rows])
        out[f"B1_rule_{name.split('.')[0]}"] = {"n": len(rows), "n_pilot": int((y == 0).sum()), "ba": ba(y, v),
                                                "ci": boot(len(y), lambda b: ba(y[b], v[b]), 2132)}
    rows = [r for r in jsonl("leak_curve_features.jsonl") if r["group"] == "crash" and r["label"] in ("pilot", "drone")
            and mc(r["log"])]
    mod = {r["log"] for r in jsonl("leak_curve_features.jsonl") if r["group"] == "crash" and r["margin"] == 0}
    out["B1_rule_modelled_multicopters"] = None
    pv = {r["log_id"]: r for n in ("holdout.jsonl", "pilot_vs_drone.jsonl") for r in jsonl(n)}
    mm = [pv[l] for l in sorted(mod) if l in pv and mc(l) and pv[l].get("label") in ("pilot", "drone")]
    if mm:
        y = np.array([1 if r["label"] == "drone" else 0 for r in mm])
        v = np.array([1 if r["verdict"] == "drone" else (0 if r["verdict"] == "pilot" else -1) for r in mm])
        out["B1_rule_modelled_multicopters"] = {"n": len(mm), "n_pilot": int((y == 0).sum()), "ba": ba(y, v),
                                                "ci": boot(len(y), lambda b: ba(y[b], v[b]), 2132)}
    rng = np.random.default_rng(2133)
    cells = {}
    for model in ("logistic", "tree"):
        for m in MARGINS:
            R = [r for r in rows if r["margin"] == m]
            X = np.array([[r[f] for f in fa.FEATURES] for r in R], float)
            y = np.array([1 if r["label"] == "drone" else 0 for r in R])
            obs, _ = r15.cv_auc(X, y, model)
            null = np.array([r15.cv_auc(X, rng.permutation(y), model)[0] for _ in range(200)])
            sd = float(null.std())
            cells[f"{model}|{m}"] = {"n": len(y), "n_pilot": int((y == 0).sum()), "auc": obs, "null_sd": sd,
                                     "p": float((np.sum(null >= obs) + 1) / 201), "bounds": [obs - 1.96 * sd, obs + 1.96 * sd]}
            print("B", model, m, round(obs, 3), flush=True)
    ps = sorted(cells, key=lambda k: cells[k]["p"])
    run = 0.0
    for i, k in enumerate(ps):
        run = max(run, min(1.0, (len(ps) - i) * cells[k]["p"]))
        cells[k]["holm"] = run
    out["B2_cells"] = cells
    out["B2_detectable_auc_80"] = 0.5 + 2.80 * cells["logistic|0"]["null_sd"]
    held = out["B1_rule_holdout"]["ba"]
    out["wording_near_chance_holds"] = bool(all(c["holm"] >= 0.05 for c in cells.values()) and held < 0.70)
    return out


# ---------------------------------------------------------------- C

def part_c(root):
    T = r15.set_table()
    sets, _ = sensitivity.load_between()
    paths = pca.ulg_paths(root)
    logs = defaultdict(list)
    for sid in sets:
        for v, rs in sets[sid].items():
            logs[v] += [r["log_id"] for r in rs]
    cases = sorted({t["case"] for t in T})
    loc = {}
    for v in sorted({t["case"] for t in T} | {c for t in T for c, _ in t["ctrl"]}):
        loc[v] = None
        for lid in dict.fromkeys(logs[v]):
            if lid in paths:
                loc[v] = oc.home(paths[lid])
                if loc[v] is not None:
                    break
    cl = oc.clusters(loc, 2.0)
    by_site = defaultdict(list)
    for t in T:
        by_site[cl[t["case"]]].append(t)
    sites = sorted(by_site)
    stat = lambda ranks_by_site: float(np.mean([np.mean(r) for r in ranks_by_site]))
    obs = stat([[oc.rank(t) for t in by_site[s]] for s in sites])
    rng = np.random.default_rng(2134)
    D = 100_000
    acc = np.zeros(D)
    for s in sites:
        site_sum = np.zeros(D)
        for t in by_site[s]:
            n = len(t["ctrl"])
            site_sum += rng.integers(0, n + 1, D) / n
        acc += site_sum / len(by_site[s])
    null = acc / len(sites)
    p = float(np.mean(null >= obs))
    pv = {"between_vib": p, "protections": 0.63, "clipping": 0.045, "manual": 0.165, "within_vib": 0.67,
          "within_track": 0.47, "between_track": 0.15}
    order, holm, run = sorted(pv, key=pv.get), {}, 0.0
    for i, k in enumerate(order):
        run = max(run, min(1.0, (len(order) - i) * pv[k]))
        holm[k] = run
    wording = ("supported" if p < 0.025 and holm["between_vib"] < 0.05 else
               "suggestive" if p < 0.10 else "not supported once sites are weighted equally")
    return {"case_sites": len(sites), "sets": len(T), "site_weighted_mean_rank": obs, "p": p,
            "holm": holm["between_vib"], "airframe_level_p_r15": 0.012, "wording": wording}


# ---------------------------------------------------------------- D

def part_d(root):
    import screening_reference as sr
    F = {r["log_id"]: r["features"] for r in jsonl("screening_reference_features.jsonl")}
    import csv
    ref = list(csv.DictReader(open(sr.REF_CSV)))
    idx = {x["log_id"]: x for x in sr.index(root)}
    C = sr.cases()
    by_drone = defaultdict(list)
    for r in ref:
        by_drone[(r["stratum"], r["vehicle"])].append(r["log_id"])

    def ref_value(lg, src):
        v = [F[l]["vib_p95"] for l in lg if F.get(l) and F[l].get("vib_p95") is not None and F[l].get("src_vib") == src]
        return float(np.median(v)) if len(v) >= 2 else None

    case_rows = [{"stratum": "|".join((idx[lid]["sys_hw"], sr.vkey(idx[lid]), idx[lid]["mav_type"])), "src": src, "val": val}
                 for v, val, src, lid, sid in C]
    keys = sorted({(c["stratum"], c["src"]) for c in case_rows})
    refvals = {k: [] for k in keys}
    for (st, v), lg in sorted(by_drone.items()):
        for k in keys:
            if k[0] == st:
                rv = ref_value(lg, k[1])
                if rv is not None:
                    refvals[k].append(rv)
    rng = np.random.default_rng(2122)
    halves = {}
    for k, vals in refvals.items():
        perm = rng.permutation(len(vals))
        halves[k] = ([vals[i] for i in perm[: len(vals) // 2]], [vals[i] for i in perm[len(vals) // 2:]])

    def thresholds(fit):
        by_src = defaultdict(list)
        for k, v in fit.items():
            by_src[k[1]] += v
        return {k: {r: (float(np.percentile(fit[k] if len(fit[k]) >= 4 else by_src[k[1]], p))
                        if (fit[k] if len(fit[k]) >= 4 else by_src[k[1]]) else np.inf) for r, p in sr.PCTS.items()}
                for k in keys}

    out = {"D1": {}}
    for tag, (fi, te) in (("A_to_B", (0, 1)), ("B_to_A", (1, 0))):
        fit = {k: h[fi] for k, h in halves.items()}
        test = {k: h[te] for k, h in halves.items()}
        thr = thresholds(fit)
        out["D1"][tag] = {r: {"in_sample": float(np.mean([x > thr[k][r] for k in keys for x in fit[k]])),
                              "out_of_sample": float(np.mean([x > thr[k][r] for k in keys for x in test[k]]))} for r in sr.PCTS}
    rb = np.random.default_rng(2123)
    fr = []
    for _ in range(2000):
        e = []
        for fi, te in ((0, 1), (1, 0)):
            fit = {k: [halves[k][fi][i] for i in rb.integers(0, len(halves[k][fi]), len(halves[k][fi]))] if halves[k][fi] else [] for k in keys}
            test = {k: [halves[k][te][i] for i in rb.integers(0, len(halves[k][te]), len(halves[k][te]))] if halves[k][te] else [] for k in keys}
            thr = thresholds(fit)
            e.append(np.mean([x > thr[k][10] for k in keys for x in test[k]]))
        fr.append(np.mean(e))
    out["D2_flag10_bootstrap"] = {"median": float(np.median(fr)), "p2_5": float(np.percentile(fr, 2.5)),
                                  "p97_5": float(np.percentile(fr, 97.5))}

    def loo(refv, cases_):
        by_src = defaultdict(list)
        for k, v in refv.items():
            by_src[k[1]] += [(k, i, x) for i, x in enumerate(v)]
        flags = []
        for k, v in refv.items():
            for i, x in enumerate(v):
                others = [z for j, z in enumerate(v) if j != i]
                if len(others) < 4:
                    others = [z for (kk, j, z) in by_src[k[1]] if not (kk == k and j == i)]
                if others:
                    flags.append(x > np.percentile(others, 90))
        f = float(np.mean(flags))
        s = float(np.mean([c["val"] > np.percentile(refv[(c["stratum"], c["src"])] if len(refv[(c["stratum"], c["src"])]) >= 4
                                                    else [z for (_, _, z) in by_src[c["src"]]], 90) for c in cases_]))
        pi = sr.PI["fleet"]
        ppv = s * pi / (s * pi + f * (1 - pi))
        return f, s, ppv / pi

    f, s, lift = loo(refvals, case_rows)
    rb = np.random.default_rng(2135)
    bl = []
    for _ in range(2000):
        cs = [case_rows[i] for i in rb.integers(0, len(case_rows), len(case_rows))]
        rv = {k: [v[i] for i in rb.integers(0, len(v), len(v))] if v else [] for k, v in refvals.items()}
        bl.append(loo(rv, cs))
    bl = np.array(bl)
    out["D3_leave_one_out_10"] = {"flag_rate": f, "sensitivity": s, "lift": lift,
                                  "ci": {n: [float(np.percentile(bl[:, i], 2.5)), float(np.percentile(bl[:, i], 97.5))]
                                         for i, n in enumerate(("flag_rate", "sensitivity", "lift"))}}
    return out


# ---------------------------------------------------------------- E

def touchdown_features(path):
    from pyulog import ULog
    from leak_curve import TOPICS, window_features
    from pilot_vs_drone import armed_period, between, topic

    u = ULog(path, message_name_filter_list=TOPICS + ["estimator_status"])
    st = topic(u, "vehicle_status")
    per = armed_period(st) if st is not None else None
    if per is None:
        return None
    t_arm, t_end = per
    rotary = bool(st["is_rotary_wing"][-1]) if "is_rotary_wing" in st else True
    land = topic(u, "vehicle_land_detected")
    t0, t_c = t_arm, t_end
    if land is not None:
        m = between(land, t_arm, t_end)
        ts, landed = land["timestamp"][m], land["landed"][m]
        air = np.where(landed == 0)[0]
        if len(air):
            t0 = ts[air[0]]
            after = np.where((ts > ts[air[-1]]) & (landed == 1))[0]
            if len(after):
                t_c = ts[after[0]]
    out = {}
    es, sp, att = topic(u, "estimator_status"), topic(u, "vehicle_rates_setpoint"), topic(u, "vehicle_attitude")
    for mg in (0, 10):
        b = t_c - mg * 1e6
        if b - t0 < 10e6:
            out[mg] = None
            continue
        f = window_features(u, st, rotary, t0, b)
        if np.isnan(f["vib_p95"]) and es is not None and "vibe[1]" in es:
            mm = between(es, t0, b)
            if mm.any():
                f["vib_p95"] = float(np.percentile(es["vibe[1]"][mm], 95))
        if rotary and np.isnan(f["tune_rms"]) and sp is not None and att is not None and "roll" in sp and "rollspeed" in att:
            mm = between(att, t0, b)
            if mm.sum() > 20:
                tt = att["timestamp"][mm]
                err = [np.interp(tt, sp["timestamp"], sp[k]) - att[a][mm] for k, a in (("roll", "rollspeed"), ("pitch", "pitchspeed"))]
                f["tune_rms"] = float(np.sqrt(np.mean(np.square(err))))
        out[mg] = {k: (None if f[k] is None or np.isnan(f[k]) else float(f[k])) for k in fa.FEATURES}
    return out


def part_e(root, db):
    paths = pca.ulg_paths(root)
    leak = jsonl("leak_curve_features.jsonl")
    normals = sorted({r["log"] for r in leak if r["group"] == "normal"})
    new = {}
    for l in normals:
        try:
            new[l] = touchdown_features(paths[l]) if l in paths else None
        except Exception:
            new[l] = None
    rows, dropped = [], set()
    for r in leak:
        if r["group"] == "normal" and r["margin"] in (0, 10):
            nf = (new.get(r["log"]) or {}).get(r["margin"])
            if nf is None:
                dropped.add(r["log"])
                continue
            rows.append({**r, **nf})
        else:
            rows.append(r)
    veh = lambda lid: db.get(lid, {}).get("vehicle_uuid") or lid
    crash148 = sorted({r["log"] for r in leak if r["group"] == "crash"})
    status = crash_status(pca.ulg_paths(root), crash148)
    tm = {l for l in crash148 if status.get(l) in ("confirmed", "tilt_unconfirmed") and db.get(l, {}).get("mav_type") in MULTI}
    out = {"normals_dropped": len(dropped)}
    out["all"] = r19.leak_with_drop(rows, veh, set(crash148), fa.FEATURES, seed=2136)
    out["tilt_multicopter"] = r19.leak_with_drop(rows, veh, tm, fa.FEATURES, seed=2136)
    out["published"] = {"all": 0.035, "tilt_multicopter": 0.114}
    return out


def main(root):
    raw = open(os.path.join(root, "dbinfo.json"), "rb").read()
    db = {x["log_id"]: x for x in json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)}
    rep = {"declared_in": "research/px4_log_study/r20_audit.py docstring"}
    for name, fn in (("A", part_a), ("B", lambda: part_b(db)), ("C", lambda: part_c(root)), ("D", lambda: part_d(root)),
                     ("E", lambda: part_e(root, db))):
        try:
            rep[name] = fn()
        except Exception as e:
            rep[name] = f"not run: {type(e).__name__}: {e}"
        print("done", name, flush=True)
        json.dump(rep, open(os.path.join(RESULTS_DIR, "r20_audit.json"), "w"), indent=1, default=float)
    open(os.path.join(RESULTS_DIR, "r20_audit.md"), "w").write(
        "# Round 20 audit\n\nDeclared in `research/px4_log_study/r20_audit.py`. Exploratory (dagger).\n\n```\n"
        + json.dumps(rep, indent=1, default=float) + "\n```\n")
    print(json.dumps(rep, indent=1, default=float))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/Volumes/One Touch/AeroFleet_px4_data")
