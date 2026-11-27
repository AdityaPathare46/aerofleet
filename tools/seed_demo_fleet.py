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
what the check reports). It then prepares the fleet `<fleet>-settings` with the first as its approved baseline and the
second uploaded for that drone, because setting a baseline needs an operator account and the demo should not depend
on one. The presenter can still repeat it by hand with an operator account.
It also writes three made-up missions (`SURVEY-A/B/C.waypoints`; A and B cross) for the conflict and wind checks,
and five in `route_check/` around Pune for the airspace route check, one per outcome (see ROUTE_CHECK).

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


# Made-up spraying and mapping jobs around Pune for the airspace route check, one per outcome.
ROUTE_CHECK = {   # spraying is flown a few metres above the crop; mapping flights higher
    "SPRAY-FIELD-A": ((18.455, 73.795), (18.445, 73.810), 5.0),    # green, low: clear
    "SPRAY-FIELD-B": ((18.445, 73.795), (18.455, 73.810), 5.0),    # green, but crosses job A at the same height and time
    "SPRAY-NEAR-AIRPORT": ((18.520, 73.850), (18.529, 73.860), 5.0),   # inside the airport's yellow zone: needs ATC permission
    "SPRAY-NEAR-CANTONMENT": ((18.500, 73.870), (18.515, 73.895), 5.0), # inside the cantonment's red zone: not permitted
    "CROP-MAP-150M": ((18.600, 73.750), (18.605, 73.756), 150.0),       # crop-health mapping planned at 150 m: above the limit
}


# Demo registrations, so the readiness board shows each registration rule once. The UINs are labelled DEMO and are not
# real Digital Sky numbers: PX4-05 has none (do not fly), PX4-07's is recorded but not verified (check first).
DEMO_UIN = {f"PX4-{i:02d}": ("VERIFIED" if i != 7 else "RECORDED") for i in range(1, 9) if i != 5}


def seed_registrations(db, drones) -> None:
    from aerofleet.data.models.models import DroneRegistration

    for d in drones:
        db.query(DroneRegistration).filter(DroneRegistration.drone_id == d).delete()
        if d in DEMO_UIN:
            status = DEMO_UIN[d]
            db.add(DroneRegistration(drone_id=d, uin=f"DEMO-UIN-{d}", status=status, recorded_by=SEEDER.username,
                                     verified_by=SEEDER.username if status == "VERIFIED" else None,
                                     verified_at=datetime.utcnow() if status == "VERIFIED" else None,
                                     verification_note="demo registration, not a real Digital Sky UIN"))
    db.commit()


# A made-up maintenance entry placed between real flights of PX4-06, so the logbook has a before/after to show. The
# flights on either side are real; the work itself is invented for the demo and the note says so.
DEMO_MAINTENANCE = [("PX4-06", "2017-10-15T09:00:00", "Propellers replaced",
                     "DEMO entry, made up to show the logbook: the flights before and after it are real public flights.")]


def seed_maintenance(db, fleet: str) -> None:
    from aerofleet.assurance import ledger
    from aerofleet.data.models.models import MaintenanceEntry

    db.query(MaintenanceEntry).filter(MaintenanceEntry.fleet == fleet).delete()
    for drone, when, action, note in DEMO_MAINTENANCE:
        done = datetime.fromisoformat(when)
        db.add(MaintenanceEntry(fleet=fleet, drone_id=drone, done_at=done, action=action, note=note, done_by=SEEDER.username))
        ledger.append(db, "maintenance", f"{fleet}/{drone}", {"done_at": done.isoformat(), "action": action, "note": note},
                      SEEDER.username)
    db.commit()


