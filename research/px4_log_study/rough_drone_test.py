"""Rough-drone test: are drones that crash already rougher on their normal flights than comparable drones
that did not crash?

PRE-DECLARED (committed before any control log was downloaded).

Why: crash flights differ from good flights (leak_curve.md) but not from the same drone's earlier flights
(within_drone.md). So the difference is between drones. If drones that later crash are rougher on their
ordinary flights than matched drones that did not, a fleet tool can flag the roughest drones in advance.

Cases: the 101 crashed drones of within_drone.py. Exposure flights: the crashed drone's 3 most recent flights
before the crash that are not rated as crashes (already downloaded for within_drone.py).
Controls: for each case, 2 drones with no crash-rated log at all, the same flight-controller hardware (sys_hw),
the same PX4 version (major.minor) and the same vehicle type, each with at least 3 flights of 30 s or more;
3 of their flights chosen at random. Fewer controls are used where fewer match; a case with none is dropped.
Seed 7.

Features per flight (within_drone.features: from first airborne to 10 s before disarming, with the older-firmware
fallbacks); a drone's value is the median over its 3 flights. Within each matched set, a value is used only if it
comes from the same measurement source for the case and the control.

Test, per feature: within each matched set, the case drone's rank among the set (case + controls), scaled to 0..1.
With no difference the scaled rank is uniform, mean 0.5.
  H1 vibration (vib_p95):  mean scaled rank > 0.5
  H2 tracking (tune_rms):  mean scaled rank > 0.5
One-sided p from 100,000 draws of the exact null; supported if p < 0.025. Also by uploader label (descriptive).
Limit stated up front: "no crash-rated log" does not mean the control never crashed (most logs are unrated).

    python research/px4_log_study/rough_drone_test.py select DBINFO_JSON WITHIN_CSV OUT_CSV
    python research/px4_log_study/rough_drone_test.py analyze SETS_CSV LOG_ROOT OUT_DIR
"""
import csv
import gzip
import json
import os
import random
import sys
from collections import defaultdict

import numpy as np

CRASH = ("crash_sw_hw", "crash_pilot")
FEATURES = ["vib_p95", "tune_rms"]
SRC = {"vib_p95": "src_vib", "tune_rms": "src_tune"}


def vkey(x):
    return ".".join((x.get("ver_sw_release") or "").split(" ")[0].lstrip("v").split(".")[:2])


def select(dbinfo, within_csv, out, per_case=2, flights=3, seed=7):
    raw = open(dbinfo, "rb").read()
    rows = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
    real = [x for x in rows if "SITL" not in str(x.get("sys_hw")) and x.get("vehicle_uuid")]
    by_vehicle = defaultdict(list)
    for x in real:
        by_vehicle[x["vehicle_uuid"]].append(x)
    crashed = {v for v, xs in by_vehicle.items() if any(x["rating"] in CRASH for x in xs)}
    index = {x["log_id"]: x for x in real}
    pool = defaultdict(list)            # (sys_hw, version, mav_type) -> control vehicles
    for v, xs in by_vehicle.items():
        if v in crashed:
            continue
        ok = [x for x in xs if (x.get("duration_s") or 0) >= 30]
        if len(ok) >= flights:
            x0 = ok[0]
            pool[(x0["sys_hw"], vkey(x0), x0["mav_type"])].append((v, ok))
    within = list(csv.DictReader(open(within_csv)))
    rng = random.Random(seed)
    used, out_rows, n_sets = set(), [], 0
    for c in [r for r in within if r["role"] == "crash"]:
        cx = index[c["log_id"]]
        earlier = sorted([r for r in within if r["role"] == "earlier" and r["crash_id"] == c["crash_id"]],
                         key=lambda r: r["log_date"], reverse=True)[:flights]
        cands = [p for p in pool[(cx["sys_hw"], vkey(cx), cx["mav_type"])] if p[0] not in used]
        if not cands:
            continue
        rng.shuffle(cands)
        controls = cands[:per_case]
        n_sets += 1
        for r in earlier:
            out_rows.append([c["crash_id"], "case", cx["vehicle_uuid"], r["log_id"], cx["rating"], r["download_url"]])
        for v, logs in controls:
            used.add(v)
            for x in rng.sample(logs, flights):
                out_rows.append([c["crash_id"], "control", v, x["log_id"], "", x["download_url"]])
    with open(out, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["set_id", "role", "vehicle", "log_id", "rating", "download_url"])
        w.writerows(out_rows)
    print(f"{n_sets} matched sets; {sum(1 for r in out_rows if r[1] == 'control')} control flights from "
          f"{len(used)} control drones")


