"""Normal-flight model: train and evaluate the expected-range model used by aerofleet/assurance/normal_flight.py.

PRE-DECLARED: this docstring (data, exclusions, model, fixed settings, tests and pass marks) is committed and pushed
before any feature is extracted from the training logs and before any model is fitted. Engineering check before commit
(not an analysis): `features()` was run on one screen_ref log (a control log was too short) and only the names of
its fields were printed.

WHAT IS LEARNED: for an ordinary PX4 flight, the 5th, 50th and 95th percentile of two measured quantities given how and
on what the drone flew. No crash label is used anywhere (the study found them unreliable).
  T1 vibration: 95th percentile of the autopilot's vibration metric over the flight (last 10 s left out); log scale.
  T2 battery_drop_pct_per_min: battery voltage drop from the first to the last tenth of the flight, % of the start
     voltage, per minute.
  Conditions: vibration source (T1 only), vehicle kind (multirotor / fixed wing / other), flight-controller hardware
  (the 15 most common in the training data, others pooled), firmware (major*100+minor), minutes, mean ground speed,
  median and maximum height above home, share of time in pilot-controlled modes, battery cell count, and (T2 only)
  starting volts per cell. Missing values are left missing for the trees to route.

DATA: every .ulg already downloaded for the study under AEROFLEET_PX4_DATA (folders except external/ and forum logs),
looked up in the archive index (dbinfo.json, 479,547 logs). Kept: real hardware (hardware name without "SITL"), not
rated crash_sw_hw, crash_pilot or unsatisfactory, readable by AeroFleet's reader, PX4, at least 60 s of track, and not
cut short (parsed length at least half the index's duration_s; the study's control folder holds some truncated
downloads). Excluded: the eight vehicles of the demo fleet (demo_fleet_key.json), so the app never scores a drone the
model was trained on. At most 10 flights per vehicle (random, seed 7) so no airframe dominates.

MODEL (fixed, not tuned on these data): scikit-learn HistGradientBoostingRegressor, loss="quantile",
quantile in {0.05, 0.5, 0.95}, max_iter=300, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=20,
l2_regularization=1.0, random_state=0. One model per target and quantile.

TESTS (held-out vehicles: GroupKFold, 5 folds, grouped by vehicle; every fold is fitted on the other four):
  H1 calibration: share of held-out flights inside their predicted 5-95% range; supported for a target if it lies in
     [0.85, 0.95].
  H2 skill: mean absolute error of the 50th-percentile prediction (log scale for T1) against a baseline that predicts
     the training fold's median (per vibration source for T1); supported for a target if the model's error is at least
     10% lower.
  H3 positive control on injected faults (RflyMAD real flights, Le et al. 2025, already downloaded under
     external/rflymad; onset from the log's rfly_ctrl_lxl fault code as in research/px4_log_study/rflymad_eval.py):
     for each motor-fault flight, the vibration score s = (log observed - log q50) / (log q95 - log q05) in the 10 s
     after onset against the 10 s before onset, conditions computed for each window from the same final model.
     Supported if post > pre by a one-sided Wilcoxon signed-rank test, p < 0.025. A flight whose windows have fewer than
     10 vibration samples or 5 track points is excluded and counted. Reported, not tested: the same for sensor-fault
     flights, and no-fault flights at a pseudo-onset (take-off + the median onset offset of the fault flights).
  The final model is fitted on all kept flights and exported to aerofleet/assurance/data/normal_flight_model.json;
  its exported trees must reproduce scikit-learn's predictions on every training row to within 1e-6.

OUTPUT: research/results/normal_flight/ (features.jsonl, results.json, model_card.md). Every result is reported,
whether or not a test is supported.

    AEROFLEET_PX4_DATA="/Volumes/One Touch/AeroFleet_px4_data" python research/normal_flight/train_eval.py
"""
from __future__ import annotations

