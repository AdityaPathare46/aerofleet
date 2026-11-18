"""Build the public-flight reference the app compares a user's flights and settings with.

    AEROFLEET_PX4_DATA="/Volumes/One Touch/AeroFleet_px4_data" python tools/build_public_reference.py

What it is: a description of ordinary public PX4 flights, not a test and not a safety limit. From the logs of the
public PX4 Flight Review archive already downloaded for the study, it keeps those whose pilot rated the flight good or
great, from real hardware (hardware name without "SITL", the study's rule), from vehicles with no crash-rated log
anywhere in the archive (so the reference is ordinary flying, and never contains the demo fleet's own drones), at most
PER_VEHICLE flights per vehicle so that no single airframe dominates. Each log is read with AeroFleet's own reader (aerofleet/assurance/flightlog.py) and
vibration is computed exactly as for an uploaded flight (aerofleet/assurance/vibration.py: 95th percentile, last 10 s
left out), so a user's flight is compared like with like. For the safety-critical PX4 settings (drift.py CRITICAL) it
counts how often each value appears.

Output: aerofleet/assurance/data/public_reference.json (derived numbers only: no log, identifier or location).
Why it helps: the in-fleet comparison needs at least four drones with the same measurement; a small operator has none.
What it does not say: a flight above most public flights is not shown to be at risk (the study found vibration was not a
validated screen), and a setting most public pilots use is not shown to be safer (settings did not differ between crash
and normal flights). The app says both next to the numbers.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import os
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATA = os.environ.get("AEROFLEET_PX4_DATA", "/Volumes/One Touch/AeroFleet_px4_data")
FOLDERS = ("control", "screen_ref", "newer", "within", "rough", "h/normal")
GOOD = {"good", "great"}
PER_VEHICLE = 5
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "aerofleet", "assurance", "data", "public_reference.json")
MIN_GROUP = 30            # fewer flights than this in a group: not stored, too few to describe


def one(path: str):
    """(vibration dict or None, vehicle kind, {critical setting: value}) for one log, or None if unreadable."""
    from aerofleet.assurance.drift import CRITICAL, severity_of
    from aerofleet.assurance.flightlog import MULTIROTORS, FlightLogError, read_flight_log
    from aerofleet.assurance.vibration import flight_vibration

    try:
        f = read_flight_log(path)
    except (FlightLogError, Exception):  # noqa: BLE001 - a public log the reader cannot use is skipped
        return None
    kind = "multirotor" if f.vehicle in MULTIROTORS else (f.vehicle or "unknown")
    v = flight_vibration(f)
    settings = {k: v_ for k, v_ in f.params.items() if severity_of(k) == CRITICAL}
    return (v, kind, settings)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    index = {r["log_id"]: r for r in json.load(gzip.open(os.path.join(DATA, "dbinfo.json")))}
    crashed = {r["vehicle_uuid"] for r in index.values() if str(r.get("rating", "")).startswith("crash") and r.get("vehicle_uuid")}
    per_vehicle = collections.defaultdict(list)
    for folder in FOLDERS:
        d = os.path.join(DATA, folder)
        for name in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            r = index.get(name[:-4])
            if (name.endswith(".ulg") and not name.startswith("._") and r and r.get("rating") in GOOD
                    and "SITL" not in str(r.get("sys_hw")).upper() and r.get("vehicle_uuid") and r["vehicle_uuid"] not in crashed):
                per_vehicle[r["vehicle_uuid"]].append(os.path.join(d, name))
    rng = random.Random(42)                                   # fixed seed: the same reference on every run
    paths, vehicle_of = [], {}
    for veh, ps in sorted(per_vehicle.items()):
        ps = sorted(set(ps), key=os.path.basename)
        for p in (rng.sample(ps, PER_VEHICLE) if len(ps) > PER_VEHICLE else ps):
            paths.append(p)
            vehicle_of[p] = veh
    print(f"{len(paths)} flights of {len(per_vehicle)} vehicles to read", flush=True)

    vib = collections.defaultdict(list)                       # (source, kind) -> [(p95, vehicle)]
    settings = collections.defaultdict(collections.Counter)
    n_settings_logs, read = 0, 0
    with ProcessPoolExecutor(a.workers) as pool:
        for i, (p, res) in enumerate(zip(paths, pool.map(one, paths, chunksize=4)), 1):
            if i % 100 == 0:
                print(f"  {i}/{len(paths)}", flush=True)
            if res is None:
                continue
            read += 1
            v, kind, s = res
            if v and v.get("source"):
                vib[(v["source"], kind)].append((v["p95"], vehicle_of[p]))
            if s:
                n_settings_logs += 1
                for k, x in s.items():
                    settings[k][f"{x:g}"] += 1

    import numpy as np

    groups = {}
    for (source, kind), vals in sorted(vib.items()):
        if len(vals) < MIN_GROUP:
            continue
        xs = np.array([x for x, _ in vals])
        groups[f"{source}|{kind}"] = {"source": source, "vehicle": kind, "flights": len(xs), "vehicles": len({v for _, v in vals}),
                                      "percentiles": [float(f"{q:.4g}") for q in np.percentile(xs, range(101))]}
    common = {k: {"logs": sum(c.values()), "values": dict(c.most_common(12))} for k, c in sorted(settings.items())
              if sum(c.values()) >= MIN_GROUP}
    out = {"made": date.today().isoformat(), "archive": "PX4 Flight Review public archive (review.px4.io)",
           "selection": f"logs rated good or great, real hardware, vehicles with no crash-rated log, at most {PER_VEHICLE} per vehicle, "
                        "read with AeroFleet's reader",
           "logs_read": read, "logs_selected": len(paths), "vehicles": len(per_vehicle),
           "vibration": groups, "settings_logs": n_settings_logs, "settings": common}
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    print(f"wrote {OUT}: {read} of {len(paths)} logs read; vibration groups "
          + ", ".join(f"{k} ({g['flights']} flights, {g['vehicles']} vehicles)" for k, g in groups.items())
          + f"; {len(common)} settings from {n_settings_logs} logs")


if __name__ == "__main__":
    main()
