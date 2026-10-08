"""Read an uploaded flight log into one plain structure — the track flown, the parameters on board,
and the flight-mode changes. No drone is contacted.

Supported: ArduPilot telemetry logs (.tlog) and ArduPilot onboard DataFlash logs (.bin), both through
pymavlink. PX4 .ulg is not supported yet (needs pyulog). The .tlog path is covered by tests that build
a real log; the .bin path uses the same code with DataFlash message names and has not yet been run
against a real onboard log (MASTER_PLAN 2.1).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

MAX_BYTES = 200 * 1024 * 1024
MAX_POINTS = 400_000
GCS_TYPE = 6  # MAV_TYPE_GCS: a ground station's heartbeat says nothing about the aircraft's mode


class FlightLogError(ValueError):
    pass


@dataclass
class FlightLog:
    format: str                                              # tlog | bin
    track: List[Tuple[float, float, float, float]] = field(default_factory=list)   # (t_s, lat, lon, alt above home m)
    params: Dict[str, float] = field(default_factory=dict)
    modes: List[Tuple[float, str]] = field(default_factory=list)                   # (t_s, mode) on each change
    position_source: str = ""                                # the message the track came from
    notes: List[str] = field(default_factory=list)

    @property
    def duration_s(self) -> float:
        return self.track[-1][0] - self.track[0][0] if len(self.track) > 1 else 0.0

    def summary(self) -> Dict[str, Any]:
        return {"format": self.format, "points": len(self.track), "duration_s": round(self.duration_s, 1),
                "param_count": len(self.params), "modes": [{"t_s": round(t - self.track[0][0], 1) if self.track else 0.0, "mode": m}
                                                           for t, m in self.modes],
                "position_source": self.position_source, "notes": self.notes}


def _valid(lat: float, lon: float) -> bool:
    return -90 <= lat <= 90 and -180 <= lon <= 180 and not (abs(lat) < 1e-7 and abs(lon) < 1e-7)


def read_flight_log(path: str) -> FlightLog:
    ext = os.path.splitext(path)[1].lower()
    if ext not in (".tlog", ".bin"):
        raise FlightLogError("Unsupported log type — upload an ArduPilot .tlog or .bin file (PX4 .ulg is not supported yet)")
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        raise FlightLogError("The log file is empty")
    if os.path.getsize(path) > MAX_BYTES:
        raise FlightLogError("The log file is larger than 200 MB")
    from pymavlink import mavutil

    try:
        mlog = mavutil.mavlink_connection(path, dialect="ardupilotmega")
    except Exception as e:  # pymavlink raises many types on a corrupt header
        raise FlightLogError(f"Could not open the log: {e}") from None

    log = FlightLog(format=ext[1:])
    tracks: Dict[str, List[Tuple[float, float, float, float]]] = {}
    wanted = ["GLOBAL_POSITION_INT", "PARAM_VALUE", "HEARTBEAT"] if ext == ".tlog" else ["POS", "GPS", "PARM", "MODE"]
    last_mode = None
    while True:
        try:
            m = mlog.recv_match(type=wanted, blocking=False)
        except Exception as e:
            log.notes.append(f"Stopped at a corrupt record: {e}")
            break
        if m is None:
            break
        kind, t = m.get_type(), float(getattr(m, "_timestamp", 0.0) or 0.0)
        if kind == "GLOBAL_POSITION_INT":
            point = (t, m.lat / 1e7, m.lon / 1e7, m.relative_alt / 1000.0)
        elif kind == "POS":
            point = (t, float(m.Lat), float(m.Lng), float(getattr(m, "RelHomeAlt", 0.0)))
        elif kind == "GPS":
            if getattr(m, "Status", 3) < 3:      # no 3D fix: the position is not usable
                continue
            point = (t, float(m.Lat), float(m.Lng), float(m.Alt))
        elif kind == "PARAM_VALUE":
            name = m.param_id if isinstance(m.param_id, str) else m.param_id.decode("ascii", "ignore")
            log.params[name.rstrip("\x00").upper()] = float(m.param_value)
            continue
        elif kind == "PARM":
            log.params[str(m.Name).upper()] = float(m.Value)
            continue
        else:  # HEARTBEAT / MODE
            if kind == "HEARTBEAT" and m.type == GCS_TYPE:
                continue
            mode = mavutil.mode_string_v10(m) if kind == "HEARTBEAT" else str(getattr(mlog, "flightmode", getattr(m, "Mode", "")))
            if mode != last_mode:
                log.modes.append((t, mode))
                last_mode = mode
            continue
        if _valid(point[1], point[2]):
            bucket = tracks.setdefault(kind, [])
            if len(bucket) < MAX_POINTS:
                bucket.append(point)

    for source in ("GLOBAL_POSITION_INT", "POS", "GPS"):     # POS (EKF, height above home) before raw GPS
        if tracks.get(source):
            log.track, log.position_source = tracks[source], source
            break
    if log.position_source == "GPS":
        home = log.track[0][3]
        log.track = [(t, la, lo, alt - home) for t, la, lo, alt in log.track]
        log.notes.append("Altitude is GPS altitude relative to the first fix (no POS records in this log)")
    if not log.track:
        raise FlightLogError("No position records found in the log — nothing to compare with a plan")
    return log