import collections
import gzip
import json
import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
DATA = os.environ.get("AEROFLEET_PX4_DATA", "/Volumes/One Touch/AeroFleet_px4_data")
OUT = os.path.join(ROOT, "research", "results", "normal_flight")
MODEL_OUT = os.path.join(ROOT, "aerofleet", "assurance", "data", "normal_flight_model.json")
BAD = {"crash_sw_hw", "crash_pilot", "unsatisfactory"}
PER_VEHICLE, TOP_HW, WIN = 10, 15, 10.0
PARAMS = dict(max_iter=300, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=20, l2_regularization=1.0, random_state=0)
QUANTILES = {"q05": 0.05, "q50": 0.5, "q95": 0.95}
TARGETS = {
    "vibration": {"numeric": ["firmware", "minutes", "speed_ms", "height_m", "max_height_m", "manual_share", "cells"],
                  "cats": ["source", "kind", "hardware"], "transform": "log"},
    "battery_drop_pct_per_min": {"numeric": ["firmware", "minutes", "speed_ms", "height_m", "max_height_m", "manual_share",
                                             "cells", "volts_per_cell"], "cats": ["kind", "hardware"], "transform": None},
}


def extract(path):
    from aerofleet.assurance.flightlog import read_flight_log
    from aerofleet.assurance.normal_flight import features
    try:
        return features(read_flight_log(path))
    except Exception:  # noqa: BLE001 - an unreadable public log is skipped and counted
        return None


def select():
    index = {r["log_id"]: r for r in json.load(gzip.open(os.path.join(DATA, "dbinfo.json")))}
    demo = set()
    key = os.path.join(DATA, "demo_fleet_key.json")
    if os.path.exists(key):
        demo = {f["vehicle_uuid"].lower() for f in json.load(open(key))["flights"]}
    paths, counts = {}, collections.Counter()
    for d, _dirs, files in os.walk(DATA):
        rel = os.path.relpath(d, DATA)
        if rel.startswith(("external", "forum")):
            continue
        for f in sorted(files):
            if f.endswith(".ulg") and not f.startswith("._"):
                paths.setdefault(f[:-4], os.path.join(d, f))
    by_vehicle = collections.defaultdict(list)
    for log_id, p in sorted(paths.items()):
        r = index.get(log_id)
        if r is None:
            counts["not in index"] += 1
        elif "SITL" in str(r.get("sys_hw")).upper():
            counts["simulation"] += 1
        elif r.get("rating") in BAD:
            counts["crash or unsatisfactory rating"] += 1
        elif not r.get("vehicle_uuid"):
            counts["no vehicle id"] += 1
        elif r["vehicle_uuid"].lower() in demo:
            counts["demo fleet vehicle"] += 1
        else:
            by_vehicle[r["vehicle_uuid"].lower()].append((log_id, p, float(r.get("duration_s") or 0)))
    rng, chosen = random.Random(7), []
    for v, logs in sorted(by_vehicle.items()):
        if len(logs) > PER_VEHICLE:
            counts["over 10 per vehicle"] += len(logs) - PER_VEHICLE
            logs = rng.sample(logs, PER_VEHICLE)
        chosen += [(v,) + x for x in logs]
    return chosen, counts, len(paths)


def build_features(chosen, counts):
    rows = []
    with ProcessPoolExecutor(6) as pool:
        for (v, log_id, p, dur), f in zip(chosen, pool.map(extract, [c[2] for c in chosen], chunksize=4)):
            if f is None:
                counts["unreadable, not PX4 or under 60 s"] += 1
            elif dur > 0 and f["minutes"] * 60 + 10 < 0.5 * dur:
                counts["cut short (truncated download)"] += 1
            else:
                rows.append(dict(f, vehicle=v, log_id=log_id))
    return rows


def design(rows, target, hw_values):
    spec = TARGETS[target]
    cats = {c: (hw_values if c == "hardware" else sorted({r[c] for r in rows})) for c in spec["cats"]}
    from aerofleet.assurance.normal_flight import encode
    enc = {"numeric": spec["numeric"], "categories": cats}
    X = np.array([encode(r, enc) for r in rows], dtype=float)
    y = np.array([r[target] for r in rows], dtype=float)
    if spec["transform"] == "log":
        y = np.log(y)
    names = spec["numeric"] + [f"{c}={v}" for c, vs in cats.items() for v in vs + ["other"]]
    return X, y, enc, names


def fit(X, y, q):
    from sklearn.ensemble import HistGradientBoostingRegressor
    return HistGradientBoostingRegressor(loss="quantile", quantile=q, **PARAMS).fit(X, y)


