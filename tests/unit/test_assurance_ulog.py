"""PX4 .ulg logs: the reader on logs written here byte by byte to the ULog file format spec."""
import struct

import pytest

from aerofleet.assurance.flightlog import FlightLogError, read_flight_log

FORMATS = {
    "vehicle_global_position": "uint64_t timestamp;double lat;double lon;float alt;",
    "home_position": "uint64_t timestamp;float alt;",
    "vehicle_status": "uint64_t timestamp;uint8_t nav_state;uint8_t arming_state;",
    "battery_status": "uint64_t timestamp;float voltage_v;float remaining;",
    "vehicle_gps_position": "uint64_t timestamp;int32_t lat;int32_t lon;int32_t alt;uint8_t satellites_used;float hdop;uint8_t fix_type;",
}
PACK = {"vehicle_global_position": "<Qddf", "home_position": "<Qf", "vehicle_status": "<QBB",
        "battery_status": "<Qff", "vehicle_gps_position": "<QiiiBfB"}


def _msg(kind, payload):
    return struct.pack("<HB", len(payload), ord(kind)) + payload


def _param(name, value):
    key = (f"float {name}" if isinstance(value, float) else f"int32_t {name}").encode()
    return _msg("P", bytes([len(key)]) + key + struct.pack("<f" if isinstance(value, float) else "<i", value))


def write_ulog(path, track, params=(), nav_states=((0.0, 2),), battery=(), gps=True, home_alt=500.0, param_at=()):
    """track: (t_s, lat, lon, height above home m). nav_states: (t_s, PX4 nav_state). param_at: (t_s, name, value)."""
    t0 = 1_000_000
    us = lambda t: t0 + int(t * 1e6)  # noqa: E731
    out = b"ULog\x01\x12\x35" + bytes([1]) + struct.pack("<Q", t0)
    out += _msg("B", bytes(40))
    for name, fmt in FORMATS.items():
        out += _msg("F", f"{name}:{fmt}".encode())
    for name, value in params:
        out += _param(name, value)
    ids = {name: i for i, name in enumerate(FORMATS)}
    for name, i in ids.items():
        out += _msg("A", struct.pack("<BH", 0, i) + name.encode())
    events = [(0.0, "home_position", (home_alt,))]
    events += [(t, "vehicle_global_position", (lat, lon, home_alt + h)) for t, lat, lon, h in track]
    if gps:
        events += [(t, "vehicle_gps_position", (int(lat * 1e7), int(lon * 1e7), int((home_alt + h) * 1e3), 12, 0.8, 3))
                   for t, lat, lon, h in track]
    events += [(t, "vehicle_status", (n, 2)) for t, n in nav_states]
    events += [(t, "battery_status", (v, r)) for t, v, r in battery]
    events += [(t, "_param", (name, value)) for t, name, value in param_at]
    for t, name, fields in sorted(events, key=lambda e: e[0]):
        if name == "_param":
            out += _param(*fields)
            continue
        out += _msg("D", struct.pack("<H", ids[name]) + struct.pack(PACK[name], us(t), *fields))
    with open(path, "wb") as f:
        f.write(out)
    return path


TRACK = [(1.0 + i, 18.52 + 0.0001 * i, 73.85, 30.0) for i in range(60)]


def test_track_heights_params_modes_battery_and_gps_are_read(tmp_path):
    p = write_ulog(str(tmp_path / "f.ulg"), TRACK, params=[("MAV_TYPE", 2), ("COM_RCL_EXCEPT", 0), ("MPC_XY_VEL_MAX", 12.0)],
                   nav_states=[(0.0, 2), (5.0, 3), (40.0, 5)], battery=[(1.0, 16.4, 0.95), (50.0, 14.9, 0.31)])
    log = read_flight_log(p)
    assert log.format == "ulg" and len(log.track) == 60 and log.position_source == "vehicle_global_position"
    assert log.track[0][1:] == pytest.approx((18.52, 73.85, 30.0))                    # height above home, not above sea level
    assert log.params["MPC_XY_VEL_MAX"] == pytest.approx(12.0) and log.vehicle == "quadcopter"
    assert [m for _, m in log.modes] == ["POSCTL", "MISSION", "RTL"]
    assert log.battery[-1][1:] == pytest.approx((14.9, 31.0)) and log.gps[0][1:] == (12, pytest.approx(0.8), 3)


def test_a_setting_changed_in_flight_is_listed_with_its_time(tmp_path):
    p = write_ulog(str(tmp_path / "f.ulg"), TRACK, params=[("GF_ACTION", 1)], param_at=[(20.0, "GF_ACTION", 0)])
    (change,) = read_flight_log(p).param_changes
    assert change[1:] == ("GF_ACTION", 1.0, 0.0) and change[0] == pytest.approx(20.0, abs=1.5)


def test_px4_hold_is_not_taken_for_a_pilot_flown_mode(tmp_path):
    from aerofleet.assurance.reconcile import PILOT_MODES

    p = write_ulog(str(tmp_path / "f.ulg"), TRACK, nav_states=[(0.0, 3), (10.0, 4)])
    assert read_flight_log(p).modes[-1][1] == "HOLD" and "HOLD" not in PILOT_MODES


def test_a_log_without_any_position_is_refused_clearly(tmp_path):
    p = write_ulog(str(tmp_path / "f.ulg"), [], nav_states=[(0.0, 2)], gps=False)
    with pytest.raises(FlightLogError, match="No position"):
        read_flight_log(p)
    (tmp_path / "bad.ulg").write_bytes(b"not a ulog at all")
    with pytest.raises(FlightLogError):
        read_flight_log(str(tmp_path / "bad.ulg"))