def analyze(sets_csv, root, out_dir):
    from within_drone import features

    rows = list(csv.DictReader(open(sets_csv)))
    feats, skipped = {}, 0
    for r in rows:
        if r["log_id"] in feats:
            continue
        path = next((os.path.join(root, d, r["log_id"] + ".ulg") for d in ("within", "rough", "crash", os.path.join("h", "crash"))
                     if os.path.exists(os.path.join(root, d, r["log_id"] + ".ulg"))), None)
        try:
            feats[r["log_id"]] = features(path, False) if path else None
        except Exception:
            feats[r["log_id"]] = None
        skipped += feats[r["log_id"]] is None
    with open(os.path.join(out_dir, "rough_drone_features.jsonl"), "w") as fh:
        for r in rows:
            f = feats.get(r["log_id"])
            fh.write(json.dumps({**r, "features": None if f is None else
                                 {k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in f.items()}}) + "\n")

    sets = defaultdict(lambda: defaultdict(list))      # set -> vehicle -> rows
    roles, labels = {}, {}
    for r in rows:
        sets[r["set_id"]][r["vehicle"]].append(r)
        roles[(r["set_id"], r["vehicle"])] = r["role"]
        if r["role"] == "case":
            labels[r["set_id"]] = {"crash_sw_hw": "drone", "crash_pilot": "pilot"}.get(r["rating"])

    def drone_value(rs, feature):
        vals = {}
        for r in rs:
            f = feats.get(r["log_id"])
            if f is not None and f.get(feature) is not None and not np.isnan(f[feature]):
                vals.setdefault(f.get(SRC[feature]), []).append(f[feature])
        return {s: float(np.median(v)) for s, v in vals.items() if len(v) >= 2}

    def test(feature, label=None, draws=100_000, seed=0):
        ranks, sizes = [], []
        for sid, vehicles in sets.items():
            if label and labels.get(sid) != label:
                continue
            case = [v for v in vehicles if roles[(sid, v)] == "case"]
            if not case:
                continue
            cv = drone_value(vehicles[case[0]], feature)
            for src, cval in cv.items():
                ctrl = [drone_value(vehicles[v], feature).get(src) for v in vehicles if roles[(sid, v)] == "control"]
                ctrl = [x for x in ctrl if x is not None]
                if ctrl:
                    ranks.append(sum(x < cval for x in ctrl) / len(ctrl))
                    sizes.append(len(ctrl))
                break
        if not ranks:
            return 0, np.nan, np.nan
        rng = np.random.default_rng(seed)
        null = np.zeros(draws)
        for n in sizes:
            null += rng.integers(0, n + 1, draws) / n
        null /= len(sizes)
        obs = float(np.mean(ranks))
        return len(ranks), obs, float((null >= obs).mean())

    L = ["# Rough-drone test: crashed drones against matched drones that did not crash", "",
         f"Matched sets: {len(sets)}; flights that could not be read or were too short: {skipped}. A drone's value is the "
         "median over its 3 flights (crashed drones: flights before the crash). Controls match the case on flight-controller "
         "hardware, PX4 version and vehicle type. Declared in advance in `rough_drone_test.py`.", "",
         "Scaled rank: 1 = the crashed drone is rougher than all its matched controls, 0 = smoother than all; 0.5 = no difference.", "",
         "| Feature | Matched sets used | Mean scaled rank | One-sided p | Result |", "|---|---|---|---|---|"]
    for f in FEATURES:
        n, mr, p = test(f)
        L.append(f"| {f} | {n} | {mr:.2f} | {p:.4f} | {'supported' if p < 0.025 else 'not supported'} |")
    L += ["", "## By uploader label", "", "| Feature | Label | Sets | Mean scaled rank | p |", "|---|---|---|---|---|"]
    for f in FEATURES:
        for lab in ("drone", "pilot"):
            n, mr, p = test(f, lab)
            L.append(f"| {f} | {lab} | {n} | {mr:.2f} | {p:.4f} |")
    L += ["", "## Limits", "",
          "- Controls have no crash-rated log, which does not prove they never crashed (most logs are unrated).",
          "- Matching is on hardware, firmware and vehicle type only; frames, propellers, payloads and use differ.",
          "- Uploader-rated crashes come from people who rate their logs, which may not represent all operators."]
    open(os.path.join(out_dir, "rough_drone.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    if sys.argv[1] == "select":
        select(*sys.argv[2:5])
    else:
        analyze(*sys.argv[2:5])
