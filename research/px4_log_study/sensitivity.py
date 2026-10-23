"""Robustness checks requested by the internal critical review (POST HOC: not declared before running).

S0  composition of the crash and normal samples (year, PX4 version, vehicle type, duration)
S1  between-drone vibration test restricted to controls with the same airframe as the case
S2  between-drone test without case flights from the crash day
S3  between-drone test by vibration measurement source
S4  Holm correction over every p-valued confirmatory test in the study
S5  screening value: how often the crashed drone is the roughest of its matched set
S6  flight duration of case versus control exposure flights (a possible confounder)
S7  within-drone test with the crash-moment tilt threshold at 45 and 75 degrees instead of 60

    python research/px4_log_study/sensitivity.py DATA_ROOT OUT_MD
DATA_ROOT holds dbinfo.json, within.csv and the downloaded logs (crash/, h/, within/).
"""
import csv
import gzip
import json
import os
import sys
from collections import Counter, defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "results", "px4_log_study")
CRASH = ("crash_sw_hw", "crash_pilot")


def null_p(ranks, sizes, draws=100_000, seed=0):
    if not ranks:
        return np.nan, np.nan, 0
    rng = np.random.default_rng(seed)
    null = np.zeros(draws)
    for n in sizes:
        null += rng.integers(0, n + 1, draws) / n
    null /= len(sizes)
    obs = float(np.mean(ranks))
    return obs, float((null >= obs).mean()), len(ranks)


def load_between():
    rows = [json.loads(line) for line in open(os.path.join(RES, "rough_drone_features.jsonl"))]
    sets = defaultdict(lambda: defaultdict(list))
    role = {}
    for r in rows:
        sets[r["set_id"]][r["vehicle"]].append(r)
        role[(r["set_id"], r["vehicle"])] = r["role"]
    return sets, role


def between(sets, role, keep_case=lambda r: True, keep_control=lambda sid, v: True, source=None, feature="vib_p95"):
    srck = {"vib_p95": "src_vib", "tune_rms": "src_tune"}[feature]

    def value(rs, flt):
        vals = defaultdict(list)
        for r in rs:
            f = r["features"]
            if f and f.get(feature) is not None and flt(r):
                vals[f.get(srck)].append(f[feature])
        return {s: float(np.median(v)) for s, v in vals.items() if len(v) >= 2}

    ranks, sizes, top = [], [], []
    for sid, vehicles in sets.items():
        case = [v for v in vehicles if role[(sid, v)] == "case"]
        if not case:
            continue
        for s, cv in value(vehicles[case[0]], keep_case).items():
            if source and s != source:
                break
            ctrl = [value(vehicles[v], lambda r: True).get(s) for v in vehicles
                    if role[(sid, v)] == "control" and keep_control(sid, v)]
            ctrl = [x for x in ctrl if x is not None]
            if ctrl:
                rank = sum(x < cv for x in ctrl) / len(ctrl)
                ranks.append(rank)
                sizes.append(len(ctrl))
                top.append(rank == 1.0)
            break
    obs, p, n = null_p(ranks, sizes)
    expected_top = float(np.mean([1 / (k + 1) for k in sizes])) if sizes else np.nan
    return obs, p, n, (float(np.mean(top)) if top else np.nan), expected_top


