"""Unit tests for the deterministic council-claims-vs-geometry check that
the VR Incident Replay surfaces."""
from aerofleet.agents.incident_taxonomy import check_claims_against_geometry


def _status(result, factor):
    return next(r["status"] for r in result["rows"] if r["factor"] == factor)


def test_confirmed_when_council_names_the_violated_factor():
    r = check_claims_against_geometry(
        ["battery_reserve_margin"], [{"factor": "battery_energy", "contributed": "CONTRIBUTED", "confidence": 0.9}],
    )
    assert _status(r, "battery_energy") == "CONFIRMED"
    assert r["agrees_with_geometry"] is True


def test_missed_when_geometry_shows_a_factor_the_council_denied():
    r = check_claims_against_geometry(
        ["min_separation"], [{"factor": "airspace_conflict", "contributed": "NOT_CONTRIBUTED"}],
    )
    assert _status(r, "airspace_conflict") == "MISSED"
    assert r["agrees_with_geometry"] is False


def test_no_geometric_evidence_for_an_unbacked_claim():
    r = check_claims_against_geometry(
        ["battery_reserve_margin"],
        [{"factor": "battery_energy", "contributed": "CONTRIBUTED"},
         {"factor": "weather_environmental", "contributed": "CONTRIBUTED"}],
    )
    assert _status(r, "weather_environmental") == "NO_GEOMETRIC_EVIDENCE"
    assert r["counts"]["NO_GEOMETRIC_EVIDENCE"] == 1


def test_factors_without_a_cbf_margin_are_not_checkable():
    r = check_claims_against_geometry([], [{"factor": "routing_navigation", "contributed": "CONTRIBUTED"}])
    assert _status(r, "routing_navigation") == "NOT_CHECKABLE"
    assert _status(r, "cross_check_anomaly") == "NOT_CHECKABLE"


def test_altitude_and_geofence_both_implicate_airspace():
    r = check_claims_against_geometry(["altitude_ceiling", "geofence_exclusion"], [])
    row = next(x for x in r["rows"] if x["factor"] == "airspace_conflict")
    assert row["implicated_by_geometry"] is True
    assert row["evidence_constraints"] == ["altitude_ceiling", "geofence_exclusion"]
    assert row["status"] == "MISSED"
    assert r["has_council_claims"] is False


def test_uncertain_and_agreed_negatives():
    r = check_claims_against_geometry(
        ["battery_reserve_margin"],
        [{"factor": "battery_energy", "contributed": "CONTRIBUTED"},
         {"factor": "communications_link", "contributed": "UNCERTAIN"},
         {"factor": "ops_scheduling_capacity", "contributed": "NOT_CONTRIBUTED"}],
    )
    assert _status(r, "communications_link") == "UNCERTAIN"
    assert _status(r, "ops_scheduling_capacity") == "AGREES_NOT_INVOLVED"


def test_tolerates_missing_or_malformed_factors():
    r = check_claims_against_geometry(["wind_limit"], None)
    assert _status(r, "weather_environmental") == "MISSED"
    r = check_claims_against_geometry(["wind_limit"], ["garbage", {"no_factor": 1}])
    assert r["has_council_claims"] is False


def test_a_constraint_violated_at_many_waypoints_is_one_piece_of_evidence():
    out = check_claims_against_geometry(["geofence_exclusion"] * 9 + ["min_separation"], None)
    row = next(r for r in out["rows"] if r["factor"] == "airspace_conflict")
    assert row["evidence_constraints"] == ["geofence_exclusion", "min_separation"]
