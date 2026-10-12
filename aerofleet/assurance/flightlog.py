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
from typing import Any, Dict, List, Optional, Tuple

MAX_BYTES = 200 * 1024 * 1024
MAX_POINTS = 400_000
AUTOPILOT_INVALID = 8   # MAV_AUTOPILOT_INVALID: heartbeats from ground stations, gimbals, companions - not the flight controller
VEHICLE_TYPES = {1: "fixed wing", 2: "quadcopter", 3: "coaxial", 4: "helicopter", 10: "ground rover", 11: "boat", 12: "submarine",
                 13: "hexacopter", 14: "octocopter", 15: "tricopter", 19: "VTOL", 20: "VTOL", 21: "VTOL", 22: "VTOL", 29: "dodecacopter"}
MULTIROTORS = {"quadcopter", "hexacopter", "octocopter", "tricopter", "coaxial", "dodecacopter"}
REBOOT_GAP_S = 5.0      # the vehicle clock jumping back by more than this means the flight controller restarted


class FlightLogError(ValueError):
    pass


@dataclass
class FlightLog:
    format: str                                              # tlog | bin
    track: List[Tuple[float, float, float, float]] = field(default_factory=list)   # (t_s, lat, lon, alt above home m)
    params: Dict[str, float] = field(default_factory=dict)
    modes: List[Tuple[float, str]] = field(default_factory=list)                   # (t_s, mode) on each change
    position_source: str = ""                                # the message the track came from
    vehicle: Optional[str] = None                            # from the autopilot's heartbeat (.tlog only)
    param_changes: List[Tuple[float, str, float, float]] = field(default_factory=list)  # (t_s, name, old, new) after first sight
    battery: List[Tuple[float, float, Optional[float]]] = field(default_factory=list)   # (t_s, volts, remaining % or None)
    gps: List[Tuple[float, int, Optional[float], int]] = field(default_factory=list)     # (t_s, satellites, HDOP or None, fix type)
    notes: List[str] = field(default_factory=list)

    @property
    def duration_s(self) -> float:
        return self.track[-1][0] - self.track[0][0] if len(self.track) > 1 else 0.0

    def summary(self) -> Dict[str, Any]:
        return {"format": self.format, "points": len(self.track), "duration_s": round(self.duration_s, 1),
                "param_count": len(self.params), "modes": [{"t_s": round(t - self.track[0][0], 1) if self.track else 0.0, "mode": m}
                                                           for t, m in self.modes],
                "position_source": self.position_source, "vehicle": self.vehicle, "battery_samples": len(self.battery), "gps_samples": len(self.gps),
                "param_changes": len(self.param_changes),
                "notes": self.notes}


def _valid(lat: float, lon: float) -> bool:
    return -90 <= lat <= 90 and -180 <= lon <= 180 and not (abs(lat) < 1e-7 and abs(lon) < 1e-7)


def _set_param(log: FlightLog, t: float, name: str, value: float) -> None:
    """Keep the latest value, and remember every time a value changed after it was first seen."""
    old = log.params.get(name)
    if old is not None and abs(old - value) > 1e-6 * max(1.0, abs(old), abs(value)) and len(log.param_changes) < 2000:
        log.param_changes.append((t, name, old, value))
    log.params[name] = value


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
    wanted = (["GLOBAL_POSITION_INT", "PARAM_VALUE", "HEARTBEAT", "SYS_STATUS", "GPS_RAW_INT"] if ext == ".tlog"
              else ["POS", "GPS", "PARM", "MODE", "BAT"])
    last_mode = None
    # Telemetry logs are stamped by the recording computer; a replayed or sped-up recording (and any
    # link delay) distorts that clock. The vehicle's own clock (time since boot) is used instead, made
    # continuous across restarts. Messages without it take the time of the latest position.
    is_tlog = ext == ".tlog"
    vehicle_t, offset, last_boot, boots, system = 0.0, 0.0, None, 1, None
    while True:
        try:
            m = mlog.recv_match(type=wanted, blocking=False)
        except Exception as e:
            log.notes.append(f"Stopped at a corrupt record: {e}")
            break
        if m is None:
            break
        kind, t = m.get_type(), float(getattr(m, "_timestamp", 0.0) or 0.0)
        if is_tlog:
            if system is None and kind == "GLOBAL_POSITION_INT":
                system = m.get_srcSystem()
            if system is not None and m.get_srcSystem() != system:
                continue                                      # another vehicle or device on the same link
            if kind == "GLOBAL_POSITION_INT":
                boot = m.time_boot_ms / 1000.0
                if last_boot is not None and boot < last_boot - REBOOT_GAP_S:
                    offset, boots = vehicle_t + 1.0, boots + 1
                    offset -= boot
                last_boot, vehicle_t = boot, boot + offset
            t = vehicle_t
        # numbers only are taken from the log; free text (STATUSTEXT, MSG) is never read
        if kind == "SYS_STATUS":
            if m.voltage_battery not in (0, 65535) and len(log.battery) < MAX_POINTS:
                log.battery.append((t, m.voltage_battery / 1000.0, float(m.battery_remaining) if m.battery_remaining >= 0 else None))
            continue
        if kind == "BAT":
            if len(log.battery) < MAX_POINTS:
                pct = getattr(m, "RemPct", None)
                log.battery.append((t, float(m.Volt), float(pct) if pct is not None else None))
            continue
        if kind == "GPS_RAW_INT":
            if len(log.gps) < MAX_POINTS:
                log.gps.append((t, int(m.satellites_visible), m.eph / 100.0 if m.eph != 65535 else None, int(m.fix_type)))
            continue
        if kind == "GPS" and len(log.gps) < MAX_POINTS:
            hdop = getattr(m, "HDop", None)
            log.gps.append((t, int(getattr(m, "NSats", 0)), float(hdop) if hdop is not None else None, int(getattr(m, "Status", 0))))
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
            _set_param(log, t, name.rstrip("\x00").upper(), float(m.param_value))
            continue
        elif kind == "PARM":
            _set_param(log, t, str(m.Name).upper(), float(m.Value))
            continue
        else:  # HEARTBEAT / MODE
            if kind == "HEARTBEAT" and (m.autopilot == AUTOPILOT_INVALID or m.get_srcComponent() != 1):
                continue
            if kind == "HEARTBEAT" and log.vehicle is None:
                log.vehicle = VEHICLE_TYPES.get(int(m.type), f"type {int(m.type)}")
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
    if log.vehicle is not None and log.vehicle not in MULTIROTORS:
        log.notes.append(f"This log is from a {log.vehicle}; the planned-versus-flown comparison assumes a multirotor")
    if boots > 1:
        log.notes.append(f"The flight controller restarted {boots - 1} time(s) in this log; times run on across the restarts")
    if not log.track:
        raise FlightLogError("No position records found in the log — nothing to compare with a plan")
    return log
