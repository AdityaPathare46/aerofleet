"""Fleet trends (aerofleet/assurance/trends.py)."""
from aerofleet.assurance.trends import fleet_trends


def review(drone, day, secs, warnings=0, outside=False, vib=1.0):
    rep = {"flight_s": secs, "vibration": {"p95": vib, "flown_at": f"2026-10-{day:02d}T08:00:00+00:00"},
           "evidence_timeline": [{"level": "warning", "kind": "sensor", "text": "x"}] * warnings
           + [{"level": "warning", "kind": "plan", "text": "off route"}],                 # plan episodes are not warnings
           "normal_flight": {"targets": {"battery_drop_pct_per_min": {"position": "above" if outside else "inside", "times_mid": 2.0 if outside else 1.0}}}}
    return {"drone_id": drone, "created_at": "2026-11-01T00:00:00", "report": rep}


def test_counts_hours_warnings_and_weekly_buckets():
    rows = [review("A", 1, 1800, warnings=2), review("A", 2, 1800), review("A", 3, 1800), review("A", 9, 1800, outside=True, vib=4.0),
            review("B", 9, 3600, warnings=1)]
    t = fleet_trends(rows)
    assert t["flights"] == 5 and t["drone_count"] == 2 and t["hours"] == 3.0 and t["period"] == "week"
    assert t["warnings_per_flight"] == 0.6 and t["share_outside_expected"] == 0.2
    assert sum(p["flights"] for p in t["periods"]) == 5 and len(t["periods"]) == 2
    a = next(d for d in t["drones"] if d["drone_id"] == "A")
    assert a["flights"] == 4 and a["hours"] == 2.0 and a["warnings_per_flight"] == 0.5
    assert a["latest_vibration_vs_own_median"] == 4.0 and a["battery_vs_expected_median"] == 1.0 and a["flights_outside_expected"] == 1
    assert "nothing is predicted" in t["note"]


def test_long_seasons_go_by_month_and_an_empty_fleet_says_so():
    rows = [review("A", 1, 600), {"drone_id": "A", "created_at": "2026-01-01T00:00:00",
                                  "report": {"flight_s": 600, "vibration": {"flown_at": "2026-03-01T00:00:00+00:00"}}}]
    assert fleet_trends(rows)["period"] == "month"
    assert fleet_trends([])["flights"] == 0
