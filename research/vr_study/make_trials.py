"""Make the trial flights for the VR debrief study (see research/vr_study/PROTOCOL.md).

Same method as the injection experiment (research/px4_log_study/injection_reconcile.py): real PX4 multirotor flights
from the crash study's normal flights (h/normal), each at least 120 s airborne with an estimator position; the plan
is built from the flight itself (a waypoint every 5 s, where the check gave no false alarms on 40 flights), and a
known deviation is injected for 30 s with 3 s ramps.

The first 30 usable flights in file-name order are used. Each gets one of five versions, so every version appears
6 times: unchanged; sideways 15 m or 35 m (left or right of the direction of travel); upward 8 m or 20 m. The window
is centred at a random point between 25% and 75% of the airborne time, so the participant has to look for it.
Flights are split into two sets of 15 (A and B, three of each version per set). Three more flights (31-33) make a
practice set P, one per answer (unchanged, sideways 50 m, upward 30 m), with the answer shown after each; practice
answers are not analysed. Everything is seeded (seed 2026).

Writes:
  aerofleet/assurance/data/vr_study_trials.json   what the app shows: plan and flown track, no answers
  research/vr_study/trials_key.json               the answers, never sent to the app

    python research/vr_study/make_trials.py [LOG_DIR]
"""
from __future__ import annotations

import json
import os
import random
import sys
from glob import glob

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "research", "px4_log_study"))
os.environ["WP_EVERY_S"] = "5"

from aerofleet.assurance.flightlog import FlightLogError, read_flight_log  # noqa: E402
import injection_reconcile as inj  # noqa: E402

LOG_DIR = "/Volumes/One Touch/AeroFleet_px4_data/h/normal"
VERSIONS = [("none", 0.0), ("sideways", 15.0), ("sideways", 35.0), ("height", 8.0), ("height", 20.0)]
N_FLIGHTS = 30
PRACTICE = [("none", 0.0), ("sideways", 50.0), ("height", 30.0)]
SEED = 2026


def main(log_dir: str = LOG_DIR) -> None:
    flights = []
    for path in sorted(glob(os.path.join(log_dir, "*.ulg"))):
        if os.path.basename(path).startswith("._"):
            continue
        try:
            f = read_flight_log(path)
        except (FlightLogError, Exception):  # noqa: BLE001
            continue
        if f.vehicle not in (None, "quadcopter", "hexacopter", "octocopter") or f.position_source != "vehicle_global_position":
            continue
        air = [p for p in f.track if p[3] > 2.0]
        if len(air) < 50 or air[-1][0] - air[0][0] < 120:
            continue
        flights.append((os.path.basename(path)[:-4], air))
        if len(flights) >= N_FLIGHTS + len(PRACTICE):
            break
    practice, flights = flights[N_FLIGHTS:], flights[:N_FLIGHTS]
    if len(flights) < N_FLIGHTS or len(practice) < len(PRACTICE):
        sys.exit(f"only {len(flights)} usable flights")
    rng = random.Random(SEED)
    versions = VERSIONS * (N_FLIGHTS // len(VERSIONS))
    rng.shuffle(versions)
    # Balance the sets: each set gets three of each version.
    by_version = {}
    for i, v in enumerate(versions):
        by_version.setdefault(v, []).append(i)
    set_of = {}
    for v, idx in by_version.items():
        for k, i in enumerate(idx):
            set_of[i] = "A" if k % 2 == 0 else "B"

    shown, key = {"A": [], "B": [], "P": []}, {}
    counter = {"A": 0, "B": 0, "P": 0}
    for j, v in enumerate(PRACTICE):
        set_of[N_FLIGHTS + j] = "P"
    for i, ((log_id, air), (kind, size)) in enumerate(zip(flights + practice, versions + PRACTICE)):
        s = set_of[i]
        counter[s] += 1
        tid = f"{s}{counter[s]:02d}"
        t0, t1 = air[0][0], air[-1][0]
        mid = t0 + (t1 - t0) * rng.uniform(0.25, 0.75)
        a, b = mid - inj.WINDOW_S / 2, mid + inj.WINDOW_S / 2
        side = rng.choice([-1.0, 1.0])
        flown = inj.inject(air, a, b, sideways=side * size if kind == "sideways" else 0.0, up=size if kind == "height" else 0.0)
        plan = inj.plan_from(air)
        thin, last = [], None
        for t, la, lo, h in flown:                      # about one point a second
            if last is None or t - last >= 1.0:
                thin.append([round(t - t0, 1), round(la, 7), round(lo, 7), round(h, 1)])
                last = t
        shown[s].append({"id": tid, "flight_s": round(t1 - t0, 1),
                         "replay": {"home": [round(air[0][1], 7), round(air[0][2], 7)],
                                    "planned": [[round(la, 7), round(lo, 7), round(h, 1)] for la, lo, h in plan.path],
                                    "flown": thin}})
        if s == "P":
            shown[s][-1]["answer"] = kind               # practice only: the answer is shown after the guess
        key[tid] = {"answer": kind, "size_m": size, "side": ("left" if side > 0 else "right") if kind == "sideways" else None,
                    "window_s": [round(a - t0, 1), round(b - t0, 1)], "log_id": log_id}
    for s in shown:
        shown[s].sort(key=lambda x: x["id"])
    out = os.path.join(ROOT, "aerofleet", "assurance", "data", "vr_study_trials.json")
    json.dump({"made_by": "research/vr_study/make_trials.py", "answers": ["none", "sideways", "height"], "sets": shown},
              open(out, "w"), separators=(",", ":"))
    json.dump(key, open(os.path.join(ROOT, "research", "vr_study", "trials_key.json"), "w"), indent=1)
    print(f"{sum(len(v) for v in shown.values())} trials -> {out}")
    for s in ("A", "B"):
        print(s, sorted((key[t['id']]['answer'], key[t['id']]['size_m']) for t in shown[s]))


if __name__ == "__main__":
    main(*sys.argv[1:2])
