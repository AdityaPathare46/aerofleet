"""Screening reference rebuilt from non-crash drones per stratum (review item A5, open since Round 13).

PRE-DECLARED (committed and pushed before any reference log is downloaded or scored). Status: exploratory (dagger).
Known before declaring: the published screening numbers, which rank each crashed drone against its 1-2 matched controls
(107 controls in the strata, 17 reused) and ASSUME a 5/10/25% flag rate among non-crash drones instead of measuring it.

CASES: the crashed drones of the 60 analysed between-drone sets (r15_audit.set_table): the case value is the median
vib_p95 over its flights from one measurement source (the first source with >= 2 values, as set_table), and its
stratum is (sys_hw, PX4 major.minor, mav_type) of the case log, plus that measurement source.
REFERENCE: for each such stratum, every vehicle in the archive index with no crash-rated log, real hardware, and >= 3
flights of >= 30 s whose first such flight is in the stratum (rough_drone_test.select's pool), at most 40 per stratum
drawn at random (seed 2120), 3 of its flights drawn at random (seed 2121). Earlier matched controls are eligible like
any other vehicle. Features: within_drone.features (as rough_drone_test.analyze); a reference drone's value is the
median vib_p95 over its flights from the case's measurement source, used only with >= 2 such flights.

SPLIT: within each stratum, reference drones are split at random into halves A and B (seed 2122).
THRESHOLDS fixed on half A: per stratum, the 75th, 90th and 95th percentiles (linear interpolation) of half-A values,
nominal flag rates 25%, 10%, 5%. A stratum with fewer than 4 half-A drones uses the pooled half-A values of all strata
with the same measurement source instead (counted and reported).
MEASURED on half B and on the cases:
  S1 realised flag rate: share of half-B drones above their stratum's threshold (pooled over strata, weighted by
     drones), per nominal rate.
  S2 sensitivity: share of the 60 case drones above their stratum's threshold.
  S3 exact Bayes PPV = s*pi / (s*pi + f*(1-pi)) with s = S2, f = S1, pi = 0.741% (fleet) and 0.689% (screenable);
     lift = PPV/pi; inspections per detected crash = 1/PPV.
  S4 AUC of case values against half-B values within stratum (mean percentile of each case among its stratum's
     half-B drones).
  Then the halves are swapped (thresholds on B, measured on A) and both results are reported with their mean.
INTERVALS: 2,000 bootstrap resamples (seed 2123) of case drones and, within each stratum, of reference drones (both
halves), thresholds re-fitted in every resample; percentile 95% intervals for S1-S4.
WORDING RULES (fixed now): the paper replaces the assumed-flag-rate PPVs with the measured ones. It describes vibration
screening as a "useful inspection ranking" only if, at the nominal 10% operating point, the mean lift is >= 2 with an
interval lower bound > 1; otherwise as "not shown to beat random inspection" (lower bound <= 1).
Limits stated in the output: "no crash-rated log" does not mean the drone never crashed; reference drones are those
with >= 3 flights in the archive; strata are those of the 60 sets only.

    python research/px4_log_study/screening_reference.py select DATA_ROOT     (writes the reference list; no outcomes)
    python research/px4_log_study/screening_reference.py sizes DATA_ROOT      (HEAD requests: download size)
    python research/px4_log_study/screening_reference.py fetch DATA_ROOT
    python research/px4_log_study/screening_reference.py analyze DATA_ROOT
"""
import csv
import gzip
import json
import os
import random
import sys
import urllib.request
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)
import postcrash_audit as pca
import r15_audit as r15
import sensitivity

RESULTS_DIR = os.path.join(SCRIPT_DIR, "..", "results", "px4_log_study")
REF_CSV = os.path.join(RESULTS_DIR, "screening_reference_sets.csv")
FEATS = os.path.join(RESULTS_DIR, "screening_reference_features.jsonl")
CRASH = ("crash_sw_hw", "crash_pilot")
CAP, PCTS = 40, {25: 75, 10: 90, 5: 95}
PI = {"fleet": 0.00741, "screenable": 0.00689}


def vkey(x):
    return ".".join((x.get("ver_sw_release") or "").split(" ")[0].lstrip("v").split(".")[:2])


def index(root):
    raw = open(os.path.join(root, "dbinfo.json"), "rb").read()
    return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)


def cases():
    """[(case vehicle, value, source, case log id)] for the 60 analysed sets, exactly as r15_audit.set_table."""
    sets, role = sensitivity.load_between()
    out = []
    for t in r15.set_table():
        rs = sets[t["set"]][t["case"]]
        vals = defaultdict(list)
        for r in rs:
            f = r["features"]
            if f and f.get("vib_p95") is not None:
                vals[f.get("src_vib")].append(f["vib_p95"])
        src = next(s for s, v in vals.items() if len(v) >= 2 and abs(float(np.median(v)) - t["val"]) < 1e-12)
        out.append((t["case"], t["val"], src, rs[0]["log_id"], t["set"]))
    return out


