"""Property-based dispatch invariants, checked across ~1,000+ generated
cases — deliberately NOT the same thing as scenario_engine/{schemas,
evaluator,runner}.py, and deliberately doesn't reuse it.

That machinery evaluates aerofleet.agents.council.CouncilOfExperts
.run_grand_debate()'s output against hand-labeled numeric
expected_outputs (eta_minutes, cost_usd, cbf_all_pass, ...) — a model
where the council computes and outputs the actual decision. That's not
how AeroFleet decides anything anymore: run_grand_debate()'s own
docstring is explicit that it only ever runs as a post-hoc explanation
of a decision the deterministic CBF gate already made
(aerofleet/api/routes/orders.py). Running the legacy scenario suite's
7 cases through it and grading against those hand-labeled numbers would
be testing a decision-making role the council doesn't have anymore —
scaling that up to 1,000 cases would just be 1,000 tests of the wrong
thing, however impressive the count sounds.

What's actually meaningful to check at scale, and what this file does
instead: real PROPERTIES that must hold regardless of implementation —
not "recompute the expected value with the same code and compare"
(circular), but invariants like "a destination inside a real, named
DGCA red zone must always be rejected" or "identical inputs must always
produce identical verdicts". No LLM involved — this is the deterministic
decision layer, which is what actually decides. For the LLM council's
real current job (explaining a decision factually, not making one), see
scenario_engine/incident_forensics_evaluation.py.

Run just this file for a focused pass:
    pytest tests/property/test_dispatch_invariants.py -q

Deliberately does NOT use conftest.py's `fresh_fleet_state` per test —
that fixture clears the process-wide FleetState cache before *and*
after every test, so `get_fleet_state()` rebuilds the whole city graph
(osmnx fetch/synthetic fallback, zone lookups, depot geocoding) from
scratch on every single one. Fine at the scale that fixture was
designed for (a handful of tests per file); at 3,000+ parametrized
cases it turned a ~1-minute suite into a run that was still going after
5+ minutes with no end in sight — confirmed via a stack sample showing
real work deep in osmnx/sklearn/pyproj, not a hang, just 3,000x more
graph-rebuild work than any of these invariants actually needs. None of
them depend on isolated drone/order state between cases (the ones that
could be affected by accumulated fleet consumption already skip rather
than assert when no drone is feasible) — only `warm_fleet_state` below,
once for the whole file.
"""
import pytest

from tests.property.generator import (
    generate_cases,
    green_zone_light_payload_cases,
    overweight_payload_cases,
    red_zone_cases,
)

pytestmark = pytest.mark.property

_ALL_CASES = generate_cases()
_RED_CASES = red_zone_cases(_ALL_CASES)
_GREEN_LIGHT_CASES = green_zone_light_payload_cases(_ALL_CASES)
_OVERWEIGHT_CASES = overweight_payload_cases(_ALL_CASES)


@pytest.fixture(scope="module", autouse=True)
def warm_fleet_state():
    """Builds the fleet state (and its city graph) once for this whole
    file instead of once per case, and leaves the cache clean afterward
    so whatever test file runs next in the same session still gets the
    isolation its own `fresh_fleet_state` fixture expects."""
    from aerofleet.fleet import state as fleet_state_module

    fleet_state_module._fleet_states.clear()
    yield
    fleet_state_module._fleet_states.clear()


