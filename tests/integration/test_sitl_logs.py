"""Real ArduCopter (SITL) logs from research/sitl_check: what the reader now finds. Skipped without the data drive.

These are the development flights (run 1 of each scenario), looked at while the reader was written; the declared
retest uses fresh flights (research/sitl_check/PROTOCOL_v2.md).
"""
from collections import Counter
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration
SITL = Path("/Volumes/One Touch/AeroFleet_px4_data/sitl")
needs = pytest.mark.skipif(not SITL.exists(), reason="data drive not attached")


def _health(name):
    from aerofleet.assurance.flightlog import read_flight_log

    return Counter(w for _a, _b, w in read_flight_log(str(SITL / f"{name}.bin")).health)


@needs
def test_normal_and_windy_flights_get_no_new_warnings():
    assert _health("S0_normal_1") == Counter() and _health("S5_wind_1") == Counter()


@needs
def test_motor_failure_shows_tilt_saturation_and_the_autopilots_thrust_loss_report():
    h = _health("S6_motor_failure_1")
    assert h["Tilt above 60°"] and h["A motor held at its maximum output (saturated)"]
    assert h["Autopilot reported: thrust loss check, thrust loss detected"]


@needs
def test_compass_failure_shows_the_compass_health_flag_and_error_report():
    h = _health("S7_compass_failure_1")
    assert h["Compass 1 reported unhealthy"] == 1 and h["Autopilot reported: compass, unhealthy"] == 1


@needs
def test_an_error_report_is_a_moment_in_the_timeline():
    from aerofleet.assurance.evidence import timeline
    from aerofleet.assurance.flightlog import read_flight_log

    f = read_flight_log(str(SITL / "S7_compass_failure_1.bin"))
    ev = timeline({"episodes": []}, f.track, f.modes, f.battery, f.gps, f.param_changes, f.health)
    assert any(e["text"] == "Autopilot reported: compass, unhealthy" for e in ev)