def export(m):
    """Trees of a fitted HistGradientBoostingRegressor in the form normal_flight._predict reads."""
    trees = []
    for pred in m._predictors:
        n = pred[0].nodes
        leaf = n["is_leaf"].astype(bool)
        trees.append({"left": [-1 if leaf[i] else int(n["left"][i]) for i in range(len(n))],
                      "right": [-1 if leaf[i] else int(n["right"][i]) for i in range(len(n))],
                      "feature": [int(x) for x in n["feature_idx"]], "threshold": [float(x) for x in n["num_threshold"]],
                      "missing_left": [bool(x) for x in n["missing_go_to_left"]], "value": [float(x) for x in n["value"]]})
    return {"init": float(np.ravel(m._baseline_prediction)[0]), "learning_rate": 1.0, "trees": trees}


def evaluate(rows, hw_values):
    from sklearn.model_selection import GroupKFold
    res = {}
    for target in TARGETS:
        rs = [r for r in rows if r.get(target) is not None and (TARGETS[target]["transform"] != "log" or r[target] > 0)]
        X, y, enc, _ = design(rs, target, hw_values)
        groups = np.array([r["vehicle"] for r in rs])
        pred = {k: np.zeros(len(y)) for k in QUANTILES}
        base = np.zeros(len(y))
        for tr, te in GroupKFold(5).split(X, y, groups):
            for k, q in QUANTILES.items():
                pred[k][te] = fit(X[tr], y[tr], q).predict(X[te])
            if target == "vibration":
                med = {}
                for i in tr:
                    med.setdefault(rs[i]["source"], []).append(y[i])
                med = {s: float(np.median(v)) for s, v in med.items()}
                base[te] = [med.get(rs[i]["source"], float(np.median(y[tr]))) for i in te]
            else:
                base[te] = float(np.median(y[tr]))
        lo, hi = np.minimum(pred["q05"], pred["q95"]), np.maximum(pred["q05"], pred["q95"])
        inside = (y >= lo) & (y <= hi)
        mae_m, mae_b = float(np.mean(np.abs(y - pred["q50"]))), float(np.mean(np.abs(y - base)))
        by_kind = {k: float(np.mean(inside[[r["kind"] == k for r in rs]])) for k in sorted({r["kind"] for r in rs})}
        res[target] = {"flights": len(rs), "vehicles": len(set(groups)), "coverage_5_95": float(np.mean(inside)),
                       "coverage_by_kind": by_kind, "mae_model": mae_m, "mae_baseline": mae_b,
                       "mae_reduction": 1 - mae_m / mae_b if mae_b > 0 else None,
                       "H1_supported": 0.85 <= float(np.mean(inside)) <= 0.95,
                       "H2_supported": mae_b > 0 and mae_m <= 0.9 * mae_b}
    return res


def final_models(rows, hw_values):
    out, exact = {"targets": {}}, {}
    for target, spec in TARGETS.items():
        rs = [r for r in rows if r.get(target) is not None and (spec["transform"] != "log" or r[target] > 0)]
        X, y, enc, names = design(rs, target, hw_values)
        qs, worst = {}, 0.0
        from aerofleet.assurance.normal_flight import _predict
        for k, q in QUANTILES.items():
            m = fit(X, y, q)
            qs[k] = export(m)
            mine = np.array([_predict(qs[k], list(x)) for x in X])
            worst = max(worst, float(np.max(np.abs(mine - m.predict(X)))))
        exact[target] = worst
        out["targets"][target] = {"numeric": enc["numeric"], "categories": enc["categories"], "transform": spec["transform"],
                                  "quantiles": qs, "feature_names": names, "flights": len(rs),
                                  "vehicles": len({r["vehicle"] for r in rs})}
    return out, exact


