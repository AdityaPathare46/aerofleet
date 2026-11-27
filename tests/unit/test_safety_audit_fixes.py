"""Regression tests for the critical safety and engineering audit fixes (27 Nov 2026)."""
from types import SimpleNamespace

import pytest

from aerofleet.assurance import evidence, flightlog, ledger, maintenance, readiness, reconcile, wind
from aerofleet.integrations.mission_planner import build_waypoint_file

pytestmark = pytest.mark.unit


def test_reconcile_reports_matching_mode_truthfully():
    home, dest = (18.5200, 73.8500), (18.5290, 73.8500)
    plan = reconcile.parse_waypoints(
        build_waypoint_file({"origin_lat": home[0], "origin_lon": home[1], "dest_lat": dest[0], "dest_lon": dest[1], "altitude_m": 40.0})
    )
    track = [(float(i), home[0] + (dest[0] - home[0]) * i / 30, home[1], 40.0) for i in range(31)]
    assert reconcile.reconcile(plan, track, ordered=True)["tolerances"]["matching"] == "in flying order"
    assert reconcile.reconcile(plan, track, ordered=False)["tolerances"]["matching"] == "nearest leg anywhere"


def test_low_altitude_and_downslope_spraying_still_flags_in_air_warnings():
    # Agricultural drone spraying downhill at -1.0 m relative to take-off at ~5 m/s (0.000045 deg/s north)
    track = [(float(t), 18.5200 + t * 0.000045, 73.8500, -1.0 if 10 <= t < 50 else 0.0) for t in range(60)]
    # Stationary for t < 10 and t >= 50
    for i in range(10):
        track[i] = (float(i), 18.5200, 73.8500, 0.0)
    for i in range(50, 60):
        track[i] = (float(i), track[49][1], 73.8500, 0.0)
    ev = evidence.timeline({"episodes": []}, track, [], health=[(20.0, 26.0, "Estimator rejected compass data")])
    sensor = [e for e in ev if e["kind"] == "sensor"]
    assert len(sensor) == 1 and sensor[0]["level"] == "warning"


def test_mid_air_critical_battery_is_a_warning_while_landing_below_10pct_is_pilot_note():
    track = [(float(t), 18.5, 73.8, 15.0 if 10 <= t < 80 else 0.0) for t in range(90)]
    # Mid-air critical battery at t=30 s (50 s before touchdown)
    ev_mid = evidence.timeline({"episodes": []}, track, [], battery=[(10.0, 22.0, 80.0), (30.0, 19.5, 8.0), (80.0, 19.2, 7.0)])
    s_mid = readiness.last_flight_summary(1, {"evidence_timeline": ev_mid}, "2026-11-27T00:00:00")
    assert len(s_mid["warnings"]) == 1 and s_mid["pilot_notes"] == []
    # Landing low battery at t=75 s (5 s before touchdown)
    ev_land = evidence.timeline({"episodes": []}, track, [], battery=[(10.0, 22.0, 80.0), (75.0, 20.1, 9.0), (80.0, 20.0, 8.0)])
    s_land = readiness.last_flight_summary(2, {"evidence_timeline": ev_land}, "2026-11-27T00:00:00")
    assert s_land["warnings"] == [] and len(s_land["pilot_notes"]) == 1


def test_readiness_no_reference_grounded_partial_log_and_circuit_breakers():
    verified = {"uin": "UA-123", "status": "VERIFIED"}
    ok_settings = {"verdict": "OK", "critical": [], "limits": []}

    # NO_REFERENCE is never a silent READY pass
    r_noref = readiness.assess("D1", {"verdict": "NO_REFERENCE", "critical": [], "limits": []}, verified, None)
    assert r_noref["status"] == readiness.CHECK_FIRST and r_noref["reasons"][0]["code"] == "no_baseline"

    # Grounded incident -> DO_NOT_FLY until cleared
    entries = [{"id": 1, "done_at": "2026-11-26T10:00:00", "action": maintenance.GROUNDING_ACTION, "note": "Hard landing", "done_by": "op"}]
    g = maintenance.is_grounded(entries)
    assert g is not None
    r_g = readiness.assess("D1", ok_settings, verified, None, grounded=g)
    assert r_g["status"] == readiness.DO_NOT_FLY and r_g["reasons"][0]["code"] == "grounded_incident"
    entries.append({"id": 2, "done_at": "2026-11-27T08:00:00", "action": maintenance.CLEARANCE_ACTION, "note": "Props replaced", "done_by": "op"})
    assert maintenance.is_grounded(entries) is None

    # Partial CSV/GPX log -> CHECK_FIRST
    s_csv = readiness.last_flight_summary(3, {"log": {"format": "csv"}, "evidence_timeline": []}, "2026-11-27T00:00:00")
    assert s_csv["partial_log"] is True
    r_csv = readiness.assess("D1", ok_settings, verified, s_csv)
    assert r_csv["status"] == readiness.CHECK_FIRST and any(x["code"] == "partial_log" for x in r_csv["reasons"])

    # PX4 circuit breakers & ArduPilot ARMING_CHECK=0 are caught by failsafes_off
    off_px4 = {f["name"] for f in readiness.failsafes_off({"CBRK_IO_SAFETY": 22027, "CBRK_SUPPLY_CHK": 894281})}
    assert off_px4 == {"CBRK_SUPPLY_CHK"}


