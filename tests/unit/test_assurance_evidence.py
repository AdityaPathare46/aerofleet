"""The evidence timeline of a flight review: facts from the log in time order, no named cause."""
from aerofleet.assurance.evidence import around_episodes, timeline

TRACK = [(100.0 + i, 18.52, 73.85, 30.0) for i in range(121)]          # 120 s of track, starting at log time 100 s
REPORT = {"episodes": [{"kind": "off_route", "start_s": 60.0, "duration_s": 15.0, "max_m": 82.4}]}


def test_events_are_in_track_time_and_in_order():
    modes = [(90.0, "AUTO"), (150.0, "LOITER")]
    battery = [(100.0 + t, 16.0 - t * 0.01, 90.0 - t * 0.7) for t in range(0, 121, 5)]
    gps = [(100.0 + t, 4 if 40 <= t < 50 else 14, 0.9, 3) for t in range(121)]
    changes = [(155.0, "FENCE_ENABLE", 1.0, 0.0), (156.0, "STAT_FLTTIME", 1.0, 2.0)]
    ev = timeline(REPORT, TRACK, modes, battery, gps, changes)
    assert [e["t_s"] for e in ev] == sorted(e["t_s"] for e in ev)
    kinds = [(e["kind"], e["t_s"]) for e in ev]
    assert ("mode", 50.0) in kinds and ev[[k for k, _ in kinds].index("mode")]["level"] == "notice"     # pilot took over from AUTO
    gps_ev = next(e for e in ev if e["kind"] == "gps")
    assert gps_ev["t_s"] == 40.0 and gps_ev["end_s"] == 50.0
    assert [e["name"] for e in ev if e["kind"] == "setting"] == ["FENCE_ENABLE"]                        # counters are not events
    assert any(e["kind"] == "battery" and "below 20%" in e["text"] for e in ev)
    assert ev[-1]["kind"] == "end" and ev[-1]["t_s"] == 120.0


def test_around_an_episode_lists_only_what_happened_near_it():
    modes = [(90.0, "AUTO"), (150.0, "LOITER")]
    gps = [(100.0 + t, 4 if 100 <= t < 110 else 14, 0.9, 3) for t in range(121)]
    ev = timeline(REPORT, TRACK, modes, gps=gps)
    (near,) = around_episodes(REPORT, ev)
    assert [e["kind"] for e in near["events"]] == ["mode"] and "pilot took control" in near["summary"]
    quiet = around_episodes({"episodes": [{"kind": "off_altitude", "start_s": 5.0, "duration_s": 3.0}]}, [])
    assert quiet[0]["summary"] == "Nothing else in the log stands out around it"


def test_no_cause_is_named():
    ev = timeline(REPORT, TRACK, [(90.0, "AUTO")])
    assert all("cause" not in e for e in ev) and not any("cause" in e["text"].lower() for e in ev)
