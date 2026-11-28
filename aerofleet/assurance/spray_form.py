"""Spray register: the crop-protection SOP's Spray Monitoring Form for each spraying flight, and its seven-day deadline.

Source: "Standard Operating Procedure (SOP) for use of Drone application with pesticides for crop protection in
agricultural, forestry, non-cropped areas, etc.", Annexure to the minutes of the 434th meeting of the Registration
Committee (CIB&RC), 30 November 2021. Section 7 says the operator or service provider submits the filled Spray
Monitoring Form (its Annexure-I) by email or the portal within seven days of applying pesticide by drone.

The field codes and labels below are the form's own (1-1 Date ... 7-3 Who was informed). What AeroFleet adds:
  * Fields a log can tell are filled from the reviewed flight, and say so: date, start and end time, height above
    the take-off point, ground speed and the main spray direction. The log does not know the crop, so the height
    is above take-off, not above the canopy, and the operator can correct it (the form keeps both and shows the
    difference).
  * Fields that rarely change for one drone (sprayer type, maker, model, number of atomizers) are copied from that
    drone's previous form; the date of last calibration comes from the maintenance logbook.
  * Fixed checks, each tied to a sentence of the SOP or of the form. Nothing here judges the spraying itself: the
    SOP says "appropriate" wind, temperature and height without numbers, so no threshold is invented for them.

Everything is deterministic; no model is involved.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from statistics import median
from typing import Any, Dict, List, Optional, Tuple

SOURCE = ("SOP for use of drone application with pesticides for crop protection, Annexure-I Spray Monitoring Form "
          "(434th Registration Committee meeting, CIB&RC, 30 Nov 2021)")
DEADLINE_DAYS = 7
DUE_SOON_DAYS = 2

# (code, label, section, kind, options, required). kind: text | number | date | datetime | choice | multi | yesno
FIELDS: List[Tuple[str, str, str, str, Optional[List[str]], bool]] = [
    ("1-1", "Date", "1 Location", "date", None, True),
    ("1-2", "Name of the location", "1 Location", "text", None, True),
    ("2-1", "Vegetation type", "2 Vegetation data", "choice", ["Crop", "Grass", "Bushes", "Trees"], True),
    ("2-2", "Height from ground / crop canopy (m)", "2 Vegetation data", "number", None, True),
    ("2-3", "Crop names and pest / disease / weed infestation intensity (%)", "2 Vegetation data", "text", None, True),
    ("3-1", "Trade name & common name", "3 Pesticide data", "text", None, True),
    ("3-2", "Concentration (g a.i./l or %)", "3 Pesticide data", "text", None, True),
    ("3-3", "Formulation", "3 Pesticide data", "choice", ["EC", "ULV", "Dust", "Other"], True),
    ("3-4", "Expiry date", "3 Pesticide data", "date", None, True),
    ("3-5", "Is the insecticide mixed with water or solvent?", "3 Pesticide data", "yesno", None, True),
    ("3-6", "If yes, what solvent and mixing ratio", "3 Pesticide data", "text", None, False),
    ("4-1s", "Start of control operations (date & time, UTC)", "4 Weather conditions", "datetime", None, True),
    ("4-1e", "End of control operations (date & time, UTC)", "4 Weather conditions", "datetime", None, True),
    ("4-2", "Temperature (°C)", "4 Weather conditions", "number", None, True),
    ("4-3", "Relative humidity (%)", "4 Weather conditions", "number", None, True),
    ("4-4", "Wind speed (m/s)", "4 Weather conditions", "number", None, True),
    ("4-5", "Wind direction (degrees from N)", "4 Weather conditions", "number", None, True),
    ("4-6", "Spray direction (degrees from N)", "4 Weather conditions", "number", None, True),
    ("5-1", "Sprayer type", "5 Spray application", "choice", ["Rotary", "Airblast", "ENS", "Hydraulic", "Other"], True),
    ("5-2", "Sprayer operator", "5 Spray application", "choice", ["Pilot", "Driver", "Hired", "Other"], True),
    ("5-3", "Sprayer manufacturer", "5 Spray application", "text", None, True),
    ("5-4", "Sprayer model", "5 Spray application", "text", None, True),
    ("5-5", "Sprayer platform", "5 Spray application", "choice", ["Aerial", "Vehicle", "Handheld"], True),
    ("5-6", "Date of last calibration", "5 Spray application", "date", None, True),
    ("5-7", "Atomizer height above ground (m)", "5 Spray application", "number", None, True),
    ("5-8", "Rotary sprayers: speed setting", "5 Spray application", "text", None, False),
    ("5-9", "Speed of atomizer (rpm)", "5 Spray application", "number", None, False),
    ("5-10", "Flow rate setting (nozzle or restrictor used)", "5 Spray application", "text", None, True),
    ("5-11", "Flow rate per atomizer (l/min)", "5 Spray application", "number", None, True),
    ("5-12", "Number of atomizers", "5 Spray application", "number", None, True),
    ("5-13", "Track spacing (m)", "5 Spray application", "number", None, True),
    ("5-14", "Barriers only: width and spacing (m)", "5 Spray application", "text", None, False),
    ("5-15", "Forward speed (km/h)", "5 Spray application", "number", None, True),
    ("5-16", "Aerial spraying: support supplied", "5 Spray application", "multi",
     ["Ground party available", "Radio communication with aircraft", "DGPS track guidance"], True),
    ("5-17", "Ground marking", "5 Spray application", "multi", ["GPS", "Flag", "Mirror", "Smoke", "Vehicle", "None"], True),
    ("6-1", "Effectiveness / mortality (%)", "6 Control efficacy", "number", None, False),
    ("6-2", "Days or hours after treatment", "6 Control efficacy", "text", None, False),
    ("6-3", "Method of effectiveness estimation", "6 Control efficacy", "choice",
     ["Quadrats", "Target size", "Visual", "Cages", "Other"], False),
    ("7-1", "Protective clothing worn by the operator", "7 Safety and environment", "multi",
     ["Goggles", "Mask", "Gloves", "Overalls", "Boots", "None"], True),
    ("7-2", "Was soap and water available?", "7 Safety and environment", "yesno", None, True),
    ("7-3", "Who was informed of spraying?", "7 Safety and environment", "multi",
     ["Farmers", "Nomads", "Villagers", "Officials", "Beekeeper", "Others"], True),
]
# Not on the Annexure, but required by the SOP's pre-application list (section 4.1), so kept with the form.
SOP_FIELDS: List[Tuple[str, str, str, str, Optional[List[str]], bool]] = [
    ("sop-notice", "Written intimation to the Gram Panchayat / Panchayat Samiti and the Agriculture Officer sent on "
     "(date & time, UTC)", "SOP 4.1 before spraying", "datetime", None, True),
    ("sop-water", "Nearest water source is at least 100 m from the target area", "SOP 4.1 before spraying", "yesno", None, True),
]
ALL_FIELDS = FIELDS + SOP_FIELDS
CODES = {f[0] for f in ALL_FIELDS}
CARRY_FORWARD = ["5-1", "5-2", "5-3", "5-4", "5-10", "5-11", "5-12", "5-16", "5-17"]
FROM_LOG = ["1-1", "4-1s", "4-1e", "4-6", "5-7", "5-15"]
CALIBRATION_ACTIONS = ("Spray system calibrated (nozzle output)",)


def _bearing(a: Tuple[float, float], b: Tuple[float, float]) -> Tuple[float, float]:
    """Bearing in degrees from north and distance in metres between two (lat, lon) points (flat-earth, short legs)."""
    dy = (b[0] - a[0]) * 111_320.0
    dx = (b[1] - a[1]) * 111_320.0 * math.cos(math.radians(a[0]))
    return (math.degrees(math.atan2(dx, dy)) % 360.0, math.hypot(dx, dy))


def log_values(report: Dict[str, Any], uploaded_at: str) -> Dict[str, Any]:
    """What the reviewed log can tell, in the form's units. Each value is None when the log cannot give it."""
    flown = ((report.get("replay") or {}).get("flown") or [])
    start_iso = (report.get("vibration") or {}).get("flown_at")
    start_unix = (report.get("log") or {}).get("start_utc")       # CSV and GPX logs have a date but no vibration
    start = (datetime.fromisoformat(start_iso) if start_iso
             else datetime.fromtimestamp(float(start_unix), timezone.utc) if start_unix else None)
    out: Dict[str, Any] = {"1-1": None, "4-1s": None, "4-1e": None, "4-6": None, "5-7": None, "5-15": None,
                           "take_off": [round(flown[0][1], 5), round(flown[0][2], 5)] if flown else None,
                           "time_source": "log time" if start else "upload time (the log has no GPS time)"}
    if start is None:
        start = datetime.fromisoformat(uploaded_at).replace(tzinfo=timezone.utc) if uploaded_at else None
    if start is not None:
        start = start.astimezone(timezone.utc)
        end = start + timedelta(seconds=float(report.get("flight_s") or 0))
        out.update({"1-1": start.date().isoformat(), "4-1s": start.strftime("%Y-%m-%dT%H:%M"),
                    "4-1e": end.strftime("%Y-%m-%dT%H:%M")})
    air = [p for p in flown if p[3] > 1.0]
    if air:
        out["5-7"] = round(median(p[3] for p in air), 1)
    speeds, sx, sy, moved = [], 0.0, 0.0, 0.0
    for a, b in zip(flown, flown[1:]):
        dt = b[0] - a[0]
        if dt <= 0 or a[3] <= 1.0 or b[3] <= 1.0:
            continue
        brg, dist = _bearing((a[1], a[2]), (b[1], b[2]))
        v = dist / dt
        if v < 1.0:                       # hovering or turning on the spot
            continue
        speeds.append(v)
        sx += dist * math.cos(math.radians(2 * brg))   # axial mean: a pass and its return count as one direction
        sy += dist * math.sin(math.radians(2 * brg))
        moved += dist
    if speeds:
        out["5-15"] = round(median(speeds) * 3.6, 1)
    if moved > 0:
        out["moved_m"] = round(moved, 1)
        r = math.hypot(sx, sy) / moved
        axis = (math.degrees(math.atan2(sy, sx)) / 2.0) % 180.0
        out["direction_strength"] = round(r, 2)
        if r >= 0.6:                       # most of the distance flown along one axis (back-and-forth passes)
            out["4-6"] = round(axis)
    return out


