"""Read an uploaded flight log into one plain structure — the track flown, the parameters on board,
and the flight-mode changes. No drone is contacted.

Supported: ArduPilot telemetry logs (.tlog) and onboard DataFlash logs (.bin), through pymavlink, and
PX4 onboard logs (.ulg), through pyulog. The .tlog and .ulg paths are covered by tests that build a real
log; .bin and .ulg have also been run on real logs (ArduPilot autotest logs, PX4 Flight Review logs).
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
    format: str                                              # tlog | bin | ulg
    track: List[Tuple[float, float, float, float]] = field(default_factory=list)   # (t_s, lat, lon, alt above home m)
    params: Dict[str, float] = field(default_factory=dict)
    modes: List[Tuple[float, str]] = field(default_factory=list)                   # (t_s, mode) on each change
    position_source: str = ""                                # the message the track came from
    vehicle: Optional[str] = None                            # from the autopilot's heartbeat (.tlog only)
    param_changes: List[Tuple[float, str, float, float]] = field(default_factory=list)  # (t_s, name, old, new) after first sight
    battery: List[Tuple[float, float, Optional[float]]] = field(default_factory=list)   # (t_s, volts, remaining % or None)
    gps: List[Tuple[float, int, Optional[float], int]] = field(default_factory=list)     # (t_s, satellites, HDOP or None, fix type)
    vibration: List[Tuple[float, float]] = field(default_factory=list)   # (t_s, worst axis) — units depend on the source
    vibration_source: Optional[str] = None                   # ardupilot_vibe | px4_imu | px4_estimator: compare only like with like
    notes: List[str] = field(default_factory=list)

    @property
    def duration_s(self) -> float:
        return self.track[-1][0] - self.track[0][0] if len(self.track) > 1 else 0.0

    def summary(self) -> Dict[str, Any]:
        return {"format": self.format, "points": len(self.track), "duration_s": round(self.duration_s, 1),
                "param_count": len(self.params), "modes": [{"t_s": round(t - self.track[0][0], 1) if self.track else 0.0, "mode": m}
                                                           for t, m in self.modes],
                "position_source": self.position_source, "vehicle": self.vehicle, "battery_samples": len(self.battery), "gps_samples": len(self.gps),
                "param_changes": len(self.param_changes), "vibration_samples": len(self.vibration),
                "vibration_source": self.vibration_source,
                "notes": self.notes}


def _valid(lat: float, lon: float) -> bool:
    return -90 <= lat <= 90 and -180 <= lon <= 180 and not (abs(lat) < 1e-7 and abs(lon) < 1e-7)


def _set_param(log: FlightLog, t: float, name: str, value: float) -> None:
    """Keep the latest value, and remember every time a value changed after it was first seen."""
    old = log.params.get(name)
    if old is not None and abs(old - value) > 1e-6 * max(1.0, abs(old), abs(value)) and len(log.param_changes) < 2000:
        log.param_changes.append((t, name, old, value))
    log.params[name] = value


# PX4 vehicle_status.nav_state. PX4's automatic "hold" is called HOLD here so it is not mistaken for
# ArduPilot's pilot-flown LOITER.
PX4_NAV_STATES = {0: "MANUAL", 1: "ALTCTL", 2: "POSCTL", 3: "MISSION", 4: "HOLD", 5: "RTL", 6: "RC_RECOVER", 7: "RTGS",
                  8: "LAND_ENG_FAIL", 9: "LAND_GPS_FAIL", 10: "ACRO", 12: "DESCEND", 13: "TERMINATION", 14: "OFFBOARD",
                  15: "STABILIZE", 16: "RATTITUDE", 17: "TAKEOFF", 18: "LAND", 19: "FOLLOW", 20: "PRECLAND", 21: "ORBIT",
                  22: "VTOL_TAKEOFF"}
ULOG_TOPICS = ["vehicle_global_position", "home_position", "vehicle_gps_position", "sensor_gps", "vehicle_status",
               "battery_status", "vehicle_imu_status", "estimator_status"]


def _read_ulog(path: str) -> FlightLog:
    """PX4 onboard log. Times are seconds since the log started; only numbers are read (no logged text)."""
    from pyulog import ULog

    try:
        u = ULog(path, message_name_filter_list=ULOG_TOPICS)
    except Exception as e:  # pyulog raises many types on a damaged file
        raise FlightLogError(f"Could not open the log: {e}") from None
    t0 = u.start_timestamp
    sec = lambda ts: (float(ts) - t0) / 1e6  # noqa: E731
    data = {}
    for d in u.data_list:
        if d.name not in data or d.multi_id == 0:
            data[d.name] = d.data
    log = FlightLog(format="ulg")
    log.params = {k.upper(): float(v) for k, v in u.initial_parameters.items()}
    for ts, name, value in u.changed_parameters:
        if ts > t0:
            _set_param(log, sec(ts), name.upper(), float(value))
    mav_type = log.params.get("MAV_TYPE")
    if mav_type is not None:
        log.vehicle = VEHICLE_TYPES.get(int(mav_type), f"type {int(mav_type)}")

    gp = data.get("vehicle_global_position")
    if gp is not None and len(gp["timestamp"]):
        home = data.get("home_position")
        if home is not None and len(home["timestamp"]) and "alt" in home:
            home_alt = float(home["alt"][0])
        else:
            home_alt = float(gp["alt"][0])
            log.notes.append("No home position in this log; heights are relative to the first position")
        step = max(1, len(gp["timestamp"]) // MAX_POINTS + 1)
        log.track = [(sec(t), float(la), float(lo), float(al) - home_alt)
                     for t, la, lo, al in zip(gp["timestamp"][::step], gp["lat"][::step], gp["lon"][::step], gp["alt"][::step])
                     if _valid(float(la), float(lo))]
        log.position_source = "vehicle_global_position"
    g = data.get("vehicle_gps_position", data.get("sensor_gps"))
    if g is not None:
        lat = g["latitude_deg"] if "latitude_deg" in g else g["lat"] / 1e7
        lon = g["longitude_deg"] if "longitude_deg" in g else g["lon"] / 1e7
        alt = g["altitude_msl_m"] if "altitude_msl_m" in g else g["alt"] / 1e3
        sats = g["satellites_used"]
        hdop = g["hdop"] if "hdop" in g else [None] * len(sats)
        for t, n, h, fix in list(zip(g["timestamp"], sats, hdop, g["fix_type"]))[:MAX_POINTS]:
            log.gps.append((sec(t), int(n), float(h) if h is not None else None, int(fix)))
        if not log.track:
            pts = [(sec(t), float(la), float(lo), float(al)) for t, la, lo, al, fix in
                   zip(g["timestamp"], lat, lon, alt, g["fix_type"]) if fix >= 3 and _valid(float(la), float(lo))][:MAX_POINTS]
            if pts:
                log.track = [(t, la, lo, al - pts[0][3]) for t, la, lo, al in pts]
                log.position_source = "vehicle_gps_position"
                log.notes.append("Altitude is GPS altitude relative to the first fix (no estimator position in this log)")
    b = data.get("battery_status")
    if b is not None:
        volts = b["voltage_v"] if "voltage_v" in b else b.get("voltage_filtered_v")
        if volts is not None:
            for t, v, r in list(zip(b["timestamp"], volts, b.get("remaining", [None] * len(volts))))[:MAX_POINTS]:
                if v > 0:
                    log.battery.append((sec(t), float(v), float(r) * 100.0 if r is not None and r >= 0 else None))
    imu, est = data.get("vehicle_imu_status"), data.get("estimator_status")
    if imu is not None and "accel_vibration_metric" in imu:
        log.vibration = [(sec(t), float(v)) for t, v in list(zip(imu["timestamp"], imu["accel_vibration_metric"]))[:MAX_POINTS]]
        log.vibration_source = "px4_imu"
    elif est is not None and "vibe[1]" in est:
        log.vibration = [(sec(t), float(v)) for t, v in list(zip(est["timestamp"], est["vibe[1]"]))[:MAX_POINTS]]
        log.vibration_source = "px4_estimator"
    st = data.get("vehicle_status")
    if st is not None:
        last = None
        for t, n in zip(st["timestamp"], st["nav_state"]):
            mode = PX4_NAV_STATES.get(int(n), f"NAV_STATE_{int(n)}")
            if mode != last:
                log.modes.append((sec(t), mode))
                last = mode
    if log.vehicle is not None and log.vehicle not in MULTIROTORS:
        log.notes.append(f"This log is from a {log.vehicle}; the planned-versus-flown comparison assumes a multirotor")
    if not log.track:
        raise FlightLogError("No position records found in the log — nothing to compare with a plan")
    return log


def read_flight_log(path: str) -> FlightLog:
    ext = os.path.splitext(path)[1].lower()
    if ext not in (".tlog", ".bin", ".ulg"):
        raise FlightLogError("Unsupported log type — upload an ArduPilot .tlog or .bin file, or a PX4 .ulg file")
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        raise FlightLogError("The log file is empty")
    if os.path.getsize(path) > MAX_BYTES:
        raise FlightLogError("The log file is larger than 200 MB")
    if ext == ".ulg":
        return _read_ulog(path)
    from pymavlink import mavutil

    try:
        mlog = mavutil.mavlink_connection(path, dialect="ardupilotmega")
    except Exception as e:  # pymavlink raises many types on a corrupt header
        raise FlightLogError(f"Could not open the log: {e}") from None

    log = FlightLog(format=ext[1:])
    tracks: Dict[str, List[Tuple[float, float, float, float]]] = {}
    wanted = (["GLOBAL_POSITION_INT", "PARAM_VALUE", "HEARTBEAT", "SYS_STATUS", "GPS_RAW_INT", "VIBRATION"] if ext == ".tlog"
              else ["POS", "GPS", "PARM", "MODE", "BAT", "VIBE"])
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
        if kind in ("VIBRATION", "VIBE"):                      # same ArduPilot measurement in telemetry and onboard logs
            if len(log.vibration) < MAX_POINTS:
                axes = (m.vibration_x, m.vibration_y, m.vibration_z) if kind == "VIBRATION" else (m.VibeX, m.VibeY, m.VibeZ)
                log.vibration.append((t, float(max(axes))))
                log.vibration_source = "ardupilot_vibe"
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
