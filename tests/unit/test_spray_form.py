"""The SOP spray form: what the log fills in, the fixed checks and the seven-day deadline."""
import math
from datetime import date

from aerofleet.assurance import spray_form as sf


def _report(passes=6, bearing_deg=0.0, speed=5.0, height=3.0, start="2026-11-10T06:30:00+00:00"):
    """A back-and-forth spraying pattern: passes along `bearing_deg`, 100 m long, 5 m apart, one point a second."""
    lat0, lon0, pts, t = 18.5, 73.8, [], 0.0
    k = 111_320.0 * math.cos(math.radians(lat0))
    b = math.radians(bearing_deg)
    pts.append([t, lat0, lon0, 0.0])
    for p in range(passes):
        side = 5.0 * p
        for i in range(int(100 / speed) + 1):
            along = i * speed if p % 2 == 0 else 100 - i * speed
            east = along * math.sin(b) + side * math.cos(b)
            north = along * math.cos(b) - side * math.sin(b)
            t += 1.0
            pts.append([t, lat0 + north / 111_320.0, lon0 + east / k, height])
    return {"flight_s": t, "replay": {"flown": pts}, "vibration": {"flown_at": start}}


def test_the_log_fills_date_times_height_speed_and_direction():
    log = sf.log_values(_report(bearing_deg=30.0), "2026-11-10T06:40:00")
    assert log["1-1"] == "2026-11-10" and log["4-1s"] == "2026-11-10T06:30"
    assert log["4-1e"] > log["4-1s"]
    assert log["5-7"] == 3.0                                    # above take-off, not above the crop
    assert 17.0 <= log["5-15"] <= 19.0                          # 5 m/s
    assert abs(log["4-6"] - 30) <= 2                            # passes and their returns are one axis


def test_no_direction_is_given_when_the_track_has_no_main_axis():
    rep = {"flight_s": 40.0, "vibration": {"flown_at": "2026-11-10T06:30:00+00:00"},
           "replay": {"flown": [[i, 18.5 + 1e-4 * math.sin(i / 3), 73.8 + 1e-4 * math.cos(i / 3), 5.0] for i in range(40)]}}
    assert sf.log_values(rep, "")["4-6"] is None


def test_defaults_say_where_each_value_came_from():
    log = sf.log_values(_report(), "")
    pre = sf.defaults(log, {"5-3": "Maker", "1-2": "Field A"}, "2026-11-01")
    assert pre["1-1"]["source"] == "log" and pre["5-3"] == {"value": "Maker", "source": "previous form"}
    assert "1-2" not in pre                                     # the location is never copied from another flight
    assert pre["5-6"] == {"value": "2026-11-01", "source": "logbook"} and pre["5-5"]["value"] == "Aerial"


def _full(**over):
    v = {c: None for c in sf.CODES}
    v.update({"1-1": "2026-11-10", "1-2": "Field A", "2-1": "Crop", "2-2": 1.0, "2-3": "Paddy, BPH 20%", "3-1": "X / y",
              "3-2": "5%", "3-3": "EC", "3-4": "2027-01-01", "3-5": "No", "4-1s": "2026-11-10T06:30", "4-1e": "2026-11-10T06:45",
              "4-2": 26, "4-3": 60, "4-4": 2, "4-5": 90, "4-6": 0, "5-1": "Hydraulic", "5-2": "Pilot", "5-3": "M", "5-4": "N",
              "5-5": "Aerial", "5-6": "2026-11-01", "5-7": 3, "5-10": "flat fan", "5-11": 1.5, "5-12": 4, "5-13": 5, "5-15": 18,
              "5-16": ["Ground party available"], "5-17": ["GPS"], "7-1": ["Gloves", "Mask"], "7-2": "Yes", "7-3": ["Farmers"],
              "sop-notice": "2026-11-08T10:00", "sop-water": "Yes"})
    v.update(over)
    return v


def test_a_complete_form_has_no_missing_fields_and_no_problems():
    found = sf.checks(_full(), {"1-1": "2026-11-10", "5-7": 3.0, "5-15": 18.0}, "UA123")
    assert [f for f in found if f["level"] in ("missing", "problem")] == []


def test_each_fixed_check_cites_its_rule():
    found = sf.checks(_full(**{"3-4": "2026-10-01", "7-1": ["None"], "sop-notice": "2026-11-10T00:00", "sop-water": "No",
                               "3-5": "Yes", "5-7": 8}), {"1-1": "2026-11-10", "5-7": 3.0}, None)
    codes = {f["code"]: f for f in found}
    assert codes["3-4"]["level"] == "problem" and "expired" in codes["3-4"]["text"]
    assert "4.2(ii)" in codes["7-1"]["rule"] and "4.1(xvi)" in codes["sop-notice"]["rule"]
    assert "100 m" in codes["sop-water"]["rule"] and codes["uin"]["level"] == "problem"
    assert codes["3-6"]["level"] == "missing"                    # mixed, so the ratio is needed
    assert codes["5-7"]["level"] == "note" and "log shows 3 m" in codes["5-7"]["text"]


def test_the_deadline_is_seven_days_after_spraying():
    v = _full()
    ready = sf.status(v, [], None, date(2026, 11, 12))
    assert ready == {"state": "READY", "due": "2026-11-17", "days_left": 5, "missing": 0, "problems": 0, "submitted_late_by": None}
    missing = [{"level": "missing"}]
    assert sf.status(v, missing, None, date(2026, 11, 12))["state"] == "DRAFT"
    assert sf.status(v, missing, None, date(2026, 11, 16))["state"] == "DUE_SOON"
    assert sf.status(v, [], None, date(2026, 11, 18))["state"] == "OVERDUE"
    late = sf.status(v, [], "2026-11-20", date(2026, 11, 25))
    assert late["state"] == "SUBMITTED" and late["submitted_late_by"] == 3


def test_the_printed_form_escapes_entered_text():
    page = sf.print_html([{"review_id": 1, "drone_id": "D1", "values": {"1-2": "<script>x</script>"}, "sources": {}}], "f")
    assert "<script>x" not in page and "&lt;script&gt;" in page and "SPRAY MONITORING FORM" in page


def test_a_csv_or_gpx_log_without_vibration_still_gives_its_own_date():
    rep = {"flight_s": 60.0, "log": {"start_utc": 1794292200.0}, "replay": {"flown": [[0, 18.5, 73.8, 0.0], [60, 18.5, 73.81, 3.0]]}}
    log = sf.log_values(rep, "2030-01-01T00:00:00")
    assert log["1-1"] == "2026-11-10" and log["time_source"].startswith("log")