def select(root):
    rows = index(root)
    idx = {x["log_id"]: x for x in rows}
    real = [x for x in rows if "SITL" not in str(x.get("sys_hw")) and x.get("vehicle_uuid")]
    byv = defaultdict(list)
    for x in real:
        byv[x["vehicle_uuid"]].append(x)
    crashed = {v for v, xs in byv.items() if any(x["rating"] in CRASH for x in xs)}
    pool = defaultdict(list)
    for v in sorted(byv):
        if v in crashed:
            continue
        ok = [x for x in byv[v] if (x.get("duration_s") or 0) >= 30]
        if len(ok) >= 3:
            pool[(ok[0]["sys_hw"], vkey(ok[0]), ok[0]["mav_type"])].append((v, ok))
    strata = sorted({(idx[c[3]]["sys_hw"], vkey(idx[c[3]]), idx[c[3]]["mav_type"]) for c in cases()})
    rng_v, rng_f = random.Random(2120), random.Random(2121)
    out = []
    for k in strata:
        cand = list(pool[k])
        rng_v.shuffle(cand)
        for v, logs in cand[:CAP]:
            for x in rng_f.sample(sorted(logs, key=lambda y: y["log_id"]), 3):
                out.append(["|".join(k), v, x["log_id"], x["download_url"]])
    with open(REF_CSV, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["stratum", "vehicle", "log_id", "download_url"])
        w.writerows(out)
    print(f"{len(strata)} strata; {len({r[1] for r in out})} reference drones; {len(out)} logs")


def todo(root):
    have = set(pca.ulg_paths(root))
    return [r for r in csv.DictReader(open(REF_CSV)) if r["log_id"] not in have]


def sizes(root):
    need = todo(root)

    def head(r):
        try:
            req = urllib.request.Request(r["download_url"], method="HEAD")
            return int(urllib.request.urlopen(req, timeout=60).headers.get("Content-Length") or 0)
        except Exception:
            return 0
    with ThreadPoolExecutor(8) as ex:
        s = list(ex.map(head, need))
    print(f"{len(need)} logs to download, {sum(s) / 1e9:.2f} GB (unknown size: {sum(x == 0 for x in s)})")


def fetch(root):
    out_dir = os.path.join(root, "screen_ref")
    os.makedirs(out_dir, exist_ok=True)

    def get(r):
        dest = os.path.join(out_dir, r["log_id"] + ".ulg")
        for _ in range(3):
            try:
                urllib.request.urlretrieve(r["download_url"], dest + ".part")
                os.replace(dest + ".part", dest)
                return True
            except Exception:
                pass
        return False
    need = todo(root)
    with ThreadPoolExecutor(6) as ex:
        ok = list(ex.map(get, need))
    print(f"downloaded {sum(ok)} of {len(need)}")


def feat_one(path):
    from within_drone import features
    try:
        f = features(path, False)
        return None if f is None else {k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in f.items()}
    except Exception:
        return None