def main(root, out_md):
    raw = open(os.path.join(root, "dbinfo.json"), "rb").read()
    db = {x["log_id"]: x for x in json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)}
    L = ["# Robustness checks (post hoc)", "",
         "These checks were run after the declared tests, in response to an internal critical review. They are "
         "exploratory: none was declared in advance.", ""]

    # S0
    crashes = [x for x in db.values() if x["rating"] in CRASH]
    normal = [x for x in db.values() if x["rating"] in ("good", "great")]
    def comp(xs):
        real = [x for x in xs if "SITL" not in str(x.get("sys_hw"))]
        years = Counter((x["log_date"] or "")[:4] for x in real)
        ver = Counter((x.get("ver_sw_release") or "?").split(" ")[0][:5] for x in real)
        typ = Counter(x.get("mav_type") for x in real)
        dur = np.median([x.get("duration_s") or 0 for x in real])
        return len(real), years, ver, typ, dur
    L += ["## S0 Composition of the archive samples", "", "| | Crash-rated (real hardware) | Rated good/great (real hardware) |", "|---|---|---|"]
    a, b = comp(crashes), comp(normal)
    L.append(f"| Logs | {a[0]} | {b[0]} |")
    L.append(f"| Median duration (s) | {a[4]:.0f} | {b[4]:.0f} |")
    for label, i in (("Years (top 4)", 1), ("PX4 version (top 4)", 2), ("Vehicle type (top 3)", 3)):
        k = 3 if i == 3 else 4
        L.append(f"| {label} | " + ", ".join(f"{y} {c}" for y, c in a[i].most_common(k)) + " | "
                 + ", ".join(f"{y} {c}" for y, c in b[i].most_common(k)) + " |")

    # between-drone checks
    sets, role = load_between()
    airframe = {}
    for sid, vehicles in sets.items():
        for v, rs in vehicles.items():
            names = Counter(db[r["log_id"]].get("airframe_name") for r in rs if r["log_id"] in db)
            airframe[(sid, v)] = names.most_common(1)[0][0] if names else None
    within_rows = list(csv.DictReader(open(os.path.join(root, "within.csv"))))
    same_day = {r["log_id"] for r in within_rows if r["role"] == "earlier" and r["same_day"] == "1"}

    def case_of(sid):
        return next(v for v in sets[sid] if role[(sid, v)] == "case")

    L += ["", "## S1-S3, S5 Between-drone vibration test, variations", "",
          "| Variation | Matched sets | Mean scaled rank | One-sided p | Crashed drone roughest of its set | Expected if no difference |",
          "|---|---|---|---|---|---|"]
    variants = [
        ("As declared (all controls, all sources)", {}),
        ("S1 controls with the same airframe as the case", {"keep_control": lambda sid, v: airframe[(sid, v)] is not None
                                                             and airframe[(sid, v)] == airframe[(sid, case_of(sid))]}),
        ("S2 no case flights from the crash day", {"keep_case": lambda r: r["log_id"] not in same_day}),
        ("S3 PX4 accelerometer vibration metric only", {"source": "imu"}),
        ("S3 older-firmware estimator vibration only", {"source": "estimator_vibe"}),
    ]
    for name, kw in variants:
        obs, p, n, top, exp = between(sets, role, **kw)
        L.append(f"| {name} | {n} | {obs:.2f} | {p:.4f} | {top:.0%} | {exp:.0%} |")

    # S4 Holm
    tests = [("Settings: protections disabled, crash vs normal (Fisher)", 0.626),
             ("Held-out: clipping, aircraft- vs pilot-blamed", 0.045),
             ("Held-out: manual mode at the crash, pilot- vs aircraft-blamed", 0.165),
             ("Within-drone vibration", 0.6654), ("Within-drone rate tracking", 0.4658),
             ("Between-drone vibration", 0.0023), ("Between-drone rate tracking", 0.1453)]
    order = sorted(range(len(tests)), key=lambda i: tests[i][1])
    adj, running = {}, 0.0
    for k, i in enumerate(order):
        running = max(running, min(1.0, (len(tests) - k) * tests[i][1]))
        adj[i] = running
    L += ["", "## S4 Holm correction over the seven p-valued confirmatory tests", "", "| Test | p | Holm-adjusted p |", "|---|---|---|"]
    for i, (name, p) in enumerate(tests):
        L.append(f"| {name} | {p:.4f} | {adj[i]:.4f} |")

    # S6 duration
    dur = {"case": [], "control": []}
    for sid, vehicles in sets.items():
        for v, rs in vehicles.items():
            for r in rs:
                if r["log_id"] in db and r["features"]:
                    dur[role[(sid, v)]].append(db[r["log_id"]].get("duration_s") or 0)
    L += ["", "## S6 Duration of the exposure flights", "",
          f"Median duration: case flights {np.median(dur['case']):.0f} s (n = {len(dur['case'])}), control flights "
          f"{np.median(dur['control']):.0f} s (n = {len(dur['control'])})."]

    # S7 tilt threshold for the within-drone test
    sys.path.insert(0, HERE)
    import pilot_vs_drone as P
    import within_drone as W

    original = P.crash_time
    def make(th):
        def ct(u, t_arm, t_end, rotary):
            if not rotary:
                return t_end
            att, land = P.topic(u, "vehicle_attitude"), P.topic(u, "vehicle_land_detected")
            t_air = t_arm
            if land is not None:
                m = P.between(land, t_arm, t_end) & (land["landed"] == 0)
                if m.any():
                    t_air = land["timestamp"][m][0]
            if att is None:
                return t_end
            m = P.between(att, t_air, t_end)
            qx, qy = att["q[1]"][m], att["q[2]"][m]
            tilt = np.degrees(np.arccos(np.clip(1 - 2 * (qx ** 2 + qy ** 2), -1, 1)))
            over = np.where(tilt > th)[0]
            return att["timestamp"][m][over[0]] if len(over) else t_end
        return ct
    prior = [json.loads(line) for line in open(os.path.join(RES, "within_drone_features.jsonl"))]
    earlier = defaultdict(list)
    for r in prior:
        if r["role"] == "earlier" and r["features"]:
            earlier[r["crash_id"]].append(r["features"])
    L += ["", "## S7 Within-drone vibration test with a different crash-moment threshold", "",
          "| Tilt threshold | Drones | Mean scaled rank | One-sided p |", "|---|---|---|---|"]
    for th in (45, 60, 75):
        P.crash_time = make(th)
        W.__dict__.get("crash_time", None)
        ranks, sizes = [], []
        for r in [x for x in within_rows if x["role"] == "crash"]:
            path = next((os.path.join(root, d, r["log_id"] + ".ulg") for d in ("within", "crash", os.path.join("h", "crash"))
                         if os.path.exists(os.path.join(root, d, r["log_id"] + ".ulg"))), None)
            try:
                f = W.features(path, True) if path else None
            except Exception:
                f = None
            if not f or f.get("vib_p95") is None or np.isnan(f["vib_p95"]):
                continue
            ev = [e["vib_p95"] for e in earlier[r["log_id"]] if e.get("vib_p95") is not None and e.get("src_vib") == f.get("src_vib")]
            if len(ev) >= 3:
                ranks.append(sum(v < f["vib_p95"] for v in ev) / len(ev))
                sizes.append(len(ev))
        obs, p, n = null_p(ranks, sizes)
        L.append(f"| {th} deg{' (declared)' if th == 60 else ''} | {n} | {obs:.2f} | {p:.4f} |")
    P.crash_time = original
    open(out_md, "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main(*sys.argv[1:3])
