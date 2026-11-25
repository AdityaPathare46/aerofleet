"""What a flight log shows, as a small set of named signs, so flights can be compared with each other.

A sign is something the evidence timeline already reports (aerofleet/assurance/evidence.py): poor GPS, the estimator
rejecting compass data, a critical battery, the pilot taking over from an automatic mode, a safety setting changed in
flight. Vibration is added only as "high for this kind of drone" (above 90% of the public reference flights).
The same function runs on the user's own reviewed flight and on the public logs on this computer, so "flights that
show the same signs" means exactly the same rules applied to both.

Words a person types are mapped to signs by a fixed list (SIGN_WORDS). That mapping was tested (declared test A1,
research/results/archive_search/summary.md) and did not connect descriptions with what the same flights' logs showed,
so the product shows which signs the words name but never matches logs from words. Nothing is learned and no cause is
named: two flights with the same signs can have different causes.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Set

SIGNS: Dict[str, str] = {
    "gps_poor": "Poor GPS (few satellites, no 3D fix or high HDOP)",
    "est_compass": "Autopilot rejected compass data",
    "est_velocity": "Autopilot rejected velocity data",
    "est_position": "Autopilot rejected position data",
    "est_height": "Autopilot rejected height data",
    "est_fault": "Autopilot reported an estimator fault",
    "battery_critical": "Battery below 10%",
    "battery_low": "Battery below 20%",
    "voltage_sag": "Battery voltage fell by more than 25%",
    "pilot_took_control": "Pilot took control from an automatic mode",
    "setting_in_flight": "Safety-critical setting changed in flight",
    "off_plan": "Left the planned route or height",
    "vibration_high": "Vibration above 90% of public flights of this kind",
}

# Fixed word list: a description that uses one of these words (after lower-casing) is matched to the sign.
SIGN_WORDS: Dict[str, List[str]] = {
    "gps_poor": ["gps", "satellite", "satellites", "sats", "hdop", "glitch", "fix"],
    "est_compass": ["compass", "mag", "magnetometer", "heading", "yaw", "toilet", "circling", "circles", "interference"],
    "est_velocity": ["velocity", "speed", "drift", "drifting", "drifts", "ekf"],
    "est_position": ["position", "drift", "drifting", "drifts", "ekf", "flyaway", "fly-away", "flew away"],
    "est_height": ["altitude", "height", "baro", "barometer", "climb", "climbed", "sink", "dropped"],
    "est_fault": ["ekf", "estimator", "fault"],
    "battery_critical": ["battery", "batteries", "low battery", "died", "power"],
    "battery_low": ["battery", "batteries", "low battery"],
    "voltage_sag": ["voltage", "sag", "cell", "cells", "brownout", "power"],
    "pilot_took_control": ["manual", "took over", "took control", "switched", "pilot"],
    "setting_in_flight": ["parameter", "parameters", "param", "setting", "settings", "changed"],
    "off_plan": ["route", "mission", "waypoint", "path", "off course", "deviated"],
    "vibration_high": ["vibration", "vibrations", "vibrating", "shaking", "shake", "jello", "wobble", "oscillation", "oscillating"],
}


def signs_from_events(events: Iterable[Dict[str, Any]], vibration_pct: Optional[float] = None) -> Set[str]:
    """Signs from an evidence timeline (the `evidence_timeline` of a flight review)."""
    out: Set[str] = set()
    for e in events:
        text, kind = e.get("text", ""), e.get("kind")
        if kind == "gps" and e.get("level") == "warning":
            out.add("gps_poor")
        elif kind == "sensor":
            for label, sign in (("compass", "est_compass"), ("velocity", "est_velocity"), ("position", "est_position"),
                                ("height", "est_height"), ("internal fault", "est_fault")):
                if label in text:
                    out.add(sign)
        elif kind == "battery":
            if text.startswith("Battery below 10%"):
                out.add("battery_critical")
            elif text.startswith("Battery below 20%"):
                out.add("battery_low")
            elif text.startswith("Battery voltage fell"):
                out.add("voltage_sag")
        elif kind == "mode" and "pilot took control" in text:
            out.add("pilot_took_control")
        elif kind == "setting" and e.get("level") == "warning":
            out.add("setting_in_flight")
        elif kind == "plan":
            out.add("off_plan")
    if vibration_pct is not None and vibration_pct >= 90:
        out.add("vibration_high")
    return out


def signs_from_report(report: Dict[str, Any]) -> Set[str]:
    from aerofleet.assurance.public_reference import vibration_position

    vib = report.get("vibration") or {}
    pos = vibration_position(vib.get("source"), (report.get("log") or {}).get("vehicle"), vib.get("p95")) if vib else None
    return signs_from_events(report.get("evidence_timeline") or [], pos and pos["higher_than_pct"])


def signs_from_words(text: str) -> Set[str]:
    low = " " + re.sub(r"[^a-z0-9\- ]+", " ", (text or "").lower()) + " "
    return {s for s, words in SIGN_WORDS.items() if any(f" {w} " in low for w in words)}


def similarity(a: Set[str], b: Set[str]) -> float:
    """Share of signs in common (Jaccard). Two flights with no signs at all are not called similar."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def signs_from_flight(flight) -> Set[str]:
    """Signs straight from a parsed log (aerofleet/assurance/flightlog.FlightLog), with no plan: the same timeline and
    vibration rules a log-only review uses."""
    from aerofleet.assurance.evidence import timeline
    from aerofleet.assurance.public_reference import vibration_position
    from aerofleet.assurance.vibration import flight_vibration

    events = timeline({"episodes": []}, flight.track, flight.modes, flight.battery, flight.gps, flight.param_changes, flight.health)
    vib = flight_vibration(flight)
    pos = vibration_position(vib["source"], flight.vehicle, vib["p95"]) if vib else None
    return signs_from_events(events, pos and pos["higher_than_pct"])
