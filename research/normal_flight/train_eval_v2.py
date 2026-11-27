"""Normal-flight model v2: does adding the drone's measured LOADING improve the expected range? Declared test.

PRE-DECLARED: this docstring and the code below are committed and pushed before any v2 feature is extracted and before
any v2 model is fitted. Engineering check before declaring (not an analysis): the new reader was run on five logs and
only whether a thrust value came out was looked at.

WHY. The model was not trained on spraying drones and payload is not an input. No public log records payload weight,
and the public archive holds almost no spraying flights (20 entries from 4 vehicles mention spraying or agriculture),
so a model cannot honestly be trained "on sprayers". What every PX4 log does record is the collective thrust the
autopilot commanded (vehicle_attitude_setpoint): a heavier drone, or one with a full tank, needs more thrust to stay
up, and a tank emptying shows as a fall during the flight. So loading can be measured from the log itself.

NEW INPUTS (aerofleet/assurance/normal_flight.features, at this commit): thrust = median commanded collective thrust
(0-1) while the motors work (above 5%), over the same window as the targets (last 10 s left out); thrust_change = median
of the last quarter of those samples minus the first quarter. Missing when fewer than 20 samples (the trees route it).

DATA: exactly as v1 (train_eval.select and build_features, same filters, same per-vehicle cap and seed 7), re-extracted
with the new reader; written to research/results/normal_flight/features_v2.jsonl. If the kept flights differ from v1's
1,121, that is reported.

MODELS: v1 = v1's inputs; v2 = v1's inputs + thrust + thrust_change. Same settings as v1 (train_eval.PARAMS), same
quantiles, same top-15 hardware values. Both are evaluated on the same rows with the same GroupKFold(5) split by vehicle.

TESTS
  H5 (primary): battery voltage drop. Supported if v2's mean absolute error of the 50th percentile on held-out vehicles
     is at least 10% lower than v1's.
  H5v (vibration, same rule): reported; decides only whether v2 is used for the vibration target.
  H6: calibrated coverage of v2's 5-95% range, computed exactly as H4 (nested conformal widening, calibrate.py),
     supported for a target if it lies in [0.85, 0.95].
SHIP RULE (decided here, in advance): the battery target switches to v2 only if H5 and H6 (battery) are supported; the
vibration target switches to v2 only if v2's error is not higher than v1's and H6 (vibration) is supported. A switched
target is refitted on all rows, exported (must reproduce scikit-learn within 1e-6) and widened as in H4; otherwise the
model file stays exactly as it is. Every result is reported, whether or not anything ships.

OUTPUT: research/results/normal_flight/results_v2.json, features_v2.jsonl, model_card_v2.md.

    AEROFLEET_PX4_DATA="/Volumes/One Touch/AeroFleet_px4_data" python research/normal_flight/train_eval_v2.py
"""
from __future__ import annotations

import collections
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calibrate as cal  # noqa: E402
import train_eval as te  # noqa: E402

LOADING = ["thrust", "thrust_change"]
V1 = te.TARGETS
V2 = {t: {**spec, "numeric": spec["numeric"] + LOADING} for t, spec in V1.items()}


def design(rows, target, hw_values, targets):
    saved = te.TARGETS
    te.TARGETS = targets
    try:
        return te.design(rows, target, hw_values)
    finally:
        te.TARGETS = saved


def compare(rows, hw_values):
    from sklearn.model_selection import GroupKFold

    out = {}
    for target, spec in V1.items():
        rs = [r for r in rows if r.get(target) is not None and (spec["transform"] != "log" or r[target] > 0)]
        groups = np.array([r["vehicle"] for r in rs])
        res = {"flights": len(rs), "vehicles": len(set(groups)),
               "with_thrust": sum(1 for r in rs if r.get("thrust") is not None)}
        for name, targets in (("v1", V1), ("v2", V2)):
            X, y, _enc, _ = design(rs, target, hw_values, targets)
            q50 = np.zeros(len(y))
            for tr, tst in GroupKFold(5).split(X, y, groups):
                q50[tst] = te.fit(X[tr], y[tr], 0.5).predict(X[tst])
            res[f"mae_{name}"] = float(np.mean(np.abs(y - q50)))
        res["reduction"] = 1 - res["mae_v2"] / res["mae_v1"] if res["mae_v1"] > 0 else None
        X, y, _enc, _ = design(rs, target, hw_values, V2)
        inside = np.zeros(len(y), bool)
        for tr, tst in GroupKFold(5).split(X, y, groups):
            c = cal.widening(X[tr], y[tr], groups[tr], te.fit)
            lo, hi = te.fit(X[tr], y[tr], 0.05).predict(X[tst]), te.fit(X[tr], y[tr], 0.95).predict(X[tst])
            lo, hi = np.minimum(lo, hi), np.maximum(lo, hi)
            inside[tst] = (y[tst] >= lo - c) & (y[tst] <= hi + c)
        res["coverage_v2_calibrated"] = float(np.mean(inside))
        res["H6_supported"] = 0.85 <= res["coverage_v2_calibrated"] <= 0.95
        out[target] = res
    b, v = out["battery_drop_pct_per_min"], out["vibration"]
    b["H5_supported"] = b["reduction"] is not None and b["reduction"] >= 0.10
    v["H5v_supported"] = v["reduction"] is not None and v["reduction"] >= 0.10
    b["ship_v2"] = b["H5_supported"] and b["H6_supported"]
    v["ship_v2"] = v["mae_v2"] <= v["mae_v1"] and v["H6_supported"]
    return out