def analyze(root):
    paths = pca.ulg_paths(root)
    ref = list(csv.DictReader(open(REF_CSV)))
    ids = sorted({r["log_id"] for r in ref})
    with ProcessPoolExecutor(6) as ex:
        F = dict(zip(ids, ex.map(feat_one, [paths.get(i) for i in ids], chunksize=4)))
    with open(FEATS, "w") as f:
        for i in ids:
            f.write(json.dumps({"log_id": i, "features": F[i]}) + "\n")
    idx = {x["log_id"]: x for x in index(root)}
    C = cases()
    by_drone = defaultdict(list)
    for r in ref:
        by_drone[(r["stratum"], r["vehicle"])].append(r["log_id"])

    def ref_value(logs, src):
        v = [F[l]["vib_p95"] for l in logs if F.get(l) and F[l].get("vib_p95") is not None and F[l].get("src_vib") == src]
        return float(np.median(v)) if len(v) >= 2 else None

    case_rows = []
    for v, val, src, lid, sid in C:
        x = idx[lid]
        case_rows.append({"stratum": "|".join((x["sys_hw"], vkey(x), x["mav_type"])), "src": src, "val": val})
    keys = sorted({(c["stratum"], c["src"]) for c in case_rows})
    refvals = {k: [] for k in keys}
    for (st, v), logs in sorted(by_drone.items()):
        for k in keys:
            if k[0] == st:
                rv = ref_value(logs, k[1])
                if rv is not None:
                    refvals[k].append(rv)
    rng = np.random.default_rng(2122)
    halves = {}
    for k, vals in refvals.items():
        perm = rng.permutation(len(vals))
        halves[k] = ([vals[i] for i in perm[: len(vals) // 2]], [vals[i] for i in perm[len(vals) // 2:]])

    def evaluate(fit, test, cases_):
        res, pooled_used = {}, 0
        by_src = defaultdict(list)
        for k, v in fit.items():
            by_src[k[1]] += v
        thr = {}
        for k in keys:
            base = fit[k] if len(fit[k]) >= 4 else by_src[k[1]]
            pooled_used += len(fit[k]) < 4
            thr[k] = {r: float(np.percentile(base, p)) if base else np.inf for r, p in PCTS.items()}
        for r in PCTS:
            fl = [x > thr[k][r] for k in keys for x in test[k]]
            f = float(np.mean(fl)) if fl else np.nan
            s = float(np.mean([c["val"] > thr[(c["stratum"], c["src"])][r] for c in cases_]))
            d = {"flag_rate": f, "sensitivity": s, "n_test_ref": len(fl)}
            for name, pi in PI.items():
                ppv = s * pi / (s * pi + f * (1 - pi)) if (s * pi + f * (1 - pi)) > 0 else np.nan
                d[f"ppv_{name}"], d[f"lift_{name}"] = ppv, ppv / pi if ppv == ppv else np.nan
            res[r] = d
        pct = [np.mean([x < c["val"] for x in test[(c["stratum"], c["src"])]]) for c in cases_ if test[(c["stratum"], c["src"])]]
        res["auc"], res["pooled_strata"] = float(np.mean(pct)) if pct else np.nan, pooled_used
        return res

    A = {k: h[0] for k, h in halves.items()}
    B = {k: h[1] for k, h in halves.items()}
    out = {"declared_in": "research/px4_log_study/screening_reference.py docstring",
           "n_cases": len(case_rows), "n_strata": len(keys),
           "reference_drones": {"|".join(k): len(v) for k, v in refvals.items()},
           "n_reference_drones": sum(len(v) for v in refvals.values()),
           "features_missing_logs": sum(F[i] is None for i in ids),
           "fit_A_test_B": evaluate(A, B, case_rows), "fit_B_test_A": evaluate(B, A, case_rows)}
    mean = {}
    for r in list(PCTS) + ["auc"]:
        a, b = out["fit_A_test_B"][r], out["fit_B_test_A"][r]
        mean[r] = (a + b) / 2 if r == "auc" else {m: (a[m] + b[m]) / 2 for m in a}
    out["mean"] = mean
    # bootstrap
    rngb = np.random.default_rng(2123)
    boots = defaultdict(list)
    for _ in range(2000):
        cs = [case_rows[i] for i in rngb.integers(0, len(case_rows), len(case_rows))]
        Ab, Bb = {}, {}
        for k in keys:
            a, b = A[k], B[k]
            Ab[k] = [a[i] for i in rngb.integers(0, len(a), len(a))] if a else []
            Bb[k] = [b[i] for i in rngb.integers(0, len(b), len(b))] if b else []
        e1, e2 = evaluate(Ab, Bb, cs), evaluate(Bb, Ab, cs)
        for r in PCTS:
            for m in ("flag_rate", "sensitivity", "ppv_fleet", "lift_fleet", "ppv_screenable", "lift_screenable"):
                boots[f"{r}|{m}"].append((e1[r][m] + e2[r][m]) / 2)
        boots["auc"].append((e1["auc"] + e2["auc"]) / 2)
    out["ci95"] = {k: [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))] for k, v in boots.items()}
    lo = out["ci95"]["10|lift_fleet"][0]
    out["wording"] = ("useful inspection ranking" if mean[10]["lift_fleet"] >= 2 and lo > 1 else
                      "not shown to beat random inspection" if lo <= 1 else "lift above 1 but below 2")
    out["limits"] = ("'no crash-rated log' does not mean the drone never crashed; reference drones have >= 3 archive "
                     "flights; strata are those of the 60 sets")
    json.dump(out, open(os.path.join(RESULTS_DIR, "screening_reference.json"), "w"), indent=1, default=float)
    open(os.path.join(RESULTS_DIR, "screening_reference.md"), "w").write(
        "# Screening reference from non-crash drones\n\nDeclared in `research/px4_log_study/screening_reference.py`.\n\n```\n"
        + json.dumps(out, indent=1, default=float) + "\n```\n")
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    {"select": select, "sizes": sizes, "fetch": fetch, "analyze": analyze}[sys.argv[1]](
        sys.argv[2] if len(sys.argv) > 2 else "/Volumes/One Touch/AeroFleet_px4_data")
