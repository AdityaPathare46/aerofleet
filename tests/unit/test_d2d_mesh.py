"""Unit tests for aerofleet/safety/d2d_mesh.py — link-state transitions,
peer TTL eviction, trajectory-point projection, and the core claim this
whole design rests on: a local, D2D-derived CBF verdict is IDENTICAL to
the centralized verdict for the same conflict geometry, because both go
through the exact same, unmodified ControlBarrierFunctionGate.
"""
import time

import pytest

from aerofleet.safety.cbf_gate import ControlBarrierFunctionGate
from aerofleet.safety.d2d_mesh import (
    D2DBasicSafetyMessage,
    D2DLinkState,
    D2DLinkStateMachine,
    D2DTransceiver,
    DEGRADED_MISSED_HEARTBEATS,
    STORE_FORWARD_MISSED_HEARTBEATS,
    haversine_m,
)

pytestmark = pytest.mark.unit


def _msg(drone_id: str, lat: float, lon: float, **overrides) -> D2DBasicSafetyMessage:
    defaults = dict(
        drone_id=drone_id, timestamp_utc=time.time(), lat=lat, lon=lon, alt_m=60.0,
        velocity_mps=10.0, heading_deg=0.0, battery_soc=0.9, link_state="NOMINAL",
    )
    defaults.update(overrides)
    return D2DBasicSafetyMessage(**defaults)


class TestHaversine:
    def test_zero_distance(self):
        assert haversine_m(18.53, 73.86, 18.53, 73.86) == pytest.approx(0.0, abs=1e-6)

    def test_one_degree_latitude_is_about_111km(self):
        d = haversine_m(0.0, 0.0, 1.0, 0.0)
        assert d == pytest.approx(111_195, rel=0.01)

    def test_known_close_pair_pune_scale(self):
        # ~0.001 deg lat difference at Pune's latitude is roughly 111m.
        d = haversine_m(18.5300, 73.8600, 18.5310, 73.8600)
        assert 90 < d < 130


class TestD2DLinkStateMachine:
    def test_starts_nominal(self):
        assert D2DLinkStateMachine().state == D2DLinkState.NOMINAL

    def test_stays_nominal_below_degraded_threshold(self):
        sm = D2DLinkStateMachine()
        for _ in range(DEGRADED_MISSED_HEARTBEATS - 1):
            sm.record_missed_heartbeat()
        assert sm.state == D2DLinkState.NOMINAL

    def test_transitions_to_degraded_at_threshold(self):
        sm = D2DLinkStateMachine()
        for _ in range(DEGRADED_MISSED_HEARTBEATS):
            sm.record_missed_heartbeat()
        assert sm.state == D2DLinkState.DEGRADED

    def test_transitions_to_isolated_with_no_peer_contact(self):
        sm = D2DLinkStateMachine()
        for _ in range(STORE_FORWARD_MISSED_HEARTBEATS):
            sm.record_missed_heartbeat()
        assert sm.state == D2DLinkState.ISOLATED

    def test_transitions_to_store_forward_with_recent_peer_contact(self):
        sm = D2DLinkStateMachine()
        sm.record_peer_contact()
        for _ in range(STORE_FORWARD_MISSED_HEARTBEATS):
            sm.record_missed_heartbeat()
        assert sm.state == D2DLinkState.STORE_FORWARD

    def test_heartbeat_recovers_to_nominal(self):
        sm = D2DLinkStateMachine()
        for _ in range(STORE_FORWARD_MISSED_HEARTBEATS):
            sm.record_missed_heartbeat()
        sm.record_heartbeat()
        assert sm.state == D2DLinkState.NOMINAL


class TestD2DTransceiver:
    def test_ignores_own_broadcasts(self):
        tx = D2DTransceiver("DRONE-A")
        tx.receive(_msg("DRONE-A", 18.53, 73.86))
        assert tx.known_peers() == []

    def test_stores_a_peer_broadcast(self):
        tx = D2DTransceiver("DRONE-A")
        tx.receive(_msg("DRONE-B", 18.53, 73.86))
        peers = tx.known_peers()
        assert len(peers) == 1
        assert peers[0].drone_id == "DRONE-B"

    def test_receiving_a_peer_advances_link_state_toward_store_forward(self):
        tx = D2DTransceiver("DRONE-A")
        tx.receive(_msg("DRONE-B", 18.53, 73.86))
        for _ in range(STORE_FORWARD_MISSED_HEARTBEATS):
            tx.link_state.record_missed_heartbeat()
        assert tx.link_state.state == D2DLinkState.STORE_FORWARD

    def test_stale_peer_is_evicted(self):
        tx = D2DTransceiver("DRONE-A")
        tx.receive(_msg("DRONE-B", 18.53, 73.86))
        assert len(tx.known_peers()) == 1
        time.sleep(0.05)
        assert tx.evict_stale(ttl_s=0.01) == ["DRONE-B"]
        assert tx.known_peers() == []

    def test_fresh_peer_survives_eviction_pass(self):
        tx = D2DTransceiver("DRONE-A")
        tx.receive(_msg("DRONE-B", 18.53, 73.86))
        assert tx.evict_stale(ttl_s=10.0) == []
        assert len(tx.known_peers()) == 1