def ship(rows, hw_values, decisions):
    """Refit and export only the targets the ship rule allows; widen them as in H4. Returns the exact-match errors."""
    from aerofleet.assurance.normal_flight import _predict

    model = json.load(open(te.MODEL_OUT))
    exact = {}
    for target, spec in V2.items():
        if not decisions[target]["ship_v2"]:
            continue
        rs = [r for r in rows if r.get(target) is not None and (spec["transform"] != "log" or r[target] > 0)]
        X, y, enc, names = design(rs, target, hw_values, V2)
        groups = np.array([r["vehicle"] for r in rs])
        qs, worst = {}, 0.0
        for k, q in te.QUANTILES.items():
            m = te.fit(X, y, q)
            qs[k] = te.export(m)
            mine = np.array([_predict(qs[k], list(x)) for x in X])
            worst = max(worst, float(np.max(np.abs(mine - m.predict(X)))))
        exact[target] = worst
        model["targets"][target] = {"numeric": enc["numeric"], "categories": enc["categories"], "transform": spec["transform"],
                                    "quantiles": qs, "feature_names": names, "flights": len(rs),
                                    "vehicles": len({r["vehicle"] for r in rs}),
                                    "widen": cal.widening(X, y, groups, te.fit), "inputs_version": "v2 (with measured loading)"}
    if exact and all(e < 1e-6 for e in exact.values()):
        model["card"]["name"] = "AeroFleet normal-flight model v2 (measured loading)"
        model["card"]["v2"] = {t: "v2" if d["ship_v2"] else "v1" for t, d in decisions.items()}
        model["card"]["v2_declared_in"] = "research/normal_flight/train_eval_v2.py"
        json.dump(model, open(te.MODEL_OUT, "w"))
    return exact


def main():
    t0 = time.time()
    chosen, counts, n_local = te.select()
    rows = te.build_features(chosen, counts)
    with open(os.path.join(te.OUT, "features_v2.jsonl"), "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    v1_model = json.load(open(te.MODEL_OUT))
    hw_values = v1_model["card"]["hardware_values"]
    decisions = compare(rows, hw_values)
    exact = ship(rows, hw_values, decisions)
    res = {"kept": len(rows), "vehicles": len({r["vehicle"] for r in rows}), "v1_kept": 1121, "excluded": dict(counts),
           "comparison": decisions, "export_max_abs_error": exact,
           "shipped": {t: d["ship_v2"] for t, d in decisions.items()}, "seconds": round(time.time() - t0)}
    json.dump(res, open(os.path.join(te.OUT, "results_v2.json"), "w"), indent=1)
    b, v = decisions["battery_drop_pct_per_min"], decisions["vibration"]
    md = ["# Normal-flight model v2: measured loading as an input (declared test)", "",
          "Declared in `research/normal_flight/train_eval_v2.py`. Full numbers in `results_v2.json`.", "",
          f"Flights kept: {res['kept']} of {res['vehicles']} vehicles (v1: 1,121). With a thrust value: battery "
          f"{b['with_thrust']} of {b['flights']}, vibration {v['with_thrust']} of {v['flights']}.", "",
          "| Test | v1 | v2 | Result | Pass mark | Outcome |", "|---|---|---|---|---|---|",
          f"| H5 battery drop, error of the middle estimate on held-out drones | {b['mae_v1']:.3f} | {b['mae_v2']:.3f} | "
          f"{100 * b['reduction']:.1f}% lower | at least 10% lower | {'Supported' if b['H5_supported'] else 'Not supported'} |",
          f"| H5v vibration (log scale), same | {v['mae_v1']:.3f} | {v['mae_v2']:.3f} | {100 * v['reduction']:.1f}% lower | "
          f"at least 10% lower | {'Supported' if v['H5v_supported'] else 'Not supported'} |",
          f"| H6 battery, calibrated coverage of v2 | | {100 * b['coverage_v2_calibrated']:.1f}% | | 85-95% | "
          f"{'Supported' if b['H6_supported'] else 'Not supported'} |",
          f"| H6 vibration, calibrated coverage of v2 | | {100 * v['coverage_v2_calibrated']:.1f}% | | 85-95% | "
          f"{'Supported' if v['H6_supported'] else 'Not supported'} |", "",
          f"Shipped by the declared rule: battery {'v2' if b['ship_v2'] else 'stays v1'}, vibration "
          f"{'v2' if v['ship_v2'] else 'stays v1'}."]
    open(os.path.join(te.OUT, "model_card_v2.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