def test_px4_default_bypasses_are_notes_not_reasons():
    """C1 (critical review 27 Nov 2026): PX4 ships CBRK_FLIGHTTERM=121212 and, on recent firmware, CBRK_IO_SAFETY=22027.
    Flagging them put 199 of 200 public PX4 drones on Check first."""
    stock = {"CBRK_FLIGHTTERM": 121212, "CBRK_IO_SAFETY": 22027, "NAV_RCL_ACT": 2, "COM_LOW_BAT_ACT": 3, "GF_ACTION": 1,
             "CBRK_SUPPLY_CHK": 0}
    assert readiness.failsafes_off(stock) == []
    assert readiness.setting_notes(stock) == ["Hardware safety switch bypassed (PX4 default on recent firmware) (CBRK_IO_SAFETY = 22027)"]
    assert readiness.setting_notes({"CBRK_IO_SAFETY": 0}) == [] and readiness.setting_notes({}) == []
    assert readiness.failsafes_off({"NAV_RCL_ACT": "0.0"})[0]["name"] == "NAV_RCL_ACT"     # string values read as numbers
    off_ap = {f["name"] for f in readiness.failsafes_off({"ARMING_CHECK": 0})}
    assert "ARMING_CHECK" in off_ap


def test_ardupilot_ekf3_follows_primary_core_switch():
    ap = flightlog._ApHealth()
    ap.add("ERR", 5.0, SimpleNamespace(Subsys=24, ECode=1))   # switched primary EKF3 core to 1
    for t in range(10, 16):
        ap.add("XKF4", float(t), SimpleNamespace(C=0, SV=0.1, SP=0.1, SH=0.1, SM=0.1))
        ap.add("XKF4", float(t), SimpleNamespace(C=1, SV=1.8, SP=0.2, SH=0.2, SM=0.2))
    runs = ap.runs({})
    assert any("velocity" in what for _, _, what in runs)


def test_wind_agri_sprayer_profile_is_physically_realistic_and_notes_low_altitude():
    home, north = (18.5200, 73.8500), (18.5290, 73.8500)  # ~1 km out, 1 km back = 2 km total
    plan_low = reconcile.parse_waypoints(
        build_waypoint_file({"origin_lat": home[0], "origin_lon": home[1], "dest_lat": north[0], "dest_lon": north[1], "altitude_m": 4.0})
    )
    prof = {10: (2.0, 0.0), 80: (6.0, 0.0), 120: (8.0, 0.0), 180: (10.0, 0.0)}
    res = wind.wind_check(plan_low, payload_kg=10.0, usable_wh=400.0, profile=prof, airframe_profile="agri_sprayer_10l")
    # 10 L sprayer at 10 kg payload draws 3400 W at 5 m/s over ~2 km (~400 s) -> ~378 Wh still air (not 17.5 Wh!)
    assert 350.0 < res["still_air"]["energy_wh"] < 410.0
    assert res["airframe"]["profile"] == "agri_sprayer_10l" and res["airframe"]["cruise_speed_mps"] == 5.0
    assert res["low_altitude_note"] is not None
    # With 2 m/s head/tail wind at 5 m/s airspeed, energy rises above 400 Wh -> FAIL
    assert res["verdict"] == "FAIL"


def test_empty_ledger_receipt_roundtrips():
    pem = ledger.public_key_pem()
    body = {"aerofleet_receipt": 1, "seq": 0, "entry_hash": ledger.GENESIS, "entry_created_at": None,
            "issued_at": "2026-11-27T00:00:00", "key_sha256": ledger.key_fingerprint(pem)}
    import base64
    import hashlib
    sig = base64.b64encode(ledger._private_key().sign(hashlib.sha256(ledger.canonical(body)).digest())).decode()
    receipt = {**body, "signature": sig}
    checked = ledger.check_receipt([], pem, receipt)
    assert checked["ok"] is True and checked["entries_since"] == 0
