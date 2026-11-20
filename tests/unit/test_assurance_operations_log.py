"""Operations log rows (aerofleet/assurance/operations_log.py)."""
from aerofleet.assurance.operations_log import COLUMNS, row, to_csv

D = 100 / 111_320.0          # about 100 m in latitude degrees


def test_a_square_field_gives_its_area_distance_and_take_off_point():
    lat, lon = 18.5, 73.8
    dlon = D / __import__("math").cos(__import__("math").radians(lat))
    square = [[0, lat, lon, 0], [10, lat, lon + dlon, 5], [20, lat + D, lon + dlon, 6], [30, lat + D, lon, 5], [40, lat, lon, 0]]
    rep = {"flight_s": 600, "replay": {"flown": square}, "vibration": {"flown_at": "2026-11-20T06:30:00+00:00"},
           "evidence_timeline": [{"level": "warning", "kind": "battery", "text": "Battery below 10%"}, {"level": "warning", "kind": "plan", "text": "x"}],
           "normal_flight": {"targets": {"battery_drop_pct_per_min": {"position": "above"}, "vibration": {"position": "inside"}}}}
    r = row({"id": 7, "drone_id": "SPRAY-1", "created_at": "2026-11-20T10:00:00", "report": rep, "log_name": "a.ulg"}, "UA-1", "ab" * 32)
    assert r["outline_area_ha"] == 1.0 and r["distance_km"] == 0.4 and r["flight_min"] == 10.0     # 100 m x 100 m = 1 ha
    assert r["date_utc"] == "2026-11-20 06:30:00" and r["take_off_lat"] == 18.5 and r["max_height_m"] == 6
    assert r["warnings"] == 1 and r["outside_expected"] == "battery_drop_pct_per_min" and r["uin"] == "UA-1"
    text = to_csv([r])
    assert text.splitlines()[0] == ",".join(COLUMNS) and "SPRAY-1" in text and "ab" * 32 in text