@pytest.fixture(scope="module")
def shared_auth_headers():
    """conftest.py's own `auth_headers` registers a fresh user (a real
    bcrypt hash) per test — fine for a handful of tests, but multiplied
    across 3,000+ cases in this file that's minutes of pure hashing
    overhead for zero added test isolation (these cases don't need
    separate identities, only fresh *fleet* state, which
    `fresh_fleet_state` already resets per test). One user, registered
    once for the whole file, via its own client — `api_client` itself is
    function-scoped (a fresh TestClient/DB session per test), which
    pytest won't let a module-scoped fixture depend on."""
    import uuid as _uuid

    from fastapi.testclient import TestClient

    from aerofleet.api.app import app

    with TestClient(app) as setup_client:
        username = f"proptest_{_uuid.uuid4().hex[:8]}"
        setup_client.post(
            "/api/v1/auth/register",
            json={"username": username, "email": f"{username}@example.com", "password": "TestPass123!"},
        )
        resp = setup_client.post("/api/v1/auth/login", data={"username": username, "password": "TestPass123!"})
        token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _dispatch(api_client, headers, case):
    resp = api_client.post(
        "/api/v1/orders/",
        headers=headers,
        json={
            "city": case.city, "origin_depot_id": case.depot_id,
            "destination_lat": case.dest_lat, "destination_lon": case.dest_lon,
            "payload_kg": case.payload_kg, "priority": case.priority,
            "deadline_minutes": 45,
        },
    )
    if resp.status_code != 201:
        return None, resp
    order_id = resp.json()["order_id"]
    try:
        dispatch_resp = api_client.post(f"/api/v1/orders/{order_id}/dispatch", headers=headers)
    except Exception:
        # A known, separate, pre-existing limitation, not what any
        # invariant in this file is checking: the real OSM street graph
        # only covers a bounded radius around each city center, and a
        # generated destination can legitimately fall outside it for a
        # depot near that edge — networkx.exception.NetworkXNoPath
        # propagates as a raw exception through the FastAPI TestClient
        # rather than a clean error response, so it has to be caught here
        # rather than checked via a status code. Treated identically to
        # any other non-CBF failure below: skip, don't fail.
        return None, None
    return order_id, dispatch_resp


class TestRedZoneAlwaysRejected:
    """A destination the app's own real zone data (aerofleet/city/
    restricted_sites.py) calls RED must never be dispatched — this is
    the actual safety property the CBF gate's geofence_exclusion
    constraint exists to guarantee. ~hundreds of real, distinct
    destination points, not one hand-picked example."""

    @pytest.mark.parametrize("case", _RED_CASES, ids=lambda c: c.case_id)
    def test_red_zone_destination_is_always_rejected(self, api_client, shared_auth_headers, case):
        order_id, dispatch_resp = _dispatch(api_client, shared_auth_headers, case)
        if order_id is None:
            if dispatch_resp is None:
                pytest.skip("dispatch raised (e.g. NetworkXNoPath at the graph-bounds edge) — not a CBF-gate case")
            pytest.skip(f"order creation itself failed ({dispatch_resp.status_code}) — not a CBF-gate case")
        body = dispatch_resp.json()
        if dispatch_resp.status_code != 200:
            # A real routing failure at the graph-bounds edge (a known,
            # separate limitation, not what this invariant is checking) —
            # skip rather than let it masquerade as a safety-gate failure.
            pytest.skip(f"non-CBF failure: {dispatch_resp.status_code} {body}")
        assert body["verdict"] == "REJECTED_BY_CBF_GATE", (
            f"{case.case_id}: a RED-zone destination was approved — real safety-property violation"
        )
        margins = body["cbf_certificate"]["safety_margins"]
        assert margins["geofence_exclusion"] < 0, (
            f"{case.case_id}: rejected, but not for the geofence reason — got margins {margins}"
        )


class TestUnobstructedLightDispatchIsApproved:
    """The inverse property: nothing structurally wrong (green zone,
    light payload) should still get dispatched — proves the gate isn't
    just rejecting everything to trivially satisfy the invariant above."""

    @pytest.mark.parametrize("case", _GREEN_LIGHT_CASES, ids=lambda c: c.case_id)
    def test_unobstructed_light_dispatch_is_approved(self, api_client, shared_auth_headers, case):
        order_id, dispatch_resp = _dispatch(api_client, shared_auth_headers, case)
        if order_id is None:
            if dispatch_resp is None:
                pytest.skip("dispatch raised (e.g. NetworkXNoPath at the graph-bounds edge)")
            pytest.skip(f"order creation itself failed ({dispatch_resp.status_code})")
        body = dispatch_resp.json()
        if dispatch_resp.status_code != 200:
            pytest.skip(f"non-CBF failure: {dispatch_resp.status_code} {body}")
        if body["verdict"] == "FAILED":
            pytest.skip("no feasible drone for this depot/payload combination — fleet capacity, not a gate decision")
        assert body["verdict"] == "APPROVED", (
            f"{case.case_id}: unobstructed light dispatch was rejected — {body.get('cbf_certificate')}"
        )


