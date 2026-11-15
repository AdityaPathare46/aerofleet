"""Fill a demo fleet with real public PX4 flights, so the app has something true to show.

    AEROFLEET_PX4_DATA="/Volumes/One Touch/AeroFleet_px4_data" python tools/seed_demo_fleet.py            # fleet "demo"
    python tools/seed_demo_fleet.py --fleet demo --drones 8 --flights 8 --reset

What it does: takes drones from the study's within-drone selection (`within.csv`: airframes with one crash-rated
flight and their earlier flights, from the public PX4 Flight Review archive), and passes each log through the same
code path as an upload in the app (`review_flight`, with no mission file). Every review lands in the signed record.

No fleet baseline is set: these are unrelated public drones, not one operator's fleet, so comparing their settings
with one another would show differences that mean nothing. For the settings check the script writes two files for
one drone into `<data>/demo_files/`: `<drone>_approved.params` (the settings in its first flight, unchanged) and
`<drone>_changed.params` (the same with one failsafe switched off and one tuning value changed BY THIS SCRIPT, to show
what the check reports). The presenter sets the first as the baseline of a fresh fleet and uploads the second.
It also writes three made-up missions (`SURVEY-A/B/C.waypoints`; A and B cross) for the conflict and wind checks.

What it is not: a test or a result. Nothing here is measured or claimed; it only loads data for a demonstration.
The logs stay where they are and are not copied into the repository. The uploader's crash rating is NOT given to the
tool (the tool names no cause). It is printed here and written to a presenter's key outside the repository, so
whoever gives the demonstration knows which flight the uploader rated a crash.

Run it from the repository root so it reads the same settings (.env, DATABASE_URL) as the API, with the API idle. `--reset` removes this fleet's rows first; the signed record is append-only and is never rewritten.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import os
import sys
from datetime import datetime
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATA = os.environ.get("AEROFLEET_PX4_DATA", "/Volumes/One Touch/AeroFleet_px4_data")
SEEDER = SimpleNamespace(username="demo-seed")


def pick(n_drones: int, n_flights: int):
    """Airframes with the most downloaded flights: each as (vehicle, [(log_id, date, role, rating, path)] oldest first)."""
    have = {}
    for d in ("within", "crash"):
        folder = os.path.join(DATA, d)
        for f in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
            if f.endswith(".ulg") and not f.startswith("._"):
                have.setdefault(f[:-4], os.path.join(folder, f))
    by = collections.defaultdict(dict)
    for r in csv.DictReader(open(os.path.join(DATA, "within.csv"))):
        if r["log_id"] in have:
            by[r["vehicle_uuid"].lower()].setdefault(r["log_id"], (r["log_id"], r["log_date"], r["role"], r["rating"], have[r["log_id"]]))
    fleets = []
    for vehicle, logs in sorted(by.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        flights = sorted(logs.values(), key=lambda x: (x[1], x[2] == "crash"))
        crash = [f for f in flights if f[2] == "crash"][-1:]
        earlier = [f for f in flights if f[2] != "crash"][-(n_flights - len(crash)):]
        if len(earlier) >= 3:
            fleets.append((vehicle, earlier + crash))
        if len(fleets) == n_drones:
            break
    return fleets


FAILSAFES = ("NAV_RCL_ACT", "NAV_DLL_ACT", "COM_LOW_BAT_ACT", "GF_ACTION")       # 0 switches the action off
TUNING = ("MC_ROLLRATE_P", "MC_PITCHRATE_P", "MC_ROLL_P")


def demo_param_files(drone: str, params: dict, folder: str):
    """The drone's real settings, and a copy with one failsafe switched off and one tuning value raised by a fifth."""
    os.makedirs(folder, exist_ok=True)
    changed, what = dict(params), []
    off = next((n for n in FAILSAFES if params.get(n)), None)
    if off:
        changed[off] = 0.0
        what.append(f"{off} {params[off]:g} -> 0")
    tune = next((n for n in TUNING if params.get(n)), None)
    if tune:
        changed[tune] = round(params[tune] * 1.2, 4)
        what.append(f"{tune} {params[tune]:g} -> {changed[tune]:g}")
    paths = [os.path.join(folder, f"{drone}_{name}.params") for name in ("approved", "changed")]
    for path, values in zip(paths, (params, changed)):
        with open(path, "w") as f:
            f.writelines(f"{k},{v:g}\n" for k, v in sorted(values.items()))
    return paths[0], paths[1], "; ".join(what) or "nothing to change in this log"


