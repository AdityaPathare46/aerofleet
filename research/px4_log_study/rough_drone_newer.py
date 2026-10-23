"""Rough-drone test on the newer vibration metric only: replication with every eligible newer-firmware drone.

DECLARED before any new log is downloaded (24 Oct 2026). Answers the paper's stated weakness that the between-drone
vibration result rests mainly on the older estimator estimate (48 sets) and the newer accelerometer metric had only
12 sets (rough_drone_test.py needed 3 earlier flights per crashed drone).

Cases: every real-hardware drone whose first crash-rated log runs PX4 1.11 or newer (the firmware that logs
vehicle_imu_status) and that has at least 1 earlier flight of 30 s or more not rated as a crash, dated on or before
the crash; its up to 3 most recent such flights are the exposure flights.
Controls: as in rough_drone_test.py: per case up to 2 drones with no crash-rated log, same flight-controller
hardware, PX4 major.minor and vehicle type, each with at least 3 flights of 30 s or more; 3 random flights each;
no control used twice. Seed 11.
Feature: vibration p95 from the accelerometer metric (source "imu") only; flights without it are dropped. A drone's
value is the median over its readable flights (at least 1).
Test: the case drone's scaled rank among its set, as before. H: mean scaled rank > 0.5, one-sided p from 100,000
draws of the exact null; supported if p < 0.025. Reported also for the sets not in the original test (new cases
only), descriptively.

    python research/px4_log_study/rough_drone_newer.py select DBINFO_JSON OUT_CSV
    python research/px4_log_study/rough_drone_newer.py analyze SETS_CSV LOG_ROOT OUT_MD [ORIGINAL_SETS_CSV]
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


def version(x):
    v = (x.get("ver_sw_release") or "").split(" ")[0].lstrip("v").split(".")
    try:
        return int(v[0]), int(v[1])
    except (ValueError, IndexError):
        return None


def select(dbinfo, out, per_case=2, flights=3, seed=11):
    raw = open(dbinfo, "rb").read()
    rows = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
    real = [x for x in rows if "SITL" not in str(x.get("sys_hw")) and x.get("vehicle_uuid")]
    by_vehicle = defaultdict(list)
    for x in real:
        by_vehicle[x["vehicle_uuid"]].append(x)
    crashed = {v for v, xs in by_vehicle.items() if any(x["rating"] in CRASH for x in xs)}
    pool = defaultdict(list)
    for v, xs in by_vehicle.items():
        if v in crashed:
            continue
        ok = sorted([x for x in xs if (x.get("duration_s") or 0) >= 30], key=lambda x: x["log_id"])
        if len(ok) >= flights:
            x0 = ok[0]
            pool[(x0["sys_hw"], version(x0), x0["mav_type"])].append((v, ok))
    rng = random.Random(seed)
    used, out_rows, n_sets = set(), [], 0
    for v in sorted(crashed):
        xs = by_vehicle[v]
        crash = min((x for x in xs if x["rating"] in CRASH), key=lambda x: (x["log_date"], x["log_id"]))
        ver = version(crash)
        if not ver or ver < (1, 11):
            continue
        earlier = sorted([x for x in xs if x["rating"] not in CRASH and x["log_date"] <= crash["log_date"]
                          and (x.get("duration_s") or 0) >= 30], key=lambda x: (x["log_date"], x["log_id"]), reverse=True)[:flights]
        if not earlier:
            continue
        cands = [p for p in pool[(crash["sys_hw"], ver, crash["mav_type"])] if p[0] not in used]
        if not cands:
            continue
        rng.shuffle(cands)
        n_sets += 1
        for x in earlier:
            out_rows.append([crash["log_id"], "case", v, x["log_id"], crash["rating"], x["download_url"]])
        for cv, logs in cands[:per_case]:
            used.add(cv)
            for x in rng.sample(logs, flights):
                out_rows.append([crash["log_id"], "control", cv, x["log_id"], "", x["download_url"]])
    with open(out, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["set_id", "role", "vehicle", "log_id", "rating", "download_url"])
        w.writerows(out_rows)
    print(f"{n_sets} matched sets; {len(out_rows)} flights; {len(used)} control drones")


def analyze(sets_csv, root, out_md, original_csv=None):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from within_drone import features

    rows = list(csv.DictReader(open(sets_csv)))
    vib, unread = {}, 0
    for r in rows:
        if r["log_id"] in vib:
            continue
        path = next((os.path.join(root, d, r["log_id"] + ".ulg") for d in ("newer", "within", "rough", "crash", os.path.join("h", "crash"))
                     if os.path.exists(os.path.join(root, d, r["log_id"] + ".ulg"))), None)
        try:
            f = features(path, False) if path else None
        except Exception:  # noqa: BLE001
            f = None
        ok = f is not None and f.get("src_vib") == "imu" and not np.isnan(f["vib_p95"])
        vib[r["log_id"]] = f["vib_p95"] if ok else None
        unread += f is None
    sets = defaultdict(lambda: defaultdict(list))
    role = {}
    for r in rows:
        if vib.get(r["log_id"]) is not None:
            sets[r["set_id"]][r["vehicle"]].append(vib[r["log_id"]])
        role[(r["set_id"], r["vehicle"])] = r["role"]
    original = set()
    if original_csv and os.path.exists(original_csv):
        original = {r["vehicle"] for r in csv.DictReader(open(original_csv)) if r["role"] == "case"}
    case_vehicle = {r["set_id"]: r["vehicle"] for r in rows if r["role"] == "case"}

    def test(only_new=False, draws=100_000, seed=0):
        ranks, sizes = [], []
        for sid, vs in sets.items():
            cv = case_vehicle[sid]
            if cv not in vs or (only_new and cv in original):
                continue
            ctrl = [float(np.median(x)) for v, x in vs.items() if role[(sid, v)] == "control"]
            if not ctrl:
                continue
            c = float(np.median(vs[cv]))
            ranks.append(sum(x < c for x in ctrl) / len(ctrl))
            sizes.append(len(ctrl))
        if not ranks:
            return 0, float("nan"), float("nan"), (float("nan"),) * 2
        rng = np.random.default_rng(seed)
        null = np.zeros(draws)
        for n in sizes:
            null += rng.integers(0, n + 1, draws) / n
        null /= len(sizes)
        obs = float(np.mean(ranks))
        boot = [np.mean(rng.choice(ranks, len(ranks))) for _ in range(10_000)]
        return len(ranks), obs, float((null >= obs).mean()), tuple(np.percentile(boot, [2.5, 97.5]))

    n, mr, p, ci = test()
    n2, mr2, p2, ci2 = test(only_new=True)
    L = ["# Rough-drone test, newer accelerometer vibration metric only (replication)", "",
         f"Declared in `rough_drone_newer.py`. Matched sets selected: {len(set(case_vehicle))}; flights that could not be read: {unread}.", "",
         "| Sets | Matched sets used | Mean scaled rank | 95% CI | One-sided p | Result |", "|---|---|---|---|---|---|",
         f"| All eligible newer-firmware drones | {n} | {mr:.2f} | {ci[0]:.2f}-{ci[1]:.2f} | {p:.4f} | {'supported' if p < 0.025 else 'not supported'} |",
         f"| Only cases not in the original test (descriptive) | {n2} | {mr2:.2f} | {ci2[0]:.2f}-{ci2[1]:.2f} | {p2:.4f} | -- |"]
    open(out_md, "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    if sys.argv[1] == "select":
        select(*sys.argv[2:4])
    else:
        analyze(*sys.argv[2:6])