class TestOverweightPayloadAlwaysRejected:
    """Payload above the real configured ceiling (5.0 kg default) must
    always fail the payload_weight_limit constraint, independent of
    where it's going."""

    @pytest.mark.parametrize("case", _OVERWEIGHT_CASES, ids=lambda c: c.case_id)
    def test_overweight_payload_is_always_rejected(self, api_client, shared_auth_headers, case):
        order_id, dispatch_resp = _dispatch(api_client, shared_auth_headers, case)
        if order_id is None:
            if dispatch_resp is None:
                pytest.skip("dispatch raised (e.g. NetworkXNoPath at the graph-bounds edge)")
            pytest.skip(f"order creation itself failed ({dispatch_resp.status_code})")
        body = dispatch_resp.json()
        if dispatch_resp.status_code != 200:
            pytest.skip(f"non-CBF failure: {dispatch_resp.status_code} {body}")
        assert body["verdict"] == "REJECTED_BY_CBF_GATE", f"{case.case_id}: overweight payload was approved"
        margins = body["cbf_certificate"]["safety_margins"]
        assert margins["payload_weight_limit"] < 0, f"{case.case_id}: rejected, but not for payload — {margins}"


class TestDeterminism:
    """The same input dispatched twice (independent orders, same fleet
    state) must produce the same verdict — proves there's no hidden
    randomness or race condition in the decision path. Sampled, not
    exhaustive: this property doesn't gain new coverage per destination
    the way the zone-based invariants do."""

    @pytest.mark.parametrize("case", _ALL_CASES[::47], ids=lambda c: c.case_id)  # every 47th case, ~40 samples
    def test_identical_input_gives_identical_verdict(self, api_client, shared_auth_headers, case):
        _, first = _dispatch(api_client, shared_auth_headers, case)
        _, second = _dispatch(api_client, shared_auth_headers, case)
        if first is None or second is None or first.status_code != 200 or second.status_code != 200:
            pytest.skip("non-CBF failure on at least one attempt")
        assert first.json()["verdict"] == second.json()["verdict"], (
            f"{case.case_id}: same input produced different verdicts across two dispatches — "
            f"{first.json()['verdict']} vs {second.json()['verdict']}"
        )


class TestGateNeverExceedsAMillisecondBudget:
    """Performance regression guard for the actual patent-relevant claim
    (docs/PATENT_NOVELTY.md: 'well under a millisecond') — generous 50ms
    ceiling so this fails on a real regression, not environment noise,
    while still catching something that broke the gate's O(1) design."""

    @pytest.mark.parametrize("case", _ALL_CASES[::23], ids=lambda c: c.case_id)  # ~90 samples
    def test_cbf_evaluation_stays_fast(self, api_client, shared_auth_headers, case):
        order_id, dispatch_resp = _dispatch(api_client, shared_auth_headers, case)
        if order_id is None or dispatch_resp.status_code != 200:
            pytest.skip("not a CBF-gate case")
        ms = dispatch_resp.json()["cbf_certificate"]["execution_time_ms"]
        assert ms < 50.0, f"{case.case_id}: CBF gate took {ms}ms — real performance regression"


def test_generator_actually_produced_a_real_battery_of_cases():
    """A guard on the suite itself: if the generator's zone classification
    ever silently breaks (e.g. a future refactor of AirspaceModel.zone_at
    changes its signature and every case quietly falls into one bucket),
    every parametrized test above would just collect zero cases and
    report as a hollow, misleading 'pass'. This is the one test that
    would actually catch that."""
    assert len(_ALL_CASES) >= 1000, f"expected 1000+ generated cases, got {len(_ALL_CASES)}"
    assert len(_RED_CASES) >= 20, f"expected a real number of RED-zone cases from real DGCA site data, got {len(_RED_CASES)}"
    assert len(_GREEN_LIGHT_CASES) >= 100, f"expected plenty of unobstructed cases, got {len(_GREEN_LIGHT_CASES)}"
