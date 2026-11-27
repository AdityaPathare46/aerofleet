"""Morning readiness: for each drone in a fleet, ready / check first / do not fly, and exactly why.

The use case: a drone service provider (for example a self-help group renting crop-spraying flights to farmers)
starts each day with a fleet of drones flown by pilots with weeks, not years, of training. This answers "which drones
can go out today, and what must someone look at first?" from records the tool already holds.

The verdict comes only from fixed rules and recorded facts, never from a prediction:

- DO NOT FLY: a safety-critical setting (failsafe, geofence, battery limit, ...) differs from the approved configuration
  and nobody has approved it; or the drone has no UIN on record (the Drone Rules 2021 require one before operating).
- CHECK FIRST: a flight-limit setting changed; the UIN is recorded but not verified; the settings were never checked;
  a failsafe is switched off in the drone's settings (whatever the approved baseline says: an approved configuration can
  have one off, and ArduPilot ships with its battery failsafe off); or the last reviewed flight's log shows warnings in
  the air (evidence.py: a GPS or autopilot-health complaint lasting 3 s or more while airborne, an autopilot error
  report while airborne). Landing below 10% battery is shown as a pilot note, not a reason (FA1, research/false_alarms) (the autopilot rejected sensor data, poor GPS, critical battery, a
  safety-critical setting changed in flight, the drone left its plan).
- READY: none of the above.

Vibration is shown beside the verdict but never changes it: in the study behind this tool, vibration did not warn of a
crash within a drone and was not shown to beat random inspection as a screen. Each reason names where to look.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

READY, CHECK_FIRST, DO_NOT_FLY = "READY", "CHECK_FIRST", "DO_NOT_FLY"
# ArduPilot: the compliance rules (aerofleet/hardware/compliance_rules.py, each with its ArduPilot source) that a
# failsafe is configured. PX4: the value PX4's parameter reference documents as "off" for each failsafe.
AP_FAILSAFE_RULES = {"batt.fs_low_action": "Low-battery failsafe", "batt.fs_critical_action": "Critical-battery failsafe",
                     "fs.rc_loss": "RC-loss (throttle) failsafe", "fs.ekf": "EKF failsafe", "fs.fence_enabled": "Geofence"}
PX4_FAILSAFES = {"NAV_RCL_ACT": (0, "RC-loss failsafe"), "COM_LOW_BAT_ACT": (0, "Low-battery failsafe (warning only)"),
                 "GF_ACTION": (0, "Geofence breach action")}


def failsafes_off(params) -> List[Dict[str, str]]:
    """Failsafes switched off in a drone's settings: [{"name", "title"}]. Empty when none, or when unknown."""
    if not params:
        return []
    out = [{"name": n, "title": t} for n, (off, t) in PX4_FAILSAFES.items() if n in params and int(params[n]) == off]
    if "FS_THR_ENABLE" in params or "BATT_FS_LOW_ACT" in params:        # ArduPilot settings
        from aerofleet.assurance.static_checks import checks_from_params

        for c in checks_from_params(params)["evaluated"]:
            if c["id"] in AP_FAILSAFE_RULES and c["status"] == "FAIL":
                names = [k for k in (c.get("evidence") or {}) if k.isupper()]       # the settings the rule read
                out.append({"name": names[0] if names else c["id"], "title": AP_FAILSAFE_RULES[c["id"]]})
    return out
ORDER = {DO_NOT_FLY: 0, CHECK_FIRST: 1, READY: 2}
VIBRATION_NOTE = ("Context only: in the study behind AeroFleet, vibration did not warn of a crash within a drone and was not "
                  "shown to beat random inspection, so it never changes the verdict.")


def _reason(level: str, text: str, where: str, code: str, **args: Any) -> Dict[str, Any]:
    """`code` and `args` let the screen show the same reason in Hindi or Marathi; `text` is the English original."""
    return {"level": level, "text": text, "where": where, "code": code, "args": args}


