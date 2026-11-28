"""Tests for DGCA Drone Rules 2021 compliance (Rule 44 insurance, Rule 34 RPC), Rule 45 48h accident dossier,
and fleet maintenance service intervals."""
from datetime import date, datetime, timezone

from aerofleet.assurance.accident_report import accident_dossier_html, build_accident_dossier
from aerofleet.assurance.readiness import CHECK_FIRST, DO_NOT_FLY, READY, assess
from aerofleet.assurance.trends import fleet_trends


def test_rule44_insurance_and_rule34_rpc_enforcement():
    ref = date(2026, 11, 27)
    ok_settings = {"verdict": "OK", "critical": [], "limits": [], "failsafes_off": []}
    ok_reg = {"uin": "UA001", "status": "VERIFIED"}

    # Valid compliance -> READY
    r_ok = assess("D1", ok_settings, ok_reg, None,
                  compliance={"insurance_valid_until": "2027-06-01", "pilot_rpc_valid_until": "2030-01-01"}, today=ref)
    assert r_ok["status"] == READY

    # Expiring within 14 days -> CHECK_FIRST
    r_soon = assess("D1", ok_settings, ok_reg, None,
                    compliance={"insurance_valid_until": "2026-12-06", "pilot_rpc_valid_until": "2030-01-01"}, today=ref)
    assert r_soon["status"] == CHECK_FIRST
    assert any(x["code"] == "insurance_expiring" for x in r_soon["reasons"])

    # Expired third-party insurance -> DO_NOT_FLY (Rule 44)
    r_exp = assess("D1", ok_settings, ok_reg, None,
                   compliance={"insurance_valid_until": "2026-11-26"}, today=ref)
    assert r_exp["status"] == DO_NOT_FLY
    assert any(x["code"] == "insurance_expired" for x in r_exp["reasons"])

    # Missing insurance expiry when compliance record exists -> CHECK_FIRST (M4)
    r_miss = assess("D1", ok_settings, ok_reg, None, compliance={"pilot_name": "P1"}, today=ref)
    assert r_miss["status"] == CHECK_FIRST
    assert any(x["code"] == "no_insurance" for x in r_miss["reasons"])

    # Expired pilot RPC -> DO_NOT_FLY (Rule 31)
    r_rpc = assess("D1", ok_settings, ok_reg, None,
                   compliance={"insurance_valid_until": "2027-06-01", "pilot_rpc_valid_until": "2026-10-01"}, today=ref)
    assert r_rpc["status"] == DO_NOT_FLY
    assert any(x["code"] == "rpc_expired" for x in r_rpc["reasons"])


def test_rule30_accident_dossier_48h_deadline_and_html_escaping():
    now = datetime(2026, 11, 27, 15, 0, tzinfo=timezone.utc)
    review = {
        "id": 42, "verdict": "DEVIATED", "log_name": "<script>bad</script>.bin", "plan_name": "spray.waypoints",
        "uploaded_at": "2026-11-27T05:00:00",
        "report": {
            "flight_s": 240.0,
            "max_height_m": {"flown": 4.2},
            "vibration": {"flown_at": "2026-11-27T05:00:00+00:00"},
            "replay": {"track": [[0.0, 18.5201, 73.8501, 0.2], [240.0, 18.5210, 73.8515, 3.8]]},
            "evidence_timeline": [{"t_s": 120.0, "level": "warning", "kind": "motor", "text": "Motor 1 saturated"}],
            "settings_changed_in_flight": {"changes": []},
            "input_files": {"log": {"sha256": "a" * 64}},
        },
    }
    dossier = build_accident_dossier(
        fleet="pune-agri", drone_id="AGRI-05",
        registration={"uin": "UA00DEMO05", "status": "VERIFIED", "verified_by": "op"},
        compliance={"insurance_policy": "POL-1", "insurance_insurer": "NIA", "insurance_valid_until": "2027-05-01",
                    "type_certificate_no": "DAN-1", "pilot_name": "Test Pilot", "pilot_rpc_no": "RPC-1"},
        review=review,
        maintenance_entries=[{"done_at": "2026-11-27T06:00:00", "action": "Incident / crash reported (grounded for inspection)", "note": "Motor loss", "done_by": "op"}],
        grounded={"done_at": "2026-11-27T06:00:00", "action": "Incident / crash reported (grounded for inspection)", "note": "Motor loss"},
        ledger_entry={"seq": 99, "created_at": "2026-11-27T05:01:00", "payload_sha256": "b" * 64, "entry_hash": "c" * 64},
        matches_record=True,
        now_utc=now,
    )
    # Grounded at 06:00 UTC -> Rule 30 deadline is +48h (39.0 h left) and 2025 AAIB notice is +24h (15.0 h left)
    assert dossier["deadline"]["status"] == "WITHIN_48H"
    assert dossier["deadline"]["hours_remaining"] == 39.0
    assert dossier["deadline"]["aaib_2025_hours_remaining"] == 15.0
    assert dossier["flight"]["takeoff"]["lat"] == 18.5201
    html = accident_dossier_html(dossier)
    assert "Rule 30" in html and "2025 Accident Investigation Rules" in html and "UA00DEMO05" in html and "VERIFIED" in html
    assert "State-approved UAS" in html
    assert "SIMULATED DEMO FLEET" in html
    assert "<script>bad</script>" not in html
    assert "&lt;script&gt;bad&lt;/script&gt;" in html

    # Without Type Certificate / State approval, 24 h AAIB banner must state "may not apply" (Rule 2(1)(a)(ii) Explanation (2))
    no_tc = build_accident_dossier(
        fleet="demo", drone_id="PX4-01",
        registration={"uin": "UA001", "status": "VERIFIED"},
        compliance={"insurance_policy": "POL-1"},
        review=review, maintenance_entries=[], grounded=None, ledger_entry=None, matches_record=None, now_utc=now,
    )
    assert "may not apply" in accident_dossier_html(no_tc)


