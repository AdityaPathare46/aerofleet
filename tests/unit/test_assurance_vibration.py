"""Vibration per flight and the fleet ranking (aerofleet/assurance/vibration.py)."""
from aerofleet.assurance.flightlog import read_flight_log
from aerofleet.assurance.vibration import fleet_ranking, flight_vibration
from tests.unit.test_assurance_flightlog import write_tlog
from tests.unit.test_assurance_ulog import TRACK, write_ulog


def test_ardupilot_and_px4_vibration_are_read_with_their_source(tmp_path):
    track = [(float(i), 18.52 + 1e-4 * i, 73.85, 20.0) for i in range(40)]
    ap = read_flight_log(write_tlog(str(tmp_path / "a.tlog"), track, vibration=lambda t: (3.0, 4.0 + (t == 30) * 20, 2.0)))
    assert ap.vibration_source == "ardupilot_vibe" and max(v for _, v in ap.vibration) == 24.0
    v = flight_vibration(ap)
    assert v["source"] == "ardupilot_vibe" and v["median"] == 4.0 and v["samples"] == 40
    px = read_flight_log(write_ulog(str(tmp_path / "p.ulg"), TRACK, vibration=[(1.0 + i, 5.0 + i % 3) for i in range(60)]))
    assert px.vibration_source == "px4_imu" and flight_vibration(px)["p95"] == 7.0


def test_ranking_compares_like_with_like_and_flags_the_roughest_quarter():
    reviews = [{"drone_id": f"D{i}", "created_at": f"2026-10-0{k + 1}", "report": {"vibration": {"p95": i * 1.0 + k * 0.1, "source": "px4_imu"}}}
               for i in range(1, 9) for k in range(3)]
    reviews.append({"drone_id": "AP1", "created_at": "2026-10-01", "report": {"vibration": {"p95": 99.0, "source": "ardupilot_vibe"}}})
    out = fleet_ranking(reviews)
    px = [d for d in out["drones"] if d["source"] == "px4_imu"]
    assert [d["drone_id"] for d in px[:2]] == ["D8", "D7"] and px[0]["vibration_p95"] == 8.1 and px[0]["flights"] == 3
    assert out["flagged"] == ["D8", "D7"]                                   # above the upper quartile; AP1 is alone in its group
    ap = next(d for d in out["drones"] if d["drone_id"] == "AP1")
    assert ap["group_size"] == 1 and ap["flag"] is False


def test_ties_and_an_even_fleet_flag_nobody():
    even = [{"drone_id": f"E{i}", "created_at": "2026-10-01", "report": {"vibration": {"p95": 0.027 if i < 4 else 0.025, "source": "px4_imu"}}}
            for i in range(6)]
    assert fleet_ranking(even)["flagged"] == []


def test_no_vibration_no_entry():
    assert fleet_ranking([{"drone_id": "X", "created_at": "2026", "report": {"vibration": None}}])["drones"] == []