def assess(drone_id: str, settings: Optional[Dict[str, Any]], registration: Optional[Dict[str, Any]],
           last_flight: Optional[Dict[str, Any]], vibration: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """`settings`: {"verdict", "critical": [names], "limits": [names]} from the drift check, or None if never uploaded.
    `registration`: {"uin", "status"} or None. `last_flight`: {"review_id", "flown_at", "warnings": [texts],
    "critical_in_flight": int, "deviated": bool} or None. `vibration`: shown, not judged."""
    reasons: List[Dict[str, Any]] = []
    if registration is None:
        reasons.append(_reason(DO_NOT_FLY, "No UIN on record: the Drone Rules 2021 require one before the drone is operated.", "register", "no_uin"))
    elif registration.get("status") != "VERIFIED":
        reasons.append(_reason(CHECK_FIRST, f"UIN {registration['uin']} is recorded but not yet verified on Digital Sky.", "register",
                               "uin_unverified", uin=registration["uin"]))

    if settings is None:
        reasons.append(_reason(CHECK_FIRST, "Settings never checked: upload its parameter file or a flight log.", "settings", "settings_never"))
    elif settings["verdict"] == "BLOCK":
        reasons.append(_reason(DO_NOT_FLY, "Safety-critical setting changed and not approved: " + ", ".join(settings["critical"][:4]) + ".", "settings",
                               "critical_changed", names=", ".join(settings["critical"][:4])))
    elif settings["verdict"] == "REVIEW":
        reasons.append(_reason(CHECK_FIRST, "Flight-limit setting changed and not approved: " + ", ".join(settings["limits"][:4]) + ".", "settings",
                               "limit_changed", names=", ".join(settings["limits"][:4])))
    for fs in (settings or {}).get("failsafes_off", [])[:4]:
        reasons.append(_reason(CHECK_FIRST, f"Failsafe switched off: {fs['title']} ({fs['name']}).", "settings",
                               "failsafe_off", title=fs["title"], name=fs["name"]))

    if last_flight is not None:
        if last_flight.get("critical_in_flight"):
            reasons.append(_reason(CHECK_FIRST, f"{last_flight['critical_in_flight']} safety-critical setting(s) were changed during the last flight.", "flight",
                                   "critical_in_flight", n=last_flight["critical_in_flight"]))
        if last_flight.get("deviated"):
            reasons.append(_reason(CHECK_FIRST, "The last flight left its planned route.", "flight", "deviated"))
        for w in last_flight.get("warnings", [])[:3]:
            reasons.append(_reason(CHECK_FIRST, f"Last flight: {w}.", "flight", "warning", warning=w))
        if len(last_flight.get("warnings", [])) > 3:
            reasons.append(_reason(CHECK_FIRST, f"Last flight: {len(last_flight['warnings']) - 3} more warnings in its timeline.", "flight",
                                   "more_warnings", n=len(last_flight["warnings"]) - 3))

    status = min((r["level"] for r in reasons), key=ORDER.get, default=READY)
    return {"drone_id": drone_id, "status": status, "reasons": sorted(reasons, key=lambda r: ORDER[r["level"]]),
            "registration": registration, "settings_verdict": settings["verdict"] if settings else None,
            "last_flight": last_flight, "vibration": vibration}


def last_flight_summary(review_id: int, report: Dict[str, Any], uploaded_at: str) -> Dict[str, Any]:
    """The facts readiness needs from a stored flight review: its warnings, in-flight setting changes, deviation."""
    seen, warnings, pilot = set(), [], []
    for e in report.get("evidence_timeline") or []:
        if e.get("kind") == "battery" and e.get("level") == "warning":
            pilot.append(e["text"])               # how the last flight was flown, not whether the drone is fit today (FA1)
            continue
        if e.get("level") == "warning" and e.get("kind") != "plan":
            key = e["text"].split(" for ")[0]                     # one line per kind of warning, not per occurrence
            if key not in seen:
                seen.add(key)
                warnings.append(e["text"])
    outside = [f"{t['label'].lower()} {t['position']} the expected range" + (f" ({t['times_mid']}x typical)" if t.get("times_mid") else "")
               for t in ((report.get("normal_flight") or {}).get("targets") or {}).values() if t["position"] != "inside"]
    return {"review_id": review_id, "flown_at": (report.get("vibration") or {}).get("flown_at") or uploaded_at,
            "normal_flight": outside,                          # context only: never a reason, never changes the verdict
            "pilot_notes": pilot,                              # e.g. landed below 10% battery: shown, never a reason
            "warnings": warnings, "critical_in_flight": (report.get("settings_changed_in_flight") or {}).get("safety_critical", 0),
            "deviated": report.get("verdict") == "DEVIATED", "flight_s": report.get("flight_s")}
