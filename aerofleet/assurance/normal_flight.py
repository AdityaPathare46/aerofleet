"""What a healthy flight looks like for a drone like this one: a learned expected range for vibration and battery drop.

Why: an operator with one or two drones has nothing to compare a flight with. A model trained on thousands of ordinary
public PX4 flights (research/normal_flight/train_eval.py) learns how vibration and battery voltage drop depend on the
kind of drone, its flight-controller hardware and firmware, and how it was flown. For a new flight it gives an expected
range (5th to 95th percentile) and says whether the flight is below, inside or above it.

What it is not: a crash predictor or a verdict. It is trained on ordinary flights only, with no crash labels (the study
behind AeroFleet showed those labels and crash predictors are unreliable). "Above the expected range" means look at
the drone, nothing more, and it never changes a readiness verdict. PX4 logs only: the model has seen no ArduPilot data.

The trees are exported from scikit-learn to data/normal_flight_model.json and evaluated here in plain Python, so the
product imports no machine-learning library. The same `features()` builds the training data and scores an upload.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from aerofleet.assurance.flightlog import MULTIROTORS
from aerofleet.assurance.reconcile import PILOT_MODES

MODEL = Path(__file__).with_name("data") / "normal_flight_model.json"
END_MARGIN_S = 10.0                    # as for the vibration value: an impact must not shape the numbers
MIN_S = 60.0
NOTE = ("Expected range from a model trained on ordinary public PX4 flights of similar drones (no crash data). Context for "
        "an inspector, not a prediction: being outside the range was not shown to mean a drone will fail.")
SPRAYER_LIMIT = ("Not trained on spraying drones: they are heavier and their tank empties during the flight, and payload is "
                 "not an input, so for a sprayer the battery range in particular is a rough guide only.")


def kind_of(vehicle: Optional[str]) -> str:
    if vehicle in MULTIROTORS:
        return "multirotor"
    if vehicle == "fixed wing":
        return "fixed wing"
    return "other"


def _fw(firmware: Optional[str]) -> Optional[float]:
    """"1.14" -> 114.0, so newer firmware is a larger number."""
    try:
        major, minor = (int(x) for x in str(firmware).split(".")[:2])
        return float(major * 100 + minor)
    except (TypeError, ValueError):
        return None


def _metres(la1: float, lo1: float, la2: float, lo2: float) -> float:
    dy = (la2 - la1) * 111_320.0
    dx = (lo2 - lo1) * 111_320.0 * math.cos(math.radians((la1 + la2) / 2))
    return math.hypot(dx, dy)


def features(flight, t_from: Optional[float] = None, t_to: Optional[float] = None) -> Optional[Dict[str, Any]]:
    """Conditions and measured targets for a PX4 flight (or a window of it, in log seconds), or None if unusable."""
    if getattr(flight, "format", None) != "ulg" or not flight.track:
        return None
    whole = t_from is None and t_to is None
    a = flight.track[0][0] if t_from is None else t_from
    b = flight.track[-1][0] - END_MARGIN_S if t_to is None else t_to
    track = [p for p in flight.track if a <= p[0] <= b]
    if len(track) < 5 or (whole and b - a < MIN_S):
        return None
    secs = track[-1][0] - track[0][0]
    if secs <= 0:
        return None
    dist = sum(_metres(p[1], p[2], q[1], q[2]) for p, q in zip(track, track[1:]))
    heights = [p[3] for p in track]
    manual, prev = 0.0, None                                   # seconds flown in pilot-controlled modes inside [a, b]
    marks = sorted(flight.modes) + [(b, None)]
    for (t, m), (t2, _m2) in zip(marks, marks[1:]):
        lo, hi = max(t, a), min(t2, b)
        if hi > lo and m and m.upper() in PILOT_MODES:
            manual += hi - lo
    vib = [v for t, v in flight.vibration if a <= t <= b]
    # Loading, measured from the log itself: the collective thrust the autopilot commanded while the motors were working
    # (above 5%). A heavier drone or a full tank needs more thrust to stay up; a tank emptying shows as a fall over the
    # flight. No payload weight is recorded in any PX4 log, so this is the closest measured stand-in.
    thr = sorted((t, v) for t, v in getattr(flight, "thrust", []) if a <= t <= b and v > 0.05)
    q = len(thr) // 4
    cells = flight.params.get("BAT1_N_CELLS") or flight.params.get("BAT_N_CELLS")
    batt = [v for t, v, _r in flight.battery if a <= t <= b and v > 0]
    out: Dict[str, Any] = {
        "source": flight.vibration_source or "none", "kind": kind_of(flight.vehicle), "hardware": flight.hardware or "unknown",
        "firmware": _fw(flight.firmware), "minutes": secs / 60.0, "speed_ms": dist / secs,
        "height_m": float(np.median(heights)), "max_height_m": float(max(heights)), "manual_share": manual / secs,
        "cells": float(cells) if cells and cells > 0 else None,
        "vibration": float(np.percentile(vib, 95)) if len(vib) >= 10 else None,
        "battery_drop_pct_per_min": None, "volts_per_cell": None,
        "thrust": float(np.median([v for _, v in thr])) if len(thr) >= 20 else None,
        "thrust_change": (float(np.median([v for _, v in thr[-q:]])) - float(np.median([v for _, v in thr[:q]])))
                         if len(thr) >= 20 else None,
    }
    if len(batt) >= 20:
        k = max(1, len(batt) // 10)
        v0, v1 = float(np.median(batt[:k])), float(np.median(batt[-k:]))
        if v0 > 0:
            out["battery_drop_pct_per_min"] = 100.0 * (v0 - v1) / v0 / out["minutes"]
            out["volts_per_cell"] = v0 / out["cells"] if out["cells"] else None
    return out


# ── evaluating the exported model ──────────────────────────────────────────────

@lru_cache(maxsize=1)
def model() -> Optional[Dict[str, Any]]:
    try:
        return json.loads(MODEL.read_text())
    except (OSError, ValueError):
        return None


def encode(f: Dict[str, Any], spec: Dict[str, Any]) -> Optional[List[float]]:
    """Numeric columns as they are (missing as NaN, which the trees were trained to route), categories one-hot."""
    row: List[float] = []
    for name in spec["numeric"]:
        v = f.get(name)
        row.append(float("nan") if v is None else float(v))
    for name, values in spec["categories"].items():
        v = f.get(name) if f.get(name) in values else "other"
        row += [1.0 if v == c else 0.0 for c in values + ["other"]]
    return row


def _tree(t: Dict[str, List], x: List[float]) -> float:
    i = 0
    while t["left"][i] != -1:
        v = x[t["feature"][i]]
        # scikit-learn sends a missing value to the side recorded at training ("missing_left"), else compares
        go_left = bool(t["missing_left"][i]) if v != v else v <= t["threshold"][i]
        i = t["left"][i] if go_left else t["right"][i]
    return t["value"][i]


def _predict(q: Dict[str, Any], x: List[float]) -> float:
    return q["init"] + q["learning_rate"] * sum(_tree(t, x) for t in q["trees"])


def expected(target: str, f: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """Expected 5th, 50th and 95th percentile of a target for these conditions, in the target's own units."""
    m = model()
    spec = (m or {}).get("targets", {}).get(target)
    if not spec:
        return None
    x = encode(f, spec)
    raw = {name: _predict(q, x) for name, q in spec["quantiles"].items()}
    w = float(spec.get("widen") or 0.0)                       # conformal widening, when calibration passed its test
    raw["q05"], raw["q95"] = min(raw["q05"], raw["q95"]) - w, max(raw["q05"], raw["q95"]) + w
    back = (lambda v: math.exp(v)) if spec.get("transform") == "log" else (lambda v: v)   # noqa: E731
    lo, mid, hi = sorted(back(raw[k]) for k in ("q05", "q50", "q95"))
    return {"low": lo, "mid": mid, "high": hi}


def assess(flight) -> Optional[Dict[str, Any]]:
    """For the flight review: each target's observed value against its expected range, or None without a model."""
    if model() is None:
        return None
    f = features(flight)
    if f is None:
        return None
    out: Dict[str, Any] = {"note": f"{NOTE} {SPRAYER_LIMIT}", "model": model().get("card", {}).get("name"), "targets": {}}
    for target, label, unit in (("vibration", "Vibration (95th percentile)", f"{f['source']} units"),
                                ("battery_drop_pct_per_min", "Battery voltage drop", "% per minute")):
        obs, exp = f.get(target), expected(target, f)
        if obs is None or exp is None:
            continue
        where = "above" if obs > exp["high"] else "below" if obs < exp["low"] else "inside"
        out["targets"][target] = {"label": label, "unit": unit, "observed": round(obs, 6), "low": round(exp["low"], 6),
                                  "mid": round(exp["mid"], 6), "high": round(exp["high"], 6), "position": where,
                                  "times_mid": round(obs / exp["mid"], 2) if exp["mid"] > 0 and obs > 0 else None}
    return out if out["targets"] else None
