"""Within-drone test: was a crashed drone already vibrating more, or tracking its commands worse, than on its
own earlier flights?

PRE-DECLARED (committed before any of these logs were downloaded).

Why: crash flights differ from good flights well before the crash (leak_curve.md: AUC ~0.86 at 30 s before),
but the good flights are other drones. Comparing each drone with itself removes that difference.

Selection (`select`): uploader-rated crashes (crash_sw_hw / crash_pilot) on real hardware, PX4 v1.12 or newer,
with a vehicle id. For each, the same drone's flights that are not rated as crashes, are at least 30 s long and
are dated on or before the crash day; the 5 most recent are kept. A crash is used only if it has at least 3.
The order of flights on the same day as the crash is unknown, so they are included in the main test and left
out in a sensitivity check.

Features (leak_curve.window_features), on the window from the first airborne moment to 10 s before the crash
moment (crash log) or 10 s before the end of the armed period (earlier flights); windows under 10 s are dropped:
  primary:      vib_p95 (vibration), tune_rms (rate tracking error)
  exploratory:  clip_rate, sat_frac

Test, per feature: for each drone, the rank of the crash flight among its own flights (crash + earlier),
scaled to 0..1 (0 = lowest of all its flights, 1 = highest). With no change, the scaled rank is uniform, mean 0.5.
  H1 (vibration):     mean scaled rank of vib_p95 > 0.5
  H2 (tracking):      mean scaled rank of tune_rms > 0.5
One-sided p from 100,000 draws of the exact null (each drone's rank uniform over its own n+1 positions, ties
ignored); supported if p < 0.025 (0.05 split over H1 and H2). Also reported: share of drones whose crash flight
is above the median of its earlier flights, the same split by uploader label, and the same-day sensitivity check.

    python research/px4_log_study/within_drone.py select DBINFO_JSON OUT_CSV
    python research/px4_log_study/within_drone.py analyze SELECTION_CSV LOG_ROOT OUT_DIR
"""
import csv
import gzip
import json
import os
import sys
from collections import defaultdict

import numpy as np

CRASH = ("crash_sw_hw", "crash_pilot")
PRIMARY, EXPLORATORY = ["vib_p95", "tune_rms"], ["clip_rate", "sat_frac"]
MARGIN_S = 10


def version_ok(x):
    rel = (x.get("ver_sw_release") or "").split(" ")[0]
    try:
        major, minor = (int(p) for p in rel.lstrip("v").split(".")[:2])
    except ValueError:
        return False
    return (major, minor) >= (1, 12)


def select(src, out, keep=5, min_earlier=3):
    raw = open(src, "rb").read()
    rows = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
    real = [x for x in rows if "SITL" not in str(x.get("sys_hw")) and x.get("vehicle_uuid")]
    by_vehicle = defaultdict(list)
    for x in real:
        by_vehicle[x["vehicle_uuid"]].append(x)
    picked = []
    for c in real:
        if c["rating"] not in CRASH or not version_ok(c) or (c.get("duration_s") or 0) < 5:
            continue
        earlier = [y for y in by_vehicle[c["vehicle_uuid"]] if y["log_id"] != c["log_id"] and y["rating"] not in CRASH
                   and (y.get("duration_s") or 0) >= 30 and y["log_date"] <= c["log_date"] and version_ok(y)]
        earlier.sort(key=lambda y: y["log_date"], reverse=True)
        earlier = earlier[:keep]
        if len(earlier) >= min_earlier:
            picked.append((c, earlier))
    with open(out, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["role", "crash_id", "log_id", "rating", "log_date", "same_day", "vehicle_uuid", "download_url"])
        for c, earlier in picked:
            w.writerow(["crash", c["log_id"], c["log_id"], c["rating"], c["log_date"], "", c["vehicle_uuid"], c["download_url"]])
            for y in earlier:
                w.writerow(["earlier", c["log_id"], y["log_id"], y["rating"], y["log_date"], int(y["log_date"] == c["log_date"]),
                            c["vehicle_uuid"], y["download_url"]])
    print(f"{len(picked)} crashes with >= {min_earlier} earlier flights of the same drone; "
          f"{sum(len(e) for _, e in picked)} earlier flights")


def features(path, is_crash):
    from pyulog import ULog

    from leak_curve import TOPICS, window_features
    from pilot_vs_drone import armed_period, between, crash_time, topic

    u = ULog(path, message_name_filter_list=TOPICS)
    st = topic(u, "vehicle_status")
    per = armed_period(st) if st is not None else None
    if per is None:
        return None
    t_arm, t_end = per
    rotary = bool(st["is_rotary_wing"][-1]) if "is_rotary_wing" in st else True
    t_c = crash_time(u, t_arm, t_end, rotary) if is_crash else t_end
    land = topic(u, "vehicle_land_detected")
    t0 = t_arm
    if land is not None:
        m = between(land, t_arm, t_c) & (land["landed"] == 0)
        if m.any():
            t0 = land["timestamp"][m][0]
    b = t_c - MARGIN_S * 1e6
    if b - t0 < 10e6:
        return None
    return window_features(u, st, rotary, t0, b)