def test_stale_flight_two_tier_note_15_to_90d_and_check_first_over_90d():
    ref = date(2026, 11, 28)
    ok_settings = {"verdict": "OK", "critical": [], "limits": [], "failsafes_off": []}
    ok_reg = {"uin": "UA001", "status": "VERIFIED"}
    fresh = {"review_id": 1, "flown_at": "2026-11-26T06:00:00+00:00", "warnings": [], "critical_in_flight": 0, "deviated": False}
    seasonal = {"review_id": 2, "flown_at": "2026-10-01T06:00:00+00:00", "warnings": [], "critical_in_flight": 0, "deviated": False}
    ancient = {"review_id": 3, "flown_at": "2026-07-01T06:00:00+00:00", "warnings": [], "critical_in_flight": 0, "deviated": False}
    r_fresh = assess("D1", ok_settings, ok_reg, fresh, today=ref, max_stale_days=14, stale_check_days=90)
    assert r_fresh["status"] == READY and r_fresh["stale_note"] is None
    r_seasonal = assess("D1", ok_settings, ok_reg, seasonal, today=ref, max_stale_days=14, stale_check_days=90)
    assert r_seasonal["status"] == READY and r_seasonal["stale_note"] is not None and r_seasonal["stale_note"]["days"] == 58
    r_ancient = assess("D1", ok_settings, ok_reg, ancient, today=ref, max_stale_days=14, stale_check_days=90)
    assert r_ancient["status"] == CHECK_FIRST and r_ancient["stale_note"] is None
    assert any(r["code"] == "stale_flight" for r in r_ancient["reasons"])


def test_signed_operator_approval_clears_deliberate_failsafe_off():
    from aerofleet.assurance.readiness import failsafes_off, setting_notes

    params = {"COM_LOW_BAT_ACT": 0, "NAV_RCL_ACT": 2}
    assert [f["name"] for f in failsafes_off(params)] == ["COM_LOW_BAT_ACT"]
    approved = {"COM_LOW_BAT_ACT": {"value": 0, "by": "chief-op", "note": "Tethered power rig"}}
    assert failsafes_off(params, approved=approved) == []
    notes = setting_notes(params, approved=approved)
    assert any("COM_LOW_BAT_ACT" in n and "chief-op" in n for n in notes)


def test_m3_smoothed_airborne_speed_rejects_parked_gps_jitter():
    from aerofleet.assurance.evidence import _airborne_spans

    # Parked drone at 0.2 m altitude with 5 Hz +-0.6 m GPS jitter (raw point-to-point speed = 6 m/s!)
    jitter_track = []
    for k in range(50):
        t = k * 0.2
        dlat = (0.000005 if k % 2 == 0 else -0.000005)
        jitter_track.append((t, 18.5200 + dlat, 73.8500, 0.2))
    assert _airborne_spans(jitter_track, 0.0) == []

    # Steady 3 m/s agricultural spraying pass at 1.2 m altitude over 10 s -> cleanly airborne
    spray_track = [(k * 0.5, 18.5200 + (k * 1.5) / 111_320.0, 73.8500, 1.2) for k in range(20)]
    spans = _airborne_spans(spray_track, 0.0)
    assert spans and sum(hi - lo for lo, hi in spans) >= 7.0


def test_fleet_trends_service_interval_since_maintenance():
    reviews = [
        {"drone_id": "D1", "created_at": "2026-11-01T10:00:00", "report": {"flight_s": 1800}},
        {"drone_id": "D1", "created_at": "2026-11-10T10:00:00", "report": {"flight_s": 3600}},
        {"drone_id": "D1", "created_at": "2026-11-15T10:00:00", "report": {"flight_s": 1800}},
    ]
    maint = {"D1": [{"done_at": "2026-11-05T09:00:00", "action": "Propellers replaced"}]}
    out = fleet_trends(reviews, maintenance=maint)
    row = out["drones"][0]
    assert row["flights"] == 3
    assert row["since_maintenance_flights"] == 2
    assert row["since_maintenance_hours"] == 1.5
    assert row["last_maintenance_action"] == "Propellers replaced"
