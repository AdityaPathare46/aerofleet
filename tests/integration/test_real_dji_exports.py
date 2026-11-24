"""Real DJI flight-record CSV exports (public, downloaded on 24 Nov 2026), reviewed end to end.

Files: three DJI Mini 4 Pro flights from the Hugging Face dataset nominal-io/dji-drone-telemetry (MIT licence) and a
10-row 2017 Mavic fragment from a public GitHub gist, kept on the data drive (not in the repository). Skipped when the
drive is not attached.
"""
from pathlib import Path

import pytest

from aerofleet.assurance import spray_form as sf

pytestmark = pytest.mark.integration
FOLDER = Path("/Volumes/One Touch/AeroFleet_px4_data/external/dji_samples")
FLIGHTS = {"hf_colorado_2024-08-02.csv": (120.2, "2024-08-03"), "hf_ocean_2024-06-29.csv": (61.6, "2024-06-29"),
           "hf_palos_verdes_2025-02-17.csv": (119.8, "2025-02-18")}
needs_drive = pytest.mark.skipif(not FOLDER.exists(), reason="data drive with the DJI samples not attached")


@needs_drive
@pytest.mark.parametrize("name", sorted(FLIGHTS))
def test_a_real_dji_export_is_reviewed_with_its_date_height_modes_and_battery(api_client, auth_headers, name):
    data = (FOLDER / name).read_bytes()
    r = api_client.post("/api/v1/assurance/fleets/dji-real/drones/MINI4/flights", headers=auth_headers,
                        files={"log": (name, data, "text/csv")})
    assert r.status_code == 200, r.text
    rep = r.json()["report"]
    top, day = FLIGHTS[name]
    assert rep["max_height_m"]["flown"] == pytest.approx(top, abs=0.2)       # the file's own OSD.heightMax column
    assert rep["log"]["format"] == "csv" and rep["log"]["battery_samples"] > 100 and rep["log"]["gps_samples"] > 100
    modes = [m["mode"] for m in rep["log"]["modes"]]
    assert "AUTO_TAKEOFF" in modes and "AUTO_LANDING" in modes
    assert not [e for e in rep["evidence_timeline"] if e["kind"] == "battery" and e["level"] == "warning"]   # ended at 37-50%
    assert sf.log_values(rep, "2030-01-01T00:00:00")["1-1"] == day


@needs_drive
def test_a_fragment_with_a_battery_not_yet_reporting_gives_no_battery_warning():
    from aerofleet.assurance.flightlog import read_flight_log

    log = read_flight_log(str(FOLDER / "gist_2017-04-16.csv"))
    assert log.battery == [] and any("local clock" in n for n in log.notes)