class TestToTrajectoryPoints:
    def test_no_peers_returns_own_state_only(self):
        tx = D2DTransceiver("DRONE-A")
        own_state = {"lat": 18.53, "lon": 73.86, "battery_margin_wh": 100.0}
        points = tx.to_trajectory_points(own_state)
        assert points == [own_state]

    def test_one_point_per_known_peer(self):
        tx = D2DTransceiver("DRONE-A")
        tx.receive(_msg("DRONE-B", 18.5310, 73.8600))
        tx.receive(_msg("DRONE-C", 18.5320, 73.8600))
        points = tx.to_trajectory_points({"lat": 18.5300, "lon": 73.8600})
        assert len(points) == 2

    def test_separation_m_matches_haversine(self):
        tx = D2DTransceiver("DRONE-A")
        tx.receive(_msg("DRONE-B", 18.5310, 73.8600))
        own_state = {"lat": 18.5300, "lon": 73.8600}
        points = tx.to_trajectory_points(own_state)
        expected = haversine_m(18.5300, 73.8600, 18.5310, 73.8600)
        assert points[0]["separation_m"] == pytest.approx(expected)

    def test_own_state_fields_are_preserved_alongside_separation(self):
        tx = D2DTransceiver("DRONE-A")
        tx.receive(_msg("DRONE-B", 18.5310, 73.8600))
        own_state = {"lat": 18.5300, "lon": 73.8600, "battery_margin_wh": 55.0, "altitude_m": 70.0}
        points = tx.to_trajectory_points(own_state)
        assert points[0]["battery_margin_wh"] == 55.0
        assert points[0]["altitude_m"] == 70.0


class TestVerdictParity:
    """The actual novel claim: a CBF verdict computed from D2D peer
    broadcasts must be identical to one computed centrally for the same
    geometry — same gate, same constraints, only the data source differs."""

    GATE_CONFIG = {"min_separation_m": 15.0, "max_altitude_m": 100.0}

    def test_violating_separation_produces_identical_verdicts(self):
        # Two drones 5m apart — well inside the 15m minimum separation.
        tx = D2DTransceiver("DRONE-A")
        tx.receive(_msg("DRONE-B", 18.530045, 73.860000))  # ~5m north of DRONE-A
        own_state = {"lat": 18.530000, "lon": 73.860000, "altitude_m": 50.0}

        d2d_points = tx.to_trajectory_points(own_state)
        centralized_points = [{"separation_m": d2d_points[0]["separation_m"], "altitude_m": 50.0}]

        d2d_gate = ControlBarrierFunctionGate(dict(self.GATE_CONFIG))
        centralized_gate = ControlBarrierFunctionGate(dict(self.GATE_CONFIG))

        d2d_result = d2d_gate.evaluate_trajectory(d2d_points)
        centralized_result = centralized_gate.evaluate_trajectory(centralized_points)

        assert d2d_result.passed is False
        assert d2d_result.passed == centralized_result.passed
        assert len(d2d_result.violations) == len(centralized_result.violations) == 1
        assert d2d_result.violations[0].constraint_name == "min_separation"
        assert d2d_result.violations[0].constraint_name == centralized_result.violations[0].constraint_name

    def test_safe_separation_produces_identical_verdicts(self):
        # Two drones ~200m apart — safely outside the 15m minimum.
        tx = D2DTransceiver("DRONE-A")
        tx.receive(_msg("DRONE-B", 18.5318, 73.8600))
        own_state = {"lat": 18.5300, "lon": 73.8600, "altitude_m": 50.0}

        d2d_points = tx.to_trajectory_points(own_state)
        centralized_points = [{"separation_m": d2d_points[0]["separation_m"], "altitude_m": 50.0}]

        d2d_result = ControlBarrierFunctionGate(dict(self.GATE_CONFIG)).evaluate_trajectory(d2d_points)
        centralized_result = ControlBarrierFunctionGate(dict(self.GATE_CONFIG)).evaluate_trajectory(centralized_points)

        assert d2d_result.passed is True
        assert d2d_result.passed == centralized_result.passed

    def test_no_peers_still_evaluates_own_state_constraints(self):
        # Zero D2D traffic shouldn't silently skip altitude/other own-state
        # constraints — this is the fallback path in to_trajectory_points().
        tx = D2DTransceiver("DRONE-A")
        own_state = {"lat": 18.53, "lon": 73.86, "altitude_m": 150.0}  # exceeds max_altitude_m=100
        points = tx.to_trajectory_points(own_state)
        result = ControlBarrierFunctionGate(dict(self.GATE_CONFIG)).evaluate_trajectory(points)
        assert result.passed is False
        assert any(v.constraint_name == "altitude_ceiling" for v in result.violations)
