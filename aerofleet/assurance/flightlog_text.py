"""Flight logs from controllers whose own log format AeroFleet cannot read: a CSV export or a GPX track.

PX4 (.ulg) and ArduPilot (.tlog / .bin) logs are read in full by aerofleet/assurance/flightlog.py; any autopilot that
speaks MAVLink also gives a .tlog through its ground station. Many spraying drones do not: DJI Agras and several
Chinese agricultural controllers keep closed logs. What their apps and third-party tools can usually give is a CSV
(one row per sample) or a GPX track. This module reads those:

  * CSV: columns are found by name, case and units ignored. Accepted names include AeroFleet's own template
    (time_s, latitude, longitude, height_m, battery_pct, voltage_v, satellites, mode), the column names of Airdata
    UAV's DJI CSV export (time(millisecond), datetime(utc), height_above_takeoff(feet), battery_percent, ...) and of
    DJI flight-record CSV converters (OSD.latitude, OSD.height [ft], BATTERY.chargeLevel, OSD.gpsNum, OSD.flycState).
    Feet are converted to metres. DJI flight-record CSVs are tested on real public exports (three DJI Mini 4 Pro
    flights and a 2017 Mavic fragment, tests/integration/test_real_dji_exports.py); the Airdata layout only on files
    built to its published column names.
  * GPX: track points with time and elevation, from any app; height is taken relative to the first point.

What these files cannot give: settings, vibration and the autopilot's own sensor checks, so a review of them has no
settings drift, no vibration and no estimator lines. The review says so.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

FT = 0.3048
MAX_ROWS = 400_000

# Column names after normalising (lower case, units and punctuation removed), in order of preference.
NAMES: Dict[str, List[str]] = {
    "datetime": ["datetime", "datetimeutc", "gpstime", "timestamp", "timestamps", "timestamps_ns", "timestamp_ns",
                 "customupdatetime", "updatetime", "date_time", "utc"],
    "time": ["time_s", "times", "timemillisecond", "time", "osdflytime", "flytime", "elapsed", "seconds", "t"],
    "lat": ["latitude", "lat", "osdlatitude", "gpslatitude", "gps_lat"],
    "lon": ["longitude", "lon", "lng", "long", "osdlongitude", "gpslongitude", "gps_lon"],
    "height": ["height_m", "heightabovetakeoff", "heightabovetakeoffmeters", "heightabovetakeoffm", "osdheight", "height",
               "relative_alt", "relativealt", "alt_m", "altitude", "alt"],
    "battery": ["battery_pct", "batterypercent", "batterychargelevel", "battery_percent", "battery", "remaining",
                "battery_remaining", "osdbattery", "centerbatteryrelativecapacity"],
    "voltage": ["voltage_v", "voltage", "batteryvoltage", "battery_voltage", "voltagev", "centerbatterycurrentpv",
                "batterycurrentpv"],
    "sats": ["satellites", "sats", "osdgpsnum", "gpsnum", "num_sats", "numsats"],
    "hdop": ["hdop", "osdgpshdop"],
    "mode": ["mode", "flight_mode", "flightmode", "osdflycstate", "flycstate"],
}


def _norm(header: str) -> Tuple[str, str]:
    """('heightabovetakeoff', 'feet') from 'height_above_takeoff(feet)'; ('osdheight', 'ft') from 'OSD.height [ft]'."""
    h = header.strip().lower()
    unit = " ".join(re.findall(r"[\[(]([^\])]*)[\])]", h))
    base = re.sub(r"[\[(][^\])]*[\])]", "", h)
    base = re.sub(r"[^a-z0-9_]", "", base.replace(" ", "_")).strip("_")
    return base, unit


def _find(headers: List[str]) -> Dict[str, Tuple[int, str]]:
    normed = [_norm(h) for h in headers]
    flat = [(b.replace("_", ""), u) for b, u in normed]
    out: Dict[str, Tuple[int, str]] = {}
    def first(cands):            # two columns with one name ("OSD.flyTime" text, "OSD.flyTime [s]" number): take the one with a unit
        return min(cands, key=lambda i: (normed[i][1] == "", i)) if cands else None

    for key, names in NAMES.items():
        for name in names:
            hit = first([i for i, (b, _) in enumerate(normed) if b == name])
            if hit is None:
                hit = first([i for i, (b, _) in enumerate(flat) if b == name.replace("_", "")])
            if hit is not None:
                out[key] = (hit, normed[hit][1])
                break
    if "time" in out and "datetime" in out and out["time"][0] == out["datetime"][0]:
        del out["time"]
    return out


def _float(v: str) -> Optional[float]:
    try:
        x = float(v.strip())
        return x if x == x else None
    except (ValueError, AttributeError):
        m = re.fullmatch(r"\s*(?:(\d+)m)?\s*([\d.]+)s\s*", v or "")      # DJI's "1m 5.3s"
        return (int(m.group(1) or 0) * 60 + float(m.group(2))) if m else None


def _when(v: str) -> Optional[float]:
    """Unix seconds from an ISO date-time, 'YYYY/MM/DD HH:MM:SS(.fff)', or an epoch number (s or ms). Treated as UTC."""
    v = (v or "").strip()
    if not v:
        return None
    x = _float(v)
    if x is not None:                    # epoch in s, ms, us or ns, by size
        for limit, div in ((1e17, 1e9), (1e14, 1e6), (1e11, 1e3), (1e8, 1.0)):
            if x > limit:
                return x / div
        return None
    v2 = v.replace("/", "-").replace("Z", "+00:00")
    for fmt in (None, "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M:%S", "%m-%d-%Y %I:%M:%S %p"):
        try:
            d = datetime.fromisoformat(v2) if fmt is None else datetime.strptime(v2, fmt)
        except ValueError:
            continue
        return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()
    return None


def read_csv_log(path: str):
    from aerofleet.assurance.flightlog import FlightLog, FlightLogError, _valid

    with open(path, "rb") as f:
        raw = f.read()
    if b"\x00" in raw[:4096]:
        raise FlightLogError("This .csv file is binary, not a text table")
    text = raw.decode("utf-8-sig", errors="replace")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = csv.reader(io.StringIO(text), dialect)
    headers = next(rows, None)
    if not headers:
        raise FlightLogError("The CSV file is empty")
    col = _find(headers)
    if "lat" not in col or "lon" not in col:
        raise FlightLogError("No latitude and longitude columns found. Name them latitude and longitude (see the template)")
    if "time" not in col and "datetime" not in col:
        raise FlightLogError("No time column found. Add time_s (seconds from start) or datetime (UTC)")
    log = FlightLog(format="csv")
    h_unit = col["height"][1] if "height" in col else ""
    h_scale = FT if h_unit in ("feet", "ft", "foot") or ("height" in col and "feet" in headers[col["height"][0]].lower()) else 1.0
    t_scale = 0.001 if "time" in col and ("milli" in col["time"][1] or col["time"][1] == "ms") else 1.0
    first_abs, h0, last_mode, n = None, None, None, 0
    for r in rows:
        n += 1
        if n > MAX_ROWS:
            log.notes.append(f"Only the first {MAX_ROWS} rows were read")
            break
        get = lambda k: r[col[k][0]] if k in col and col[k][0] < len(r) else ""  # noqa: E731
        lat, lon = _float(get("lat")), _float(get("lon"))
        absolute = _when(get("datetime")) if "datetime" in col else None
        rel = _float(get("time"))
        if absolute is not None:
            first_abs = absolute if first_abs is None else first_abs
            t = absolute - first_abs
        elif rel is not None:
            t = rel * t_scale
        else:
            continue
        if "mode" in col and get("mode").strip() and get("mode").strip() != last_mode:
            last_mode = get("mode").strip()
            log.modes.append((t, last_mode.upper().replace(" ", "_")))
        pct, volts = _float(get("battery")), _float(get("voltage"))
        if volts is not None and volts > 0:
            log.battery.append((t, volts, pct))
        elif pct is not None and pct > 0:       # 0% with no voltage is a battery not reporting yet, not an empty one
            log.battery.append((t, 0.0, pct))
        sats = _float(get("sats"))
        if sats is not None:
            log.gps.append((t, int(sats), _float(get("hdop")), 3 if sats >= 4 else 1))
        if lat is None or lon is None or not _valid(lat, lon):
            continue
        h = _float(get("height"))
        h = (h * h_scale) if h is not None else 0.0
        if "height" in col and _norm(headers[col["height"][0]])[0] in ("altitude", "alt"):
            h0 = h if h0 is None else h0       # an altitude column may be above sea level: use it relative to the start
            h -= h0
        log.track.append((t, lat, lon, h))
    if not log.track:
        raise FlightLogError("No rows with a valid position in the CSV file")
    log.track.sort()
    if first_abs is not None:
        log.start_utc = first_abs
    log.position_source = "CSV export"
    log.battery = [b if b[1] > 0 else (b[0], 0.0, b[2]) for b in log.battery]
    log.notes.append("Read from a CSV export: it carries no settings, no vibration and none of the autopilot's own sensor "
                     "checks, so those parts of the review are empty")
    if "datetime" not in col:
        log.notes.append("The CSV has no date-time column, so the flight's date is the upload date")
    elif "update" in _norm(headers[col["datetime"][0]])[0] or "local" in col["datetime"][1]:
        log.notes.append("Times come from the controller app's local clock and are treated as UTC; the date may be off "
                         "by the time-zone difference")
    return log


def read_gpx_log(path: str):
    import xml.etree.ElementTree as ET

    from aerofleet.assurance.flightlog import FlightLog, FlightLogError, _valid

    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as e:
        raise FlightLogError(f"Not a readable GPX file: {e}") from None
    pts = [el for el in root.iter() if el.tag.endswith("trkpt")]
    if not pts:
        raise FlightLogError("The GPX file has no track points")
    log = FlightLog(format="gpx")
    first, h0 = None, None
    for i, p in enumerate(pts[:MAX_ROWS]):
        try:
            lat, lon = float(p.get("lat")), float(p.get("lon"))
        except (TypeError, ValueError):
            continue
        ele = next((c.text for c in p if c.tag.endswith("ele")), None)
        when = next((c.text for c in p if c.tag.endswith("time")), None)
        ts = _when(when) if when else None
        if ts is not None:
            first = ts if first is None else first
        t = (ts - first) if ts is not None and first is not None else float(i)
        h = _float(ele) if ele else None
        if h is not None:
            h0 = h if h0 is None else h0
        if _valid(lat, lon):
            log.track.append((t, lat, lon, (h - h0) if h is not None and h0 is not None else 0.0))
    if not log.track:
        raise FlightLogError("No valid positions in the GPX file")
    log.start_utc = first
    log.position_source = "GPX track"
    log.notes.append("Read from a GPX track: position and time only (no battery, GPS quality, modes, settings or vibration)")
    if first is None:
        log.notes.append("The GPX points have no times; one second per point was assumed")
    return log
