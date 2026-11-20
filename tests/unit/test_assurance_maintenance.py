"""Maintenance logbook: flights before vs after the work (aerofleet/assurance/maintenance.py)."""
from aerofleet.assurance.maintenance import effect, flight_points


def review(i, day, p95, batt=None, source="px4_imu"):
    rep = {"vibration": {"p95": p95, "source": source, "flown_at": f"2026-10-{day:02d}T08:00:00+00:00"}}
    if batt is not None:
        rep["normal_flight"] = {"targets": {"battery_drop_pct_per_min": {"times_mid": batt}}}
    return {"id": i, "drone_id": "D1", "created_at": "2026-11-01T00:00:00", "report": rep}


ROWS = [review(1, 1, 9.0, 2.0), review(2, 2, 10.0, 2.2), review(3, 3, 11.0, 1.8), review(4, 4, 99.0, 9.0, source="px4_estimator"),
        review(5, 10, 4.0, 1.0), review(6, 11, 5.0, 1.2), {"id": 7, "drone_id": "OTHER", "created_at": "2026-10-05", "report": {}}]


def test_the_three_flights_each_side_are_compared_in_the_order_flown():
    pts = flight_points(ROWS, "D1")
    assert [p["review_id"] for p in pts] == [1, 2, 3, 4, 5, 6]
    e = effect(pts, "2026-10-06T00:00:00")
    vib = next(m for m in e["measures"] if m["label"].startswith("Vibration"))
    # only the same vibration measurement is compared: flight 4 (another source) is left out of the "before" side
    assert vib["before"] == 10.5 and vib["after"] == 4.5 and vib["flights_before"] == 2 and vib["change_pct"] == -57
    batt = next(m for m in e["measures"] if m["label"].startswith("Battery"))
    assert batt["flights_before"] == 3 and batt["before"] == 2.2 and batt["after"] == 1.1
    assert "fell 57%" in e["summary"] and "cannot prove" in e["note"]


def test_nothing_is_claimed_without_flights_on_both_sides():
    pts = flight_points(ROWS, "D1")
    assert "No flight reviewed since" in effect(pts, "2026-10-20T00:00:00")["summary"]
    assert "nothing to compare" in effect(pts, "2026-09-01T00:00:00")["summary"]
    assert effect(pts, "2026-10-20T00:00:00")["measures"] == []
