"""Vibration per flight and the fleet ranking (aerofleet/assurance/vibration.py)."""
from aerofleet.assurance.flightlog import read_flight_log
from aerofleet.assurance.vibration import drone_history, fleet_ranking, flight_vibration
from tests.unit.test_assurance_flightlog import write_tlog
from tests.unit.test_assurance_ulog import TRACK, write_ulog


def test_ardupilot_and_px4_vibration_are_read_with_their_source(tmp_path):
    track = [(float(i), 18.52 + 1e-4 * i, 73.85, 20.0) for i in range(40)]
    ap = read_flight_log(write_tlog(str(tmp_path / "a.tlog"), track, vibration=lambda t: (3.0, 4.0 + (t == 30) * 20, 2.0)))
    assert ap.vibration_source == "ardupilot_vibe" and max(v for _, v in ap.vibration) == 24.0
    v = flight_vibration(ap)
    assert v["source"] == "ardupilot_vibe" and v["median"] == 4.0 and v["samples"] == 30 and v["end_margin_s"] == 10.0   # last 10 s left out
    px = read_flight_log(write_ulog(str(tmp_path / "p.ulg"), TRACK, vibration=[(1.0 + i, 5.0 + i % 3) for i in range(60)]))
    assert px.vibration_source == "px4_imu" and flight_vibration(px)["p95"] == 7.0


def test_the_end_of_the_flight_is_left_out_so_an_impact_cannot_raise_the_value(tmp_path):
    crash = [(1.0 + i, 5.0 if i < 50 else 80.0) for i in range(60)]             # calm, then an impact in the last seconds
    v = flight_vibration(read_flight_log(write_ulog(str(tmp_path / "c.ulg"), TRACK, vibration=crash)))
    assert v["end_margin_s"] == 10.0 and v["p95"] == 5.0 and v["p95_whole_flight"] > 50


def test_ranking_compares_like_with_like_and_flags_nobody():
    reviews = [{"drone_id": f"D{i}", "created_at": f"2026-10-0{k + 1}", "report": {"vibration": {"p95": i * 1.0 + k * 0.1, "source": "px4_imu"}}}
               for i in range(1, 9) for k in range(3)]
    reviews.append({"drone_id": "AP1", "created_at": "2026-10-01", "report": {"vibration": {"p95": 99.0, "source": "ardupilot_vibe"}}})
    out = fleet_ranking(reviews)
    px = [d for d in out["drones"] if d["source"] == "px4_imu"]
    assert [d["drone_id"] for d in px[:2]] == ["D8", "D7"] and px[0]["vibration_p95"] == 8.1 and px[0]["flights"] == 3
    assert px[0]["rank"] == 1 and px[0]["group_size"] == 8 and px[0]["times_group_median"] > 1.5
    # no threshold has been validated (screening lift 1.77 [1.00, 2.60]), so nothing is flagged
    assert "flagged" not in out and all("flag" not in d for d in out["drones"]) and "1.77" in out["evidence"]
    ap = next(d for d in out["drones"] if d["drone_id"] == "AP1")
    assert ap["group_size"] == 1 and ap["comparable"] is False and ap["times_group_median"] is None


def test_history_is_in_the_order_flown_not_the_order_uploaded():
    def review(i, uploaded, flown, p95):
        v = {"p95": p95, "source": "px4_imu"}
        if flown:
            v["flown_at"] = flown
        return {"id": i, "drone_id": "D1", "created_at": uploaded, "report": {"vibration": v}}
    # the roughest flight was uploaded first but flown last
    rows = [review(1, "2026-11-01T10:00", "2026-10-05T09:00+00:00", 9.0), review(2, "2026-11-01T10:01", "2026-10-01T09:00+00:00", 2.0),
            review(3, "2026-11-01T10:02", "2026-10-02T09:00+00:00", 2.2), review(4, "2026-11-01T10:03", "2026-10-03T09:00+00:00", 2.1)]
    out = drone_history(rows, "D1")
    assert [f["review_id"] for f in out["flights"]] == [2, 3, 4, 1] and "GPS time" in out["order_note"]
    assert out["latest_vs_own"] == {"latest_p95": 9.0, "earlier_median": 2.1, "earlier_flights": 3, "higher_than": 3, "times_own_median": 4.29}
    assert "0.48" in out["evidence"]                       # the study found no within-drone warning; the screen says so
    few = drone_history(rows[:2], "D1")
    assert few["latest_vs_own"] is None and "3 earlier flights" in few["message"]
    assert "upload time" in drone_history([review(5, "2026-11-02", None, 1.0), review(6, "2026-11-03", None, 1.0)], "D1")["order_note"]
    assert drone_history(rows, "nobody")["flights"] == []


def test_no_vibration_no_entry():
    assert fleet_ranking([{"drone_id": "X", "created_at": "2026", "report": {"vibration": None}}])["drones"] == []