def area_estimate(log: Dict[str, Any], values: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Geometric area estimate from moving airborne distance * track spacing (5-13).

    Honest limit: turns between passes are included and no spray-flow sensor is read from the autopilot log,
    so this is an upper-bound geometric swath estimate for billing/record reference, not metered volume.
    """
    moved = _num(log.get("moved_m"))
    spacing = _num(values.get("5-13"))
    if moved is None or moved <= 0 or spacing is None or not (0 < spacing <= 30):
        return None
    area_m2 = moved * spacing
    return {
        "moved_m": round(moved, 1),
        "spacing_m": round(spacing, 2),
        "hectares": round(area_m2 / 10_000.0, 3),
        "acres": round(area_m2 / 4_046.8564, 2),
        "note": "Geometric swath upper bound (moving airborne distance × track spacing 5-13); includes turns and does not measure spray flow.",
    }


def defaults(log: Dict[str, Any], previous: Optional[Dict[str, Any]], last_calibration: Optional[str]) -> Dict[str, Dict[str, Any]]:
    """Pre-filled values with where each came from: log | previous form | logbook | form (fixed by the platform)."""
    pre: Dict[str, Dict[str, Any]] = {}
    timed = str(log.get("time_source", "")).startswith("log")
    for code in FROM_LOG:
        if log.get(code) is not None:
            when = code in ("1-1", "4-1s", "4-1e")
            pre[code] = {"value": log[code], "source": "log" if timed or not when else "upload time"}
    for code in CARRY_FORWARD:
        v = (previous or {}).get(code)
        if v not in (None, "", []):
            pre[code] = {"value": v, "source": "previous form"}
    if last_calibration:
        pre["5-6"] = {"value": last_calibration, "source": "logbook"}
    pre["5-5"] = {"value": "Aerial", "source": "drone"}
    return pre


def _empty(v: Any) -> bool:
    return v is None or v == "" or v == []


def _num(v: Any) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def checks(values: Dict[str, Any], log: Dict[str, Any], uin: Optional[str]) -> List[Dict[str, str]]:
    """Fixed checks on one form. level: missing | problem | note. Each cites where the rule comes from."""
    out: List[Dict[str, str]] = []
    for code, label, _s, _k, _o, required in ALL_FIELDS:
        if required and _empty(values.get(code)):
            out.append({"level": "missing", "code": code, "text": f"{code} {label}: not filled", "rule": "Annexure-I"})
    if values.get("3-5") == "Yes" and _empty(values.get("3-6")):
        out.append({"level": "missing", "code": "3-6", "text": "3-6 Solvent and mixing ratio: needed because 3-5 is Yes",
                    "rule": "Annexure-I 3-6"})
    day = values.get("1-1")
    if day and values.get("3-4") and values["3-4"] < day:
        out.append({"level": "problem", "code": "3-4", "text": f"The product expired on {values['3-4']}, before the spraying "
                    f"date {day}", "rule": "Annexure-I 3-4; SOP 5.2: only CIB&RC-approved pesticides, within the approved dose"})
    if day and values.get("5-6") and values["5-6"] > day:
        out.append({"level": "problem", "code": "5-6", "text": "The last calibration is dated after the spraying",
                    "rule": "Annexure-I 5-6"})
    if day and values.get("5-6"):
        gap = (date.fromisoformat(day) - date.fromisoformat(values["5-6"])).days
        if gap >= 0:
            out.append({"level": "note", "code": "5-6", "text": f"Spray system last calibrated {gap} days before this flight",
                        "rule": "SOP 4.1(x): calibrate the spray system for accurate application of labelled rates"})
    worn = values.get("7-1") or []
    if worn and ("None" in worn):
        out.append({"level": "problem", "code": "7-1", "text": "No protective clothing recorded",
                    "rule": "SOP 4.2(ii): wear personal protective equipment"})
    if values.get("7-2") == "No":
        out.append({"level": "note", "code": "7-2", "text": "No soap and water at the site", "rule": "Annexure-I 7-2"})
    notice, start = values.get("sop-notice"), values.get("4-1s")
    if notice and start:
        hours = (datetime.fromisoformat(start) - datetime.fromisoformat(notice)).total_seconds() / 3600
        if hours < 24:
            out.append({"level": "problem", "code": "sop-notice", "text": f"Written intimation sent {max(hours, 0):.0f} h before "
                        "spraying; the SOP asks for at least 24 h", "rule": "SOP 4.1(xvi)"})
    if values.get("sop-water") == "No":
        out.append({"level": "problem", "code": "sop-water", "text": "A water source is within 100 m of the target area",
                    "rule": "SOP 4.1(xv): do not spray pesticides less than 100 m from water sources"})
    if values.get("1-1") and log.get("1-1") and values["1-1"] != log["1-1"]:
        out.append({"level": "problem", "code": "1-1", "text": f"Date entered ({values['1-1']}) is not the date in the log "
                    f"({log['1-1']})", "rule": "The form must describe this flight"})
    for code, unit, tol in (("5-7", "m", 1.0), ("5-15", "km/h", 2.0)):
        a, b = _num(values.get(code)), _num(log.get(code))
        if a is not None and b is not None and abs(a - b) > tol:
            out.append({"level": "note", "code": code, "text": f"{code}: entered {a:g} {unit}, the log shows {b:g} {unit}"
                        + (" above the take-off point" if code == "5-7" else ""), "rule": "Both values are kept"})
    if not uin:
        out.append({"level": "problem", "code": "uin", "text": "This drone has no UIN on record",
                    "rule": "Drone Rules 2021: a drone may be flown only with a unique identification number"})
    return out


def status(values: Dict[str, Any], found: List[Dict[str, str]], submitted_on: Optional[str], as_of: date) -> Dict[str, Any]:
    """Where the form stands and how long is left. Due = spraying date + 7 days (SOP section 7)."""
    day = values.get("1-1")
    due = (date.fromisoformat(day) + timedelta(days=DEADLINE_DAYS)) if day else None
    missing = sum(1 for f in found if f["level"] == "missing")
    problems = sum(1 for f in found if f["level"] == "problem")
    if submitted_on:
        state = "SUBMITTED"
        late = (date.fromisoformat(submitted_on) - due).days if due else None
        return {"state": state, "due": due and due.isoformat(), "days_left": None, "missing": missing, "problems": problems,
                "submitted_late_by": late if late and late > 0 else 0}
    left = (due - as_of).days if due else None
    if left is not None and left < 0:
        state = "OVERDUE"
    elif missing:
        state = "DUE_SOON" if left is not None and left <= DUE_SOON_DAYS else "DRAFT"
    else:
        state = "READY"
    return {"state": state, "due": due and due.isoformat(), "days_left": left, "missing": missing, "problems": problems,
            "submitted_late_by": None}


ORDER = {"OVERDUE": 0, "DUE_SOON": 1, "DRAFT": 2, "READY": 3, "SUBMITTED": 4}


def _show(v: Any) -> str:
    if v is None or v == "" or v == []:
        return ""
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    return str(v).replace("T", " ")


def print_html(forms: List[Dict[str, Any]], fleet: str) -> str:
    """Annexure-I as printed: one row per field, one column per application (the form has six columns)."""
    from html import escape as e

    css = ("body{font:12px/1.35 -apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#111;margin:24px}"
           "h1{font-size:17px;margin:0}table{border-collapse:collapse;width:100%;margin-top:10px}"
           "td,th{border:1px solid #999;padding:3px 5px;vertical-align:top;text-align:left}th{background:#f0f0f0}"
           ".sec td{background:#f7f7f7;font-weight:700}.code{white-space:nowrap;color:#444}.muted{color:#555;font-size:11px}"
           ".log{color:#1d4ed8}@media print{body{margin:8mm}}")
    head = "".join(f"<th>{i + 1}<div class='muted'>{e(f['drone_id'])} · flight #{f['review_id']}</div></th>" for i, f in enumerate(forms))
    rows, section = [], None
    for code, label, sec, _k, _o, _r in ALL_FIELDS:
        if sec != section:
            section = sec
            rows.append(f"<tr class='sec'><td colspan='{len(forms) + 2}'>{e(sec)}</td></tr>")
        cells = []
        for f in forms:
            src = (f.get("sources") or {}).get(code)
            mark = " <span class='log' title='from the flight log'>(log)</span>" if src == "log" else ""
            cells.append(f"<td>{e(_show(f['values'].get(code)))}{mark}</td>")
        rows.append(f"<tr><td class='code'>{e(code)}</td><td>{e(label)}</td>{''.join(cells)}</tr>")
    meta = "".join(f"<div class='muted'>{i + 1}: drone {e(f['drone_id'])}, UIN {e(f.get('uin') or 'none on record')}, "
                   f"review #{f['review_id']}"
                   + (f", est. swath upper bound {f['area']['acres']} acres ({f['area']['hectares']} ha; includes turns, no flow sensor)" if f.get("area") else "")
                   + f" (signed review SHA-256 {e(f.get('review_sha256', '')[:16])}…)</div>" for i, f in enumerate(forms))
    sim_note = ("<div style='background:#fffbeb;border-left:4px solid #d97706;padding:6px 10px;margin:8px 0;font-size:12px'>"
                "<b>SIMULATED DEMO FLEET (ArduPilot SITL):</b> Printed from simulated demonstration logs, not field spraying.</div>"
                if fleet == "pune-agri" else "")
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Spray Monitoring Form - {e(fleet)}</title>"
            f"<style>{css}</style></head><body><h1>SPRAY MONITORING FORM <span class='muted'>(Annexure-I)</span></h1>"
            f"{sim_note}"
            f"<div class='muted'>{e(SOURCE)}. Filled from AeroFleet fleet {e(fleet)}; values marked (log) were read from "
            "the flight log. Submit within seven days of application, by email or the portal named in the CIB&RC "
            f"guidelines.</div>{meta}<table><thead><tr><th>Code</th><th>Field</th>{head}</tr></thead><tbody>{''.join(rows)}"
            "</tbody></table></body></html>")