# Demo spray forms on the last four flights of the drone that flew most recently, so the spray register shows each state once. The public logs are not spraying
# flights: every value typed here is made up and labelled DEMO; only the dates, times, height and speed come from the logs.
DEMO_SPRAY = {"1-2": "DEMO field, village not real", "2-1": "Crop", "2-2": 0.9, "2-3": "DEMO: paddy, brown planthopper 15%",
              "3-1": "DEMO product / common name", "3-2": "DEMO 20% SC", "3-3": "Other", "3-5": "Yes", "3-6": "Water, DEMO ratio",
              "4-2": 27, "4-3": 62, "4-4": 2.0, "4-5": 270, "4-6": 0, "5-1": "Hydraulic", "5-2": "Pilot", "5-3": "DEMO maker",
              "5-4": "DEMO model", "5-10": "DEMO flat-fan nozzles", "5-11": 1.2, "5-12": 4, "5-13": 4.0,
              "5-16": ["Ground party available", "Radio communication with aircraft"], "5-17": ["GPS"],
              "7-1": ["Goggles", "Mask", "Gloves", "Overalls"], "7-2": "Yes", "7-3": ["Farmers", "Villagers", "Officials"], "sop-water": "Yes"}


def seed_spray_forms(db, fleet: str, drone: str = "") -> None:
    from datetime import timedelta

    from aerofleet.assurance import ledger
    from aerofleet.assurance import spray_form as sf
    from aerofleet.data.models.models import FlightReview, MaintenanceEntry, SprayForm

    db.query(SprayForm).filter(SprayForm.fleet == fleet).delete()
    every = db.query(FlightReview).filter(FlightReview.fleet == fleet).order_by(FlightReview.id).all()
    if not every:
        return
    when = {r.id: sf.log_values(r.report or {}, r.created_at.isoformat())["4-1s"] or "" for r in every}
    drone = drone or max(every, key=lambda r: when[r.id]).drone_id     # so "as of the last flight" shows days left
    reviews = [r for r in every if r.drone_id == drone]
    dated = sorted(((sf.log_values(r.report or {}, r.created_at.isoformat()), r) for r in reviews), key=lambda x: x[0]["4-1s"] or "")
    if len(dated) < 4:
        return
    first_day = datetime.fromisoformat(dated[-4][0]["1-1"])
    note = "DEMO entry, made up to fill the spray form's date of last calibration."
    db.query(MaintenanceEntry).filter(MaintenanceEntry.fleet == fleet, MaintenanceEntry.drone_id == drone,
                                      MaintenanceEntry.action.in_(sf.CALIBRATION_ACTIONS)).delete()
    done = first_day - timedelta(days=12)
    db.add(MaintenanceEntry(fleet=fleet, drone_id=drone, done_at=done, action=sf.CALIBRATION_ACTIONS[0], note=note, done_by=SEEDER.username))
    ledger.append(db, "maintenance", f"{fleet}/{drone}", {"done_at": done.isoformat(), "action": sf.CALIBRATION_ACTIONS[0], "note": note}, SEEDER.username)
    plans = [("submitted", {}), ("ready", {}), ("problems", {"3-4": None, "sop-notice": None, "7-1": ["None"]}), ("not_spray", {})]
    for (log, r), (kind, over) in zip(dated[-4:], plans):
        start = datetime.fromisoformat(log["4-1s"])
        v = {**DEMO_SPRAY, "3-4": (start + timedelta(days=400)).date().isoformat(),
             "sop-notice": (start - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"), **over}
        if kind == "problems":
            v["3-4"] = (start - timedelta(days=30)).date().isoformat()          # expired product
            v["sop-notice"] = (start - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M")   # under 24 h notice
        row = SprayForm(review_id=r.id, fleet=fleet, drone_id=drone, values={} if kind == "not_spray" else v,
                        not_spray=kind == "not_spray", updated_by=SEEDER.username)
        if kind == "submitted":
            row.values = {**v, **{k: x for k, x in log.items() if k in sf.FROM_LOG and x is not None}, "5-5": "Aerial",
                          "5-6": done.date().isoformat()}
            row.submitted_on = (start + timedelta(days=5)).date().isoformat()
            row.submitted_via = "DEMO: email to the address in the CIB&RC guidelines"
        db.add(row)
        db.flush()
        ledger.append(db, "spray_form", f"{fleet}/review/{r.id}", {"review_id": r.id, "review_sha256": ledger.payload_hash(r.report),
                      "values": row.values, "not_spray": row.not_spray, "submitted_on": row.submitted_on,
                      "submitted_via": row.submitted_via}, SEEDER.username)
    db.commit()


def route_check_missions(folder: str):
    from aerofleet.integrations.mission_planner import build_waypoint_file

    os.makedirs(folder, exist_ok=True)
    for name, ((la0, lo0), (la1, lo1), alt) in ROUTE_CHECK.items():
        with open(os.path.join(folder, f"{name}.waypoints"), "w") as f:
            f.write(build_waypoint_file({"origin_lat": la0, "origin_lon": lo0, "dest_lat": la1, "dest_lon": lo1, "altitude_m": alt}))
    return sorted(ROUTE_CHECK)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fleet", default="demo")
    ap.add_argument("--drones", type=int, default=8)
    ap.add_argument("--flights", type=int, default=8)
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--spray-only", action="store_true", help="only (re)make the demo spray forms on an existing demo fleet")
    ap.add_argument("--agri-only", action="store_true", help="only seed the realistic ArduCopter spraying fleet 'pune-agri' from sitl_v2")
    ap.add_argument("--key", default=os.path.join(DATA, "demo_fleet_key.json"), help="presenter's key (kept outside the repository)")
    a = ap.parse_args()

    from fastapi import HTTPException

    from aerofleet.api.routes.assurance import review_flight
    from aerofleet.data.database import get_session, init_db
    from aerofleet.data.models.models import FleetBaseline, FlightReview, ParamSnapshot

    init_db()
    db = get_session()
    if a.agri_only:
        seed_agri_fleet(db, "pune-agri")
        return
    if a.spray_only:
        seed_spray_forms(db, a.fleet)
        print(f"Demo spray forms made for fleet '{a.fleet}' (the last four flights of the most recently flown drone).")
        return
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
    seed_registrations(db, sorted({k["drone"] for k in key}))
    seed_maintenance(db, a.fleet)
    seed_spray_forms(db, a.fleet)
    crashed = sorted({k["drone"] for k in key if k["role"] == "crash"})
    print(f"\n{len(key)} flights of {len({k['drone'] for k in key})} drones loaded into fleet '{a.fleet}'.")
    print(f"Drones whose last flight the uploader rated a crash: {', '.join(crashed) or 'none'}")
    print(f"Presenter's key: {a.key}")
    print(f"Made-up missions for the conflict and wind checks: {', '.join(demo_missions(os.path.join(DATA, 'demo_files')))} (.waypoints)")
    print(f"Made-up missions for the airspace route check: {', '.join(route_check_missions(os.path.join(DATA, 'demo_files', 'route_check')))}")
    if files:
        print(f"Settings files for the drift check: {files[0]} (approved), {files[1]} (changed: {files[2]})")
        seed_settings_fleet(db, f"{a.fleet}-settings", files)
    seed_agri_fleet(db, "pune-agri")


def seed_agri_fleet(db, fleet: str = "pune-agri") -> None:
    """Seed a cohesive 6-drone ArduCopter spraying fleet from real SITL v2 Pune spraying flights (.bin + .waypoints).

    Gives the live demonstration a true Indian agricultural fleet with:
      * a shared approved ArduCopter fleet baseline (from S0_normal_1),
      * real 4 m back-and-forth spraying missions reconciled against their .waypoints plans (and playable in 3D/VR),
      * active November 2026 Spray Register forms with auto-extracted height, speed, spray axis and estimated acres,
      * every readiness outcome: Ready, Check first (GPS/compass/fence-in-flight), Do not fly (failsafe off & grounded incident).
    """
    from datetime import timedelta

    from aerofleet.api.routes.assurance import review_flight
    from aerofleet.assurance import ledger
    from aerofleet.assurance import maintenance as maint
    from aerofleet.assurance import spray_form as sf
    from aerofleet.data.models.models import DroneRegistration, FleetBaseline, FlightReview, MaintenanceEntry, ParamSnapshot, SprayForm

    sitl_dir = os.path.join(DATA, "sitl_v2")
    if not os.path.isdir(sitl_dir):
        print(f"Skipping '{fleet}': {sitl_dir} not found.")
        return

    scenarios = [
        ("AGRI-01", "S0_normal_1", "VERIFIED", "submitted"),
        ("AGRI-02", "S5_wind_1", "VERIFIED", "ready"),
        ("AGRI-03", "S1_failsafe_off_1", "VERIFIED", "problems"),
        ("AGRI-04", "S4_fence_off_in_flight_1", "VERIFIED", "draft"),
        ("AGRI-05", "S6_motor_failure_1", "VERIFIED", "not_spray"),
        ("AGRI-06", "S7_compass_failure_1", "RECORDED", "draft"),
    ]
    for model in (SprayForm, MaintenanceEntry, FlightReview, ParamSnapshot):
        db.query(model).filter(model.fleet == fleet).delete()
    db.query(FleetBaseline).filter(FleetBaseline.fleet == fleet).delete()
    db.commit()

    baseline_set = False
    seeded_reviews = []
    for drone, stem, uin_status, form_kind in scenarios:
        bin_path = os.path.join(sitl_dir, f"{stem}.bin")
        wp_path = os.path.join(sitl_dir, f"{stem}.waypoints")
        if not (os.path.isfile(bin_path) and os.path.isfile(wp_path)):
            continue
        plan_bytes = open(wp_path, "rb").read()
        out = review_flight(
            db, SEEDER, fleet, drone, plan_bytes.decode("utf-8", errors="replace"),
            f"{stem}.waypoints", open(bin_path, "rb").read(), f"{stem}.bin", city="pune", plan_bytes=plan_bytes,
        )
        if not baseline_set:
            snap = (db.query(ParamSnapshot).filter(ParamSnapshot.fleet == fleet, ParamSnapshot.drone_id == drone)
                    .order_by(ParamSnapshot.id.desc()).first())
            if snap:
                db.add(FleetBaseline(fleet=fleet, params=snap.params, approved={}, source=f"{stem}.bin (approved ArduCopter baseline)",
                                     set_by=SEEDER.username, set_at=datetime.utcnow()))
                ledger.append(db, "baseline", fleet, {"params": snap.params, "source": f"{stem}.bin"}, SEEDER.username)
                db.commit()
                baseline_set = True
        db.query(DroneRegistration).filter(DroneRegistration.drone_id == drone).delete()
        db.add(DroneRegistration(
            drone_id=drone, uin=f"UA00DEMO{drone[-2:]}", status=uin_status, recorded_by=SEEDER.username,
            verified_by=SEEDER.username if uin_status == "VERIFIED" else None,
            verified_at=datetime.utcnow() if uin_status == "VERIFIED" else None,
            verification_note="DEMO UIN for ArduCopter SITL spraying fleet",
        ))
        seeded_reviews.append((drone, out["id"], form_kind))

    # Ground AGRI-05 after its motor-failure flight in the maintenance logbook
    now = datetime.utcnow().replace(microsecond=0)
    db.add(MaintenanceEntry(
        fleet=fleet, drone_id="AGRI-05", done_at=now - timedelta(hours=2),
        action=maint.GROUNDING_ACTION,
        note="Motor 1 thrust loss in SITL v2 S6; grounded pending motor/ESC bench check.",
        done_by=SEEDER.username,
    ))
    ledger.append(db, "maintenance", f"{fleet}/AGRI-05",
                  {"done_at": (now - timedelta(hours=2)).isoformat(), "action": maint.GROUNDING_ACTION,
                   "note": "Motor 1 thrust loss in SITL v2 S6; grounded pending motor/ESC bench check."}, SEEDER.username)

    # Calibration record + live November 2026 spray forms using 8 m swath spacing matching the SITL mission
    for drone, rev_id, kind in seeded_reviews:
        r = db.get(FlightReview, rev_id)
        log = sf.log_values(r.report or {}, r.created_at.isoformat())
        start_iso = log.get("4-1s") or now.strftime("%Y-%m-%dT%H:%M")
        start = datetime.fromisoformat(start_iso)
        cal_day = (start - timedelta(days=5)).replace(hour=9, minute=0)
        db.add(MaintenanceEntry(fleet=fleet, drone_id=drone, done_at=cal_day, action=sf.CALIBRATION_ACTIONS[0],
                                note="Pre-week nozzle flow calibration (DEMO).", done_by=SEEDER.username))
        if kind == "not_spray":
            row = SprayForm(review_id=rev_id, fleet=fleet, drone_id=drone, values={}, not_spray=True, updated_by=SEEDER.username)
        elif kind == "draft":
            row = SprayForm(review_id=rev_id, fleet=fleet, drone_id=drone,
                            values={"1-2": "Mulshi Block, Pune (SITL demo)", "5-13": 8.0}, not_spray=False, updated_by=SEEDER.username)
        else:
            v = {**DEMO_SPRAY, "1-2": "Mulshi Block, Pune (SITL demo)", "5-13": 8.0,
                 "3-4": (start + timedelta(days=365)).date().isoformat(),
                 "sop-notice": (start - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")}
            if kind == "problems":
                v["3-4"] = (start - timedelta(days=15)).date().isoformat()
                v["sop-notice"] = (start - timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M")
                v["7-1"] = ["None"]
            row = SprayForm(review_id=rev_id, fleet=fleet, drone_id=drone, values=v, not_spray=False, updated_by=SEEDER.username)
            if kind == "submitted":
                row.values = {**v, **{k: x for k, x in log.items() if k in sf.FROM_LOG and x is not None},
                              "5-5": "Aerial", "5-6": cal_day.date().isoformat()}
                row.submitted_on = min(now.date(), (start + timedelta(days=1)).date()).isoformat()
                row.submitted_via = "DEMO: CIB&RC Annexure-I email submission"
        db.add(row)
        db.flush()
        ledger.append(db, "spray_form", f"{fleet}/review/{rev_id}",
                      {"review_id": rev_id, "review_sha256": ledger.payload_hash(r.report),
                       "values": row.values, "not_spray": row.not_spray,
                       "submitted_on": row.submitted_on, "submitted_via": row.submitted_via}, SEEDER.username)
    db.commit()
    print(f"Fleet '{fleet}': {len(seeded_reviews)} ArduCopter 4 m Pune spraying flights seeded with baseline, plans, spray forms & maintenance.")


def seed_settings_fleet(db, fleet: str, files) -> None:
    """A fleet whose baseline is the approved file and whose drone has the changed file uploaded, as the app would
    record it: baseline, then the settings check, both in the signed record."""
    from aerofleet.api.routes.assurance import _drift
    from aerofleet.assurance import ledger
    from aerofleet.assurance.params import parse_param_bytes
    from aerofleet.data.models.models import FleetBaseline, ParamSnapshot

    approved, changed = (open(f, "rb").read() for f in files[:2])
    drone = os.path.basename(files[1]).split("_")[0]
    db.query(ParamSnapshot).filter(ParamSnapshot.fleet == fleet).delete()
    db.query(FleetBaseline).filter(FleetBaseline.fleet == fleet).delete()
    base = parse_param_bytes(approved)
    db.add(FleetBaseline(fleet=fleet, params=base.params, approved={}, source=os.path.basename(files[0]),
                         set_by=SEEDER.username, set_at=datetime.utcnow()))
    ledger.append(db, "baseline", fleet, {"params": base.params, "source": os.path.basename(files[0]),
                                          "input_file": ledger.file_fingerprint(os.path.basename(files[0]), approved)}, SEEDER.username)
    parsed = parse_param_bytes(changed)
    db.add(ParamSnapshot(drone_id=drone, fleet=fleet, params=parsed.params, file_format=parsed.format,
                         filename=os.path.basename(files[1]), uploaded_by=SEEDER.username))
    db.flush()
    report = _drift(db, fleet, drone)
    report["input_file"] = ledger.file_fingerprint(os.path.basename(files[1]), changed)
    ledger.append(db, "drift", f"{fleet}/{drone}", report, SEEDER.username)
    db.commit()
    print(f"Fleet '{fleet}': baseline from {os.path.basename(files[0])}, {drone} uploaded with {os.path.basename(files[1])} "
          f"-> {report['verdict']} ({', '.join(c['name'] for c in report['vs_baseline']['changes'])})")


if __name__ == "__main__":
    main()
