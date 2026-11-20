"""Normal-flight model, exploratory follow-up (dagger): conformal calibration of the expected range.

PRE-DECLARED (committed and pushed before it runs), AFTER the declared test H1 of train_eval.py failed: on held-out
vehicles the 5-95% range held 72.7% of vibration flights and 73.3% of battery flights (pass mark 85-95%). The ranges
are too narrow for drones the model has not seen. This is a fix chosen after seeing that result, so it is exploratory
and is reported as such; H1 stays failed.

METHOD (conformalised quantile regression, Romano et al. 2019), per target, on the saved features
(research/results/normal_flight/features.jsonl, unchanged; same rows, same model settings as train_eval.py):
  conformity score E_i = max(q05_i - y_i, y_i - q95_i), computed out-of-fold with GroupKFold(5) by vehicle;
  widening c = the ceil((n + 1) * 0.90) / n empirical quantile of E; calibrated range = [q05 - c, q95 + c]
  (log scale for vibration).

TEST H4: nested, so the widening is never fitted on the vehicles it is tested on. Outer GroupKFold(5) by vehicle; in
each outer training part, c is computed by an inner GroupKFold(5) by vehicle as above and the three quantile models are
refitted on the whole outer training part; coverage of [q05 - c, q95 + c] is measured on the outer held-out vehicles.
Supported for a target if the pooled coverage lies in [0.85, 0.95]. Also reported: coverage per vehicle kind and the
median width of the range before and after.

If supported, c (computed on all rows) is written into aerofleet/assurance/data/normal_flight_model.json as each
target's "widen", and the app shows the calibrated range. If not supported, the model file is left unchanged and the app
labels its range with the coverage measured in H1.

    python research/normal_flight/calibrate.py
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "research", "results", "normal_flight")
MODEL = os.path.join(ROOT, "aerofleet", "assurance", "data", "normal_flight_model.json")
LEVEL = 0.90


def widening(X, y, groups, fit):
    """Out-of-fold conformity scores by vehicle, and their finite-sample (n+1) quantile."""
    from sklearn.model_selection import GroupKFold
    e = np.zeros(len(y))
    for tr, te in GroupKFold(5).split(X, y, groups):
        lo, hi = fit(X[tr], y[tr], 0.05).predict(X[te]), fit(X[tr], y[tr], 0.95).predict(X[te])
        e[te] = np.maximum(np.minimum(lo, hi) - y[te], y[te] - np.maximum(lo, hi))
    k = min(len(e), math.ceil((len(e) + 1) * LEVEL))
    return float(np.sort(e)[k - 1])


def main():
    import train_eval as te
    from sklearn.model_selection import GroupKFold

    rows = [json.loads(line) for line in open(os.path.join(OUT, "features.jsonl"))]
    model = json.load(open(MODEL))
    hw_values = model["card"]["hardware_values"]
    res = {}
    for target, spec in te.TARGETS.items():
        rs = [r for r in rows if r.get(target) is not None and (spec["transform"] != "log" or r[target] > 0)]
        X, y, _enc, _ = te.design(rs, target, hw_values)
        groups = np.array([r["vehicle"] for r in rs])
        inside_raw, inside_cal, width_raw, width_cal = np.zeros(len(y), bool), np.zeros(len(y), bool), [], []
        for tr, tst in GroupKFold(5).split(X, y, groups):
            c = widening(X[tr], y[tr], groups[tr], te.fit)
            lo, hi = te.fit(X[tr], y[tr], 0.05).predict(X[tst]), te.fit(X[tr], y[tr], 0.95).predict(X[tst])
            lo, hi = np.minimum(lo, hi), np.maximum(lo, hi)
            inside_raw[tst] = (y[tst] >= lo) & (y[tst] <= hi)
            inside_cal[tst] = (y[tst] >= lo - c) & (y[tst] <= hi + c)
            width_raw += list(hi - lo)
            width_cal += list(hi - lo + 2 * c)
        cov = float(np.mean(inside_cal))
        kinds = sorted({r["kind"] for r in rs})
        res[target] = {"flights": len(rs), "coverage_before": float(np.mean(inside_raw)), "coverage_after": cov,
                       "coverage_after_by_kind": {k: float(np.mean(inside_cal[[r["kind"] == k for r in rs]])) for k in kinds},
                       "median_width_before": float(np.median(width_raw)), "median_width_after": float(np.median(width_cal)),
                       "H4_supported": 0.85 <= cov <= 0.95,
                       "widen_all_rows": widening(X, y, groups, te.fit)}
    supported = all(r["H4_supported"] for r in res.values())
    if supported:
        for target, r in res.items():
            model["targets"][target]["widen"] = r["widen_all_rows"]
        model["card"]["calibration"] = "conformal widening (research/normal_flight/calibrate.py), held-out coverage " + \
            ", ".join(f"{t} {100 * r['coverage_after']:.1f}%" for t, r in res.items())
        json.dump(model, open(MODEL, "w"))
    res["written_to_model"] = supported
    json.dump(res, open(os.path.join(OUT, "calibration.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