def rfly(final):
    """H3: vibration score in the 10 s before and after the injected fault, same flight, same final model."""
    sys.path.insert(0, os.path.join(ROOT, "research", "px4_log_study"))
    from pyulog import ULog
    from scipy.stats import wilcoxon

    from aerofleet.assurance import normal_flight as nf
    from aerofleet.assurance.flightlog import read_flight_log
    from rflymad_eval import onset

    nf.model = lambda: final  # type: ignore[assignment]   # score with the model just fitted, not a file on disk
    root = os.path.join(DATA, "external", "rflymad")
    cases = []
    for d, _dirs, files in os.walk(root):
        for f in files:
            if f.endswith(".ulg") and not f.startswith("._"):
                cls = os.path.relpath(d, root).split(os.sep)[0].replace("Real-", "").lower()
                cases.append((cls, os.path.join(d, f)))
    scored, skipped, offsets = [], collections.Counter(), []

    def score(fl, a, b):
        f = nf.features(fl, a, b)
        if f is None or f["vibration"] is None or f["vibration"] <= 0:
            return None
        e = nf.expected("vibration", f)
        s = (np.log(f["vibration"]) - np.log(e["mid"])) / max(1e-9, np.log(e["high"]) - np.log(e["low"]))
        return float(s), bool(f["vibration"] > e["high"])

    loaded = []
    for cls, p in sorted(cases):
        try:
            u = ULog(p, message_name_filter_list=["rfly_ctrl_lxl"])
            tf, _end, _id = onset(u)
            fl = read_flight_log(p)
        except Exception:  # noqa: BLE001
            skipped[f"{cls}: unreadable"] += 1
            continue
        t_f = None if tf is None else (tf - u.start_timestamp) / 1e6
        if cls != "no_fault" and t_f is None:
            skipped[f"{cls}: no fault code"] += 1
            continue
        if cls == "no_fault" and t_f is not None:
            skipped["no_fault: has a fault code"] += 1
            continue
        if t_f is not None and fl.track:
            offsets.append(t_f - fl.track[0][0])
        loaded.append((cls, p, fl, t_f))
    pseudo = float(np.median(offsets)) if offsets else 30.0
    for cls, p, fl, t_f in loaded:
        t = t_f if t_f is not None else fl.track[0][0] + pseudo
        pre, post = score(fl, t - WIN, t), score(fl, t, t + WIN)
        if pre is None or post is None:
            skipped[f"{cls}: window too sparse"] += 1
            continue
        scored.append({"class": cls, "file": os.path.relpath(p, root), "pre": pre[0], "post": post[0],
                       "pre_above": pre[1], "post_above": post[1]})
    res = {"skipped": dict(skipped), "pseudo_onset_s": pseudo}
    for cls in ("motor", "sensors", "no_fault"):
        s = [x for x in scored if x["class"] == cls]
        if not s:
            continue
        pre, post = np.array([x["pre"] for x in s]), np.array([x["post"] for x in s])
        alt = "greater" if cls == "motor" else "two-sided"
        p = float(wilcoxon(post, pre, alternative=alt).pvalue) if len(s) >= 5 else None
        res[cls] = {"flights": len(s), "median_pre": float(np.median(pre)), "median_post": float(np.median(post)),
                    "share_post_higher": float(np.mean(post > pre)), "p": p, "alternative": alt,
                    "share_above_range_pre": float(np.mean([x["pre_above"] for x in s])),
                    "share_above_range_post": float(np.mean([x["post_above"] for x in s]))}
    res["H3_supported"] = bool(res.get("motor", {}).get("p") is not None and res["motor"]["p"] < 0.025)
    return res, scored


def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    chosen, counts, n_local = select()
    print(f"{n_local} local logs; {len(chosen)} chosen after the archive-index filters", flush=True)
    rows = build_features(chosen, counts)
    with open(os.path.join(OUT, "features.jsonl"), "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    hw_counts = collections.Counter(r["hardware"] for r in rows)
    hw_values = [h for h, _ in hw_counts.most_common(TOP_HW)]
    print(f"{len(rows)} flights of {len({r['vehicle'] for r in rows})} vehicles kept; evaluating", flush=True)
    ev = evaluate(rows, hw_values)
    final, exact = final_models(rows, hw_values)
    final["card"] = {"name": "AeroFleet normal-flight model v1", "trained": time.strftime("%Y-%m-%d"),
                     "flights": len(rows), "vehicles": len({r["vehicle"] for r in rows}), "hardware_values": hw_values,
                     "settings": PARAMS, "declared_in": "research/normal_flight/train_eval.py"}
    h3, scored = rfly(final)
    with open(MODEL_OUT, "w") as fh:
        json.dump(final, fh)
    results = {"local_logs": n_local, "chosen": len(chosen), "kept": len(rows), "excluded": dict(counts),
               "evaluation": ev, "export_max_abs_error": exact, "export_exact": all(v < 1e-6 for v in exact.values()),
               "rflymad": h3, "seconds": round(time.time() - t0)}
    json.dump(results, open(os.path.join(OUT, "results.json"), "w"), indent=1)
    with open(os.path.join(OUT, "rflymad_scores.jsonl"), "w") as fh:
        for s in scored:
            fh.write(json.dumps(s) + "\n")
    print(json.dumps({k: v for k, v in results.items() if k != "evaluation"}, indent=1))
    print(json.dumps(ev, indent=1))


if __name__ == "__main__":
    main()