def rank_test(groups, feature, rng, draws=100_000):
    """groups: list of (crash_value, [earlier values]). Returns (n drones, mean scaled rank, p, share above median)."""
    ranks, sizes, above = [], [], []
    for cv, ev in groups:
        ev = [v for v in ev if v is not None and not np.isnan(v)]
        if cv is None or np.isnan(cv) or len(ev) < 3:
            continue
        n = len(ev)
        ranks.append(sum(v < cv for v in ev) / n)
        sizes.append(n)
        above.append(cv > np.median(ev))
    if not ranks:
        return 0, np.nan, np.nan, np.nan
    observed = float(np.mean(ranks))
    null = np.zeros(draws)
    for n in sizes:
        null += rng.integers(0, n + 1, draws) / n
    null /= len(sizes)
    return len(ranks), observed, float((null >= observed).mean()), float(np.mean(above))


def analyze(sel_csv, root, out_dir):
    rows = list(csv.DictReader(open(sel_csv)))
    feats, skipped = {}, 0
    for r in rows:
        path = None
        for sub in ("within", "crash", os.path.join("h", "crash")):
            p = os.path.join(root, sub, r["log_id"] + ".ulg")
            if os.path.exists(p) and os.path.getsize(p) > 10_000:
                path = p
                break
        try:
            f = features(path, r["role"] == "crash") if path else None
        except Exception:
            f = None
        skipped += f is None
        feats[(r["crash_id"], r["log_id"])] = f
    with open(os.path.join(out_dir, "within_drone_features.jsonl"), "w") as fh:
        for r in rows:
            f = feats[(r["crash_id"], r["log_id"])]
            fh.write(json.dumps({**r, "features": None if f is None else
                                 {k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in f.items()}}) + "\n")

    crashes = [r for r in rows if r["role"] == "crash"]
    rng = np.random.default_rng(0)

    def groups(feature, label=None, same_day=True):
        out = []
        for c in crashes:
            if label and {"crash_sw_hw": "drone", "crash_pilot": "pilot"}[c["rating"]] != label:
                continue
            cf = feats[(c["crash_id"], c["log_id"])]
            if cf is None:
                continue
            ev = [feats[(r["crash_id"], r["log_id"])] for r in rows
                  if r["role"] == "earlier" and r["crash_id"] == c["crash_id"] and (same_day or r["same_day"] == "0")]
            out.append((cf.get(feature), [e.get(feature) for e in ev if e is not None]))
        return out

    L = ["# Within-drone test: the crash flight against the same drone's earlier flights", "",
         f"Crashes selected: {len(crashes)}; logs that could not be read or had under 10 s before the cut-off: {skipped}. "
         f"Features on each flight up to {MARGIN_S} s before the crash (or before the end of an earlier flight). "
         "Declared in advance in `within_drone.py`.", "",
         "Scaled rank: 0 = the crash flight is the lowest of that drone's flights, 1 = the highest; 0.5 = no change.", "",
         "| Feature | Drones | Mean scaled rank | One-sided p | Crash flight above the drone's median | Result |", "|---|---|---|---|---|---|"]
    for f in PRIMARY + EXPLORATORY:
        n, mr, p, ab = rank_test(groups(f), f, rng)
        res = ("supported" if p < 0.025 else "not supported") if f in PRIMARY else "exploratory"
        L.append(f"| {f} | {n} | {mr:.2f} | {p:.4f} | {ab:.0%} | {res} |")
    L += ["", "## By uploader label", "", "| Feature | Label | Drones | Mean scaled rank | p |", "|---|---|---|---|---|"]
    for f in PRIMARY:
        for lab in ("drone", "pilot"):
            n, mr, p, _ = rank_test(groups(f, lab), f, rng)
            L.append(f"| {f} | {lab} | {n} | {mr:.2f} | {p:.4f} |")
    L += ["", "## Sensitivity: earlier flights from the crash day left out", "", "| Feature | Drones | Mean scaled rank | p |", "|---|---|---|---|"]
    for f in PRIMARY:
        n, mr, p, _ = rank_test(groups(f, same_day=False), f, rng)
        L.append(f"| {f} | {n} | {mr:.2f} | {p:.4f} |")
    L += ["", "## Limits", "",
          "- Uploader ratings; 'earlier' flights are the drone's own logs that were not rated as crashes (most are unrated).",
          "- A drone can be modified between flights (new propellers, a re-tune), which this test cannot see.",
          "- The crash flight is cut 10 s before the estimated crash moment; earlier flights 10 s before disarming."]
    open(os.path.join(out_dir, "within_drone.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    if sys.argv[1] == "select":
        select(*sys.argv[2:4])
    else:
        analyze(*sys.argv[2:5])
