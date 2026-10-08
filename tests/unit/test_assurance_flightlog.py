"""Flight-log reading (aerofleet/assurance/flightlog.py) — on a real .tlog built with pymavlink."""
import struct

import pytest

from aerofleet.assurance.flightlog import FlightLogError, read_flight_log

pytestmark = pytest.mark.unit


def write_tlog(path, track, params=(), modes=(), gcs_heartbeats=True):
    """A telemetry log is a sequence of [8-byte big-endian microsecond timestamp][MAVLink packet]."""
    from pymavlink.dialects.v20 import ardupilotmega as mav

    link = mav.MAVLink(None, srcSystem=1, srcComponent=1)
    t0 = 1_760_000_000.0
    with open(path, "wb") as f:
        def put(t, msg):
            f.write(struct.pack(">Q", int((t0 + t) * 1e6)) + msg.pack(link))

        for i, (name, value) in enumerate(params):
            put(0.0, mav.MAVLink_param_value_message(name.encode(), value, mav.MAV_PARAM_TYPE_REAL32, len(params), i))
        mode_at = dict(modes)
        custom = 0
        for t, lat, lon, alt in track:
            if t in mode_at:
                custom = mode_at[t]
            put(t, mav.MAVLink_heartbeat_message(mav.MAV_TYPE_QUADROTOR, mav.MAV_AUTOPILOT_ARDUPILOTMEGA,
                                                 mav.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, custom, mav.MAV_STATE_ACTIVE, 3))
            if gcs_heartbeats:
                put(t, mav.MAVLink_heartbeat_message(mav.MAV_TYPE_GCS, mav.MAV_AUTOPILOT_INVALID, 0, 0, 0, 3))
            put(t, mav.MAVLink_global_position_int_message(int(t * 1000), int(lat * 1e7), int(lon * 1e7),
                                                           int((560 + alt) * 1000), int(alt * 1000), 0, 0, 0, 0))
    return path


TRACK = [(float(i), 18.5200 + i * 1e-5, 73.8500, min(i * 2.0, 40.0)) for i in range(60)]


def test_reads_track_parameters_and_mode_changes(tmp_path):
    p = write_tlog(str(tmp_path / "flight.tlog"), TRACK, params=[("FS_THR_ENABLE", 1.0), ("RTL_ALT", 1500.0)],
                   modes=[(0.0, 5), (10.0, 3), (50.0, 6)])     # ArduCopter: 5 LOITER, 3 AUTO, 6 RTL
    log = read_flight_log(p)
    assert log.format == "tlog" and log.position_source == "GLOBAL_POSITION_INT"
    assert len(log.track) == 60 and log.duration_s == pytest.approx(59.0, abs=0.01)
    t, lat, lon, alt = log.track[30]
    assert lat == pytest.approx(18.5203, abs=1e-6) and lon == pytest.approx(73.85, abs=1e-6) and alt == pytest.approx(40.0)
    assert log.params == {"FS_THR_ENABLE": 1.0, "RTL_ALT": 1500.0}
    assert [m for _, m in log.modes] == ["LOITER", "AUTO", "RTL"]          # the ground station's heartbeats are ignored
    s = log.summary()
    assert s["points"] == 60 and [m["t_s"] for m in s["modes"]] == [0.0, 10.0, 50.0]


def test_points_without_a_position_are_dropped(tmp_path):
    track = [(0.0, 0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0)] + TRACK[2:10]
    assert len(read_flight_log(write_tlog(str(tmp_path / "f.tlog"), track)).track) == 8


def test_clear_errors_for_unusable_files(tmp_path):
    with pytest.raises(FlightLogError, match="Unsupported log type"):
        read_flight_log(str(tmp_path / "flight.ulg"))
    empty = tmp_path / "empty.tlog"
    empty.write_bytes(b"")
    with pytest.raises(FlightLogError, match="empty"):
        read_flight_log(str(empty))
    no_pos = write_tlog(str(tmp_path / "nopos.tlog"), [(0.0, 0.0, 0.0, 0.0)])
    with pytest.raises(FlightLogError, match="No position records"):
        read_flight_log(no_pos)
