"""Morning readiness: for each drone in a fleet, ready / check first / do not fly, and exactly why.

The use case: a small-to-mid commercial or institutional UAV operator in India (DaaS operator, RPTO training
academy, or agricultural drone service aggregator) starts each day with a fleet of drones flown by multiple
pilots. This answers "which drones can go out today, and what must someone look at first?" from records the
tool already holds.

The verdict comes only from fixed rules and recorded facts, never from a prediction:

- DO NOT FLY: a safety-critical setting (failsafe, geofence, battery limit, ...) differs from the approved configuration
  and nobody has approved it; no UIN on record (the Drone Rules 2021 require one before operating); or the drone was
  grounded in the maintenance logbook after a reported incident/crash without a later inspection clearance.
- CHECK FIRST: a flight-limit setting changed; settings have not been compared with an approved baseline yet
  (NO_REFERENCE); the UIN is recorded but not verified; settings were never checked; a failsafe or safety check is
  switched off in the drone's settings (whatever the baseline says); the last reviewed flight came from a partial
  CSV/GPX export without autopilot health/settings; or the last reviewed flight's log shows warnings in the air
  (evidence.py: a GPS or autopilot-health complaint lasting 3 s or more while airborne, an autopilot error report
  while airborne, an in-flight critical battery drop > 15 s before touchdown, a safety-critical setting changed in
  flight, or leaving the planned route). A low-battery landing (< 10% near touchdown) is shown as a pilot note, not
  a reason (FA1/FA2, research/false_alarms).
- READY: none of the above.

Vibration is shown beside the verdict but never changes it: in the study behind this tool, vibration did not warn of a
crash within a drone and was not shown to beat random inspection as a screen. Each reason names where to look.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

IST = timezone(timedelta(hours=5, minutes=30))
INSURANCE_WARN_DAYS = 14
STALE_FLIGHT_DAYS = 14     # default age threshold in fleet_readiness(): confirm no unlogged flights occurred since

READY, CHECK_FIRST, DO_NOT_FLY = "READY", "CHECK_FIRST", "DO_NOT_FLY"
# ArduPilot: the compliance rules (aerofleet/hardware/compliance_rules.py, each with its ArduPilot source) that a
# failsafe is configured. PX4: documented "off" / safety-bypass values for each failsafe or circuit breaker.
AP_FAILSAFE_RULES = {"batt.fs_low_action": "Low-battery failsafe", "batt.fs_critical_action": "Critical-battery failsafe",
                     "fs.rc_loss": "RC-loss (throttle) failsafe", "fs.ekf": "EKF failsafe", "fs.fence_enabled": "Geofence"}
AP_MARKERS = ("FS_THR_ENABLE", "BATT_FS_LOW_ACT", "BATT_FS_CRT_ACT", "FENCE_ENABLE", "FS_EKF_ACTION", "ARMING_CHECK")
PX4_FAILSAFES = {"NAV_RCL_ACT": (0, "RC-loss failsafe"), "COM_LOW_BAT_ACT": (0, "Low-battery failsafe (warning only)"),
                 "GF_ACTION": (0, "Geofence breach action")}
PX4_CIRCUIT_BREAKERS = {"CBRK_SUPPLY_CHK": (894281, "Power-supply check bypassed")}
# PX4 circuit breakers that are bypassed BY DEFAULT, so flagging them would put nearly every stock drone on "Check first"
# (27 Nov 2026, 200 random public PX4 logs: CBRK_FLIGHTTERM bypassed in 199, CBRK_IO_SAFETY in 142;
# docs/CRITICAL_REVIEW_2026-11-27.md, C1). CBRK_FLIGHTTERM is not checked at all: flight termination is an extra
# feature that PX4 ships disabled, not a failsafe. CBRK_IO_SAFETY (no hardware safety switch) is shown as a note only.
PX4_DEFAULT_BYPASS_NOTES = {"CBRK_IO_SAFETY": (22027, "Hardware safety switch bypassed (PX4 default on recent firmware)")}


def _as_int(v) -> Optional[int]:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _approved_match(approved: Optional[Dict[str, Any]], name: str, val: Any) -> Optional[Dict[str, Any]]:
    if not approved or name not in approved:
        return None
    entry = approved[name]
    a_val = _as_int(entry.get("value") if isinstance(entry, dict) else entry)
    p_val = _as_int(val)
    if a_val is not None and p_val is not None and a_val == p_val:
        return entry if isinstance(entry, dict) else {"value": a_val}
    return None


def failsafes_off(params, approved: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
    """Failsafes or critical safety checks switched off in a drone's settings: [{"name", "title"}]. These are reasons
    for "Check first" unless the operator has explicitly signed off that exact value in `FleetBaseline.approved`
    with a written reason (in which case setting_notes() records the signed exception). Values that are the firmware's
    own default bypass are in setting_notes() instead."""
    if not params:
        return []
    raw = [{"name": n, "title": t} for n, (off, t) in PX4_FAILSAFES.items() if n in params and _as_int(params[n]) == off]
    raw += [{"name": n, "title": t} for n, (bypass, t) in PX4_CIRCUIT_BREAKERS.items() if n in params and _as_int(params[n]) == bypass]
    if "ARMING_CHECK" in params and _as_int(params["ARMING_CHECK"]) == 0:
        raw.append({"name": "ARMING_CHECK", "title": "Pre-arm safety checks disabled"})
    if any(k in params for k in AP_MARKERS):                               # ArduPilot settings
        from aerofleet.assurance.static_checks import checks_from_params

        for c in checks_from_params(params)["evaluated"]:
            if c["id"] in AP_FAILSAFE_RULES and c["status"] == "FAIL":
                names = [k for k in (c.get("evidence") or {}) if k.isupper()]       # the settings the rule read
                raw.append({"name": names[0] if names else c["id"], "title": AP_FAILSAFE_RULES[c["id"]]})
    return [item for item in raw if _approved_match(approved, item["name"], params.get(item["name"])) is None]


def setting_notes(params, approved: Optional[Dict[str, Any]] = None) -> List[str]:
    """Safety-related settings worth knowing about that are the firmware's default or disabled under a signed
    operator approval: shown beside the verdict, never a reason (like the pilot notes)."""
    if not params:
        return []
    notes = [f"{t} ({n} = {v})" for n, (v, t) in PX4_DEFAULT_BYPASS_NOTES.items() if n in params and _as_int(params[n]) == v]
    if approved:
        for item in failsafes_off(params, approved=None):
            hit = _approved_match(approved, item["name"], params.get(item["name"]))
            if hit is not None:
                who = hit.get("by") or "operator"
                notes.append(f"{item['title']} ({item['name']}): off under signed approval by {who}")
    return notes


ORDER = {DO_NOT_FLY: 0, CHECK_FIRST: 1, READY: 2}
VIBRATION_NOTE = ("Context only: in the study behind AeroFleet, vibration did not warn of a crash within a drone and was not "
                  "shown to beat random inspection, so it never changes the verdict.")


def _reason(level: str, text: str, where: str, code: str, **args: Any) -> Dict[str, Any]:
    """`code` and `args` let the screen show the same reason in Hindi or Marathi; `text` is the English original."""
    return {"level": level, "text": text, "where": where, "code": code, "args": args}


def assess(drone_id: str, settings: Optional[Dict[str, Any]], registration: Optional[Dict[str, Any]],
           last_flight: Optional[Dict[str, Any]], vibration: Optional[Dict[str, Any]] = None,
           grounded: Optional[Dict[str, Any]] = None, compliance: Optional[Dict[str, Any]] = None,
           today: Optional[date] = None, max_stale_days: Optional[int] = None) -> Dict[str, Any]:
    """`settings`: {"verdict", "critical": [names], "limits": [names]} from the drift check, or None if never uploaded.
    `registration`: {"uin", "status"} or None. `last_flight`: {"review_id", "flown_at", "warnings": [texts],
    "critical_in_flight": int, "deviated": bool, "partial_log": bool} or None. `vibration`: shown, not judged.
    `grounded`: unresolved incident/crash entry from maintenance.is_grounded(), or None.
    `compliance`: optional DGCA Rule 44 insurance / Rule 31 pilot RPC dict; enforced when present (IST date).
    `max_stale_days`: if set, flags `CHECK_FIRST` (`stale_flight`) when `last_flight.flown_at` is older than this
    many days so a drone that flew unlogged or sat unreviewed cannot quietly show 'No rule fired'.
    Note: `failsafes_off` fires regardless of baseline by design (both ArduPilot and PX4 ship low-battery actions
    off/warn-only by default, so copying a stock drone as baseline must not silently approve a disabled failsafe)."""
    reasons: List[Dict[str, Any]] = []
    if grounded is not None:
        reasons.append(_reason(DO_NOT_FLY, "Drone grounded after a reported incident or crash: inspect and log clearance before flying.",
                               "settings", "grounded_incident"))
    if registration is None:
        reasons.append(_reason(DO_NOT_FLY, "No UIN on record: the Drone Rules 2021 require one before the drone is operated.", "register", "no_uin"))
    elif registration.get("status") != "VERIFIED":
        reasons.append(_reason(CHECK_FIRST, f"UIN {registration['uin']} is recorded but not yet verified on Digital Sky.", "register",
                               "uin_unverified", uin=registration["uin"]))

    if compliance is not None:
        ref = today or datetime.now(IST).date()
        ins_end = compliance.get("insurance_valid_until")
        if not ins_end:
            reasons.append(_reason(CHECK_FIRST, "No third-party insurance expiry on record (Drone Rules 2021 Rule 44).",
                                   "register", "no_insurance"))
        else:
            try:
                exp = date.fromisoformat(str(ins_end)[:10])
                days = (exp - ref).days
                if days < 0:
                    reasons.append(_reason(DO_NOT_FLY, f"Third-party insurance expired on {exp.isoformat()} (Drone Rules 2021 Rule 44).",
                                           "register", "insurance_expired", date=exp.isoformat()))
                elif days <= INSURANCE_WARN_DAYS:
                    reasons.append(_reason(CHECK_FIRST, f"Third-party insurance expires in {days} day(s) ({exp.isoformat()}).",
                                           "register", "insurance_expiring", days=days, date=exp.isoformat()))
            except ValueError:
                pass
        rpc_end = compliance.get("pilot_rpc_valid_until")
        if rpc_end:
            try:
                exp = date.fromisoformat(str(rpc_end)[:10])
                if (exp - ref).days < 0:
                    reasons.append(_reason(DO_NOT_FLY, f"Assigned pilot RPC expired on {exp.isoformat()} (Drone Rules 2021 Rule 31).",
                                           "register", "rpc_expired", date=exp.isoformat()))
            except ValueError:
                pass

    if settings is None:
        reasons.append(_reason(CHECK_FIRST, "Settings never checked: upload its parameter file or a flight log.", "settings", "settings_never"))
    elif settings["verdict"] == "BLOCK":
        reasons.append(_reason(DO_NOT_FLY, "Safety-critical setting changed and not approved: " + ", ".join(settings["critical"][:4]) + ".", "settings",
                               "critical_changed", names=", ".join(settings["critical"][:4])))
    elif settings["verdict"] == "REVIEW":
        reasons.append(_reason(CHECK_FIRST, "Flight-limit setting changed and not approved: " + ", ".join(settings["limits"][:4]) + ".", "settings",
                               "limit_changed", names=", ".join(settings["limits"][:4])))
    elif settings["verdict"] == "NO_REFERENCE":
        reasons.append(_reason(CHECK_FIRST, "Settings have not been compared with an approved fleet baseline yet.", "settings", "no_baseline"))
    for fs in (settings or {}).get("failsafes_off", [])[:4]:
        reasons.append(_reason(CHECK_FIRST, f"Failsafe switched off: {fs['title']} ({fs['name']}).", "settings",
                               "failsafe_off", title=fs["title"], name=fs["name"]))

    stale_note: Optional[Dict[str, Any]] = None
    if last_flight is not None:
        if max_stale_days is not None and last_flight.get("flown_at"):
            try:
                ref = today or datetime.now(IST).date()
                fdt = datetime.fromisoformat(str(last_flight["flown_at"]).replace("Z", "+00:00"))
                fdate = fdt.astimezone(IST).date() if fdt.tzinfo else fdt.date()
                age = (ref - fdate).days
                if age > max_stale_days:
                    stale_note = {
                        "days": age,
                        "date": fdate.isoformat(),
                        "text": f"Last reviewed flight was {age} day(s) ago ({fdate.isoformat()}): confirm no unlogged flights occurred since.",
                    }
            except ValueError:
                pass
        if last_flight.get("partial_log"):
            reasons.append(_reason(CHECK_FIRST, "Last flight was read from a CSV/GPX export: autopilot health and settings could not be verified.",
                                   "flight", "partial_log"))
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
            "registration": registration, "compliance": compliance, "settings_verdict": settings["verdict"] if settings else None,
            "last_flight": last_flight, "stale_note": stale_note, "vibration": vibration, "grounded": grounded}


def last_flight_summary(review_id: int, report: Dict[str, Any], uploaded_at: str) -> Dict[str, Any]:
    """The facts readiness needs from a stored flight review: its warnings, in-flight setting changes, deviation."""
    seen, warnings, pilot = set(), [], []
    for e in report.get("evidence_timeline") or []:
        if e.get("kind") == "battery" and e.get("level") == "warning" and not e.get("in_flight"):
            pilot.append(e["text"])               # low-battery landing: pilot note, not an aircraft fault (FA1)
            continue
        if e.get("level") == "warning" and e.get("kind") != "plan":
            key = e["text"].split(" for ")[0]                     # one line per kind of warning, not per occurrence
            if key not in seen:
                seen.add(key)
                warnings.append(e["text"])
    outside = [f"{t['label'].lower()} {t['position']} the expected range" + (f" ({t['times_mid']}x typical)" if t.get("times_mid") else "")
               for t in ((report.get("normal_flight") or {}).get("targets") or {}).values() if t["position"] != "inside"]
    fmt = ((report.get("log") or {}).get("format") or "").lower()
    return {"review_id": review_id, "flown_at": (report.get("vibration") or {}).get("flown_at") or uploaded_at,
            "normal_flight": outside,                          # context only: never a reason, never changes the verdict
            "pilot_notes": pilot,                              # e.g. landed below 10% battery: shown, never a reason
            "partial_log": fmt in ("csv", "gpx"),
            "warnings": warnings, "critical_in_flight": (report.get("settings_changed_in_flight") or {}).get("safety_critical", 0),
            "deviated": report.get("verdict") == "DEVIATED", "flight_s": report.get("flight_s")}
