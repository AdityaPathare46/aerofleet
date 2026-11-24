"""CSV exports and GPX tracks from controllers whose own logs AeroFleet cannot read."""
import pytest

from aerofleet.assurance.flightlog import FlightLogError, read_flight_log
from aerofleet.assurance.flightlog_text import _norm


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_column_names_are_found_whatever_their_case_and_units():
    assert _norm("height_above_takeoff(feet)") == ("height_above_takeoff", "feet")
    assert _norm("OSD.height [ft]") == ("osdheight", "ft")
    assert _norm("BATTERY.chargeLevel [%]") == ("batterychargelevel", "%")


def test_the_aerofleet_template_reads_time_position_battery_gps_and_mode(tmp_path):
    rows = ["time_s,latitude,longitude,height_m,battery_pct,voltage_v,satellites,mode"]
    rows += [f"{i},{18.5 + i * 1e-5},{73.8},{min(i, 5)},{100 - i},{25.0 - i * 0.05},{12 if i < 20 else 4},{'AUTO' if i < 30 else 'MANUAL'}"
             for i in range(40)]
    log = read_flight_log(_write(tmp_path, "agri.csv", "\n".join(rows)))
    assert log.format == "csv" and len(log.track) == 40 and log.track[-1][3] == 5
    assert log.modes == [(0.0, "AUTO"), (30.0, "MANUAL")]
    assert log.battery[0] == (0.0, 25.0, 100.0) and log.gps[25][1] == 4
    assert any("no settings" in n for n in log.notes)


def test_airdata_style_dji_columns_convert_feet_and_milliseconds(tmp_path):
    head = "time(millisecond),datetime(utc),latitude,longitude,height_above_takeoff(feet),battery_percent,satellites,flycState"
    rows = [head] + [f"{i * 100},2026-11-10 06:30:{i // 10:02d},18.5,{73.8 + i * 1e-5},{i},90,15,P-GPS" for i in range(50)]
    log = read_flight_log(_write(tmp_path, "dji.csv", "\n".join(rows)))
    assert log.start_utc is not None and abs(log.track[-1][3] - 49 * 0.3048) < 1e-6
    assert log.track[-1][0] == pytest.approx(4.0)          # from the date-time column, which wins over elapsed ms


def test_dji_flight_record_converter_columns(tmp_path):
    head = "CUSTOM.updateTime [local],OSD.flyTime [s],OSD.latitude,OSD.longitude,OSD.height [ft],BATTERY.chargeLevel [%],OSD.gpsNum"
    rows = [head] + [f"2026/11/10 06:30:{i:02d}.000,{i},18.5,{73.8 + i * 1e-5},{10},{80 - i},{14}" for i in range(30)]
    log = read_flight_log(_write(tmp_path, "rec.csv", "\n".join(rows)))
    assert len(log.track) == 30 and log.track[0][3] == pytest.approx(3.048) and log.battery[-1][2] == 51


def test_a_csv_without_positions_or_times_is_refused_with_a_reason(tmp_path):
    with pytest.raises(FlightLogError, match="latitude"):
        read_flight_log(_write(tmp_path, "x.csv", "a,b\n1,2\n"))
    with pytest.raises(FlightLogError, match="time"):
        read_flight_log(_write(tmp_path, "y.csv", "latitude,longitude\n18.5,73.8\n"))


def test_a_gpx_track_gives_position_time_and_height_from_the_first_point(tmp_path):
    pts = "".join(f'<trkpt lat="{18.5 + i * 1e-5}" lon="73.8"><ele>{560 + i}</ele><time>2026-11-10T06:30:{i:02d}Z</time></trkpt>'
                  for i in range(20))
    gpx = f'<?xml version="1.0"?><gpx xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>{pts}</trkseg></trk></gpx>'
    log = read_flight_log(_write(tmp_path, "track.gpx", gpx))
    assert log.format == "gpx" and len(log.track) == 20 and log.track[-1][3] == 19 and log.track[-1][0] == 19
    assert log.start_utc is not None


def test_the_real_dji_flight_record_layout_with_text_and_numeric_fly_time(tmp_path):
    # Column names as in real 2024-25 DJI flight-record CSVs: epoch "timestamps_ns" in seconds, "OSD.flyTime" as text
    # ("1m 5.3s") beside "OSD.flyTime [s]", feet, and BATTERY.* columns. Rows are made up.
    head = ("timestamps_ns,OSD.flyTime,OSD.flyTime [s],OSD.latitude,OSD.longitude,OSD.height [ft],OSD.flycState,OSD.gpsNum,"
            "BATTERY.chargeLevel,BATTERY.voltage [V]")
    rows = [head] + [f"{1739843207.5 + i},{i // 60}m {i % 60}.0s,{i},33.73,{-118.33 + i * 1e-5},{min(i, 100)},P-GPS,20,{80 - i // 10},7.8"
                     for i in range(120)]
    log = read_flight_log(_write(tmp_path, "dji2025.csv", "\n".join(rows)))
    assert len(log.track) == 120 and log.track[-1][0] == pytest.approx(119)
    assert log.track[-1][3] == pytest.approx(100 * 0.3048) and log.start_utc == pytest.approx(1739843207.5)
    assert log.battery[0] == (0.0, 7.8, 80.0)


def test_fly_time_text_and_epoch_units_are_understood():
    from aerofleet.assurance.flightlog_text import _float, _when

    assert _float("1m 5.3s") == pytest.approx(65.3) and _float("0m 0.0s") == 0.0
    assert _when("1739843207.52") == pytest.approx(1739843207.52)
    assert _when("1739843207520") == pytest.approx(1739843207.52)
    assert _when("1739843207520000000") == pytest.approx(1739843207.52)