def demo_missions(folder: str):
    """Three made-up missions over Pune for the conflict and wind checks: two cross at the same height, one is clear."""
    from aerofleet.integrations.mission_planner import build_waypoint_file

    os.makedirs(folder, exist_ok=True)
    legs = {"SURVEY-A": (18.5200, 73.8500, 18.5290, 73.8600), "SURVEY-B": (18.5290, 73.8500, 18.5200, 73.8600),
            "SURVEY-C": (18.5400, 73.8700, 18.5480, 73.8780)}
    for name, (la0, lo0, la1, lo1) in legs.items():
        with open(os.path.join(folder, f"{name}.waypoints"), "w") as f:
            f.write(build_waypoint_file({"origin_lat": la0, "origin_lon": lo0, "dest_lat": la1, "dest_lon": lo1, "altitude_m": 60.0}))
    return sorted(legs)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fleet", default="demo")
    ap.add_argument("--drones", type=int, default=8)
    ap.add_argument("--flights", type=int, default=8)
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--key", default=os.path.join(DATA, "demo_fleet_key.json"), help="presenter's key (kept outside the repository)")
    a = ap.parse_args()

    from fastapi import HTTPException

    from aerofleet.api.routes.assurance import review_flight
    from aerofleet.data.database import get_session, init_db
    from aerofleet.data.models.models import FleetBaseline, FlightReview, ParamSnapshot

    init_db()
    db = get_session()
    if a.reset:
        for model in (FlightReview, ParamSnapshot):
            db.query(model).filter(model.fleet == a.fleet).delete()
        db.query(FleetBaseline).filter(FleetBaseline.fleet == a.fleet).delete()
        db.commit()
    key, files = [], None
    for i, (vehicle, flights) in enumerate(pick(a.drones, a.flights), 1):
        drone = f"PX4-{i:02d}"
        for log_id, date, role, rating, path in flights:
            try:
                out = review_flight(db, SEEDER, a.fleet, drone, None, "", open(path, "rb").read(), f"{log_id}.ulg")
            except HTTPException as e:                      # a public log the reader cannot use: say so and go on
                print(f"  {drone} {log_id} skipped: {e.detail}")
                db.rollback()
                continue
            vib = out["report"].get("vibration") or {}
            print(f"  {drone} {date} {role:7s} review #{out['id']} vibration {vib.get('p95')} ({vib.get('source')})")
            key.append({"drone": drone, "vehicle_uuid": vehicle, "review_id": out["id"], "log_id": log_id, "log_date": date,
                        "role": role, "uploader_rating": rating or None})
            if files is None and out["report"]["log"]["param_count"]:
                snap = (db.query(ParamSnapshot).filter(ParamSnapshot.fleet == a.fleet, ParamSnapshot.drone_id == drone)
                        .order_by(ParamSnapshot.id.desc()).first())
                files = demo_param_files(drone, snap.params, os.path.join(DATA, "demo_files"))
    json.dump({"fleet": a.fleet, "made": datetime.utcnow().isoformat(), "note": "Uploader ratings are labels from the public "
               "archive, not findings. The tool is never given them.", "flights": key}, open(a.key, "w"), indent=1)
    crashed = sorted({k["drone"] for k in key if k["role"] == "crash"})
    print(f"\n{len(key)} flights of {len({k['drone'] for k in key})} drones loaded into fleet '{a.fleet}'.")
    print(f"Drones whose last flight the uploader rated a crash: {', '.join(crashed) or 'none'}")
    print(f"Presenter's key: {a.key}")
    print(f"Made-up missions for the conflict and wind checks: {', '.join(demo_missions(os.path.join(DATA, 'demo_files')))} (.waypoints)")
    if files:
        print(f"Settings files for the drift check: {files[0]} (approved), {files[1]} (changed: {files[2]})")


if __name__ == "__main__":
    main()
