"""End-to-end tests for /api/v1/hardware/fc — the real MAVLink path.

Each test starts tools/mock_mavlink_vehicle.py on a free UDP port (it sends
there the way Mission Planner's MAVLink mirror does), points AeroFleet's
discovery at that port via AEROFLEET_FC_UDP_PORTS, and drives the real
FastAPI app: discovery -> background inspection (params, AUTOPILOT_VERSION,
telemetry, PreArm) -> report -> checklist -> motor test. pymavlink is not
mocked anywhere; every byte goes over a real socket.
"""
import time

import pytest

from aerofleet.hardware.fc_discovery import SOURCE_MP_FORWARD, discover
from aerofleet.hardware.fc_inspector import FCInspector
from tests.fc_mock import running_mock

pytestmark = pytest.mark.integration

BASE = "/api/v1/hardware/fc"

# What the faulty profile must be failed for (see the mock's docstring).
FAULTY_EXPECTED_FAILS = {
    "batt.fs_low_action",     # BATT_FS_LOW_ACT = 0, the real ArduCopter default
    "batt.fs_critical_action",
    "batt.fs_thresholds",
    "batt.cell_balance",      # one cell 0.25 V low
    "fs.fence_altitude",      # FENCE_ALT_MAX 150 m > 120 m
    "fc.vibration",           # clipping growing
    "fc.sensor_mag",          # no compass
    "fc.prearm",              # "PreArm: Compass not healthy"
    "mot.output_mapping",     # SERVO3 duplicates Motor1, Motor3 unmapped
}


def _start(client, headers, **body):
    payload = {"auto": True, "uin": "UA-TEST-0001", "weight_kg": 12.5, "sample_seconds": 2.0}
    payload.update(body)
    resp = client.post(f"{BASE}/inspections", headers=headers, json=payload)
    assert resp.status_code == 202, resp.text
    return resp.json()["inspection_id"]


def _wait(client, headers, inspection_id, timeout_s=25.0):
    deadline = time.monotonic() + timeout_s
    seen_progress = set()
    while time.monotonic() < deadline:
        body = client.get(f"{BASE}/inspections/{inspection_id}", headers=headers).json()
        seen_progress.add(body["progress"])
        if body["status"] in ("READY", "FAILED"):
            body["_seen_progress"] = seen_progress
            return body
        time.sleep(0.2)
    raise TimeoutError(f"{inspection_id} still {body['status']} at {body['progress']}% ({body['stage']})")


def _fail_ids(detail):
    return {c["id"] for c in detail["report"]["checks"] if c["status"] == "FAIL"}


@pytest.fixture
def udp_port_env(monkeypatch):
    def _set(port):
        monkeypatch.setenv("AEROFLEET_FC_UDP_PORTS", str(port))
    return _set


class TestDiscoveryOverUdp:
    def test_detects_forwarded_heartbeat_from_the_mock(self):
        with running_mock("healthy") as port:
            result = discover(udp_ports=[port], listen_s=1.5, scan_usb=False)
        rec = result.recommended
        assert rec is not None
        assert rec.source == SOURCE_MP_FORWARD
        assert rec.connection == f"udpin:127.0.0.1:{port}"
        assert rec.autopilot == 3 and rec.vehicle_type == 2 and rec.system_id == 1

    def test_discover_endpoint(self, api_client, auth_headers, udp_port_env):
        with running_mock("healthy") as port:
            udp_port_env(port)
            resp = api_client.get(f"{BASE}/discover?listen_s=1.5", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["recommended"]["source"] == SOURCE_MP_FORWARD
        assert body["recommended"]["udp_port"] == port
        assert body["mission_planner_help"] is None

    def test_discover_endpoint_requires_auth(self, api_client):
        assert api_client.get(f"{BASE}/discover").status_code == 401


class TestInspectorAgainstMock:
    def test_lossy_parameter_download_is_completed_by_retries(self):
        with running_mock("healthy", "--lossy-params") as port:
            snap = FCInspector(f"udpin:127.0.0.1:{port}", sample_seconds=1.5).run()
        assert snap.param_count_expected and len(snap.params) == snap.param_count_expected
        assert snap.params_missing_count == 0
        assert snap.autopilot_version["firmware"]["version"] == "4.5.7"
        assert snap.prearm_command_result == "ACCEPTED"
        assert {"SYS_STATUS", "BATTERY_STATUS", "GPS_RAW_INT", "EKF_STATUS_REPORT", "RC_CHANNELS",
                "SERVO_OUTPUT_RAW", "ESC_TELEMETRY_1_TO_4", "POWER_STATUS"} <= set(snap.telemetry)
        assert len(snap.vibration_samples) >= 2


class TestEndToEndInspection:
    def test_faulty_profile_yields_the_expected_fails(self, api_client, operator_headers, udp_port_env):
        auth_headers = operator_headers
        with running_mock("faulty") as port:
            udp_port_env(port)
            iid = _start(api_client, auth_headers)
            detail = _wait(api_client, auth_headers, iid)
            # The duplicated output mapping shows up in a real motor test too:
            # Motor1 is on outputs 1 AND 3, so spinning A turns both ESCs.
            spin = api_client.post(f"{BASE}/inspections/{iid}/motor-test", headers=auth_headers,
                                   json={"motor": "A", "throttle_pct": 10, "duration_s": 0.5,
                                         "props_removed_confirmed": True})
            assert spin.status_code == 200, spin.text
            corro = spin.json()["result"]["esc_corroboration"]
            assert corro["spun_esc"] == [1, 3] and corro["expected_esc"] == [1, 3]

        assert detail["status"] == "READY", detail.get("error")
        assert detail["source"] == SOURCE_MP_FORWARD
        assert detail["connection"] == f"udpin:127.0.0.1:{port}"
        assert len(detail["_seen_progress"]) >= 2  # progress was reported, not just 0 -> 100
        rep = detail["report"]
        assert rep["verdict"] == "FAIL"
        assert FAULTY_EXPECTED_FAILS <= _fail_ids(detail), sorted(_fail_ids(detail))
        fence = next(c for c in rep["checks"] if c["id"] == "fs.fence_altitude")
        assert fence["evidence"]["FENCE_ALT_MAX"] == 150
        assert fence["source"].startswith("https://")
        assert rep["firmware"] == "4.5.7"

        history = api_client.get(f"{BASE}/inspections", headers=auth_headers).json()
        assert history[0]["inspection_id"] == iid and history[0]["verdict"] == "FAIL"

        export = api_client.get(f"{BASE}/inspections/{iid}/export", headers=auth_headers)
        assert "attachment" in export.headers["content-disposition"]
        assert export.json()["snapshot"]["params"]["BATT_FS_LOW_ACT"] == 0

    def test_bench_profile_downgrades_no_fix_to_warn(self, api_client, auth_headers, udp_port_env):
        with running_mock("bench") as port:
            udp_port_env(port)
            detail = _wait(api_client, auth_headers, _start(api_client, auth_headers, bench_mode=True))
        assert detail["status"] == "READY"
        checks = {c["id"]: c for c in detail["report"]["checks"]}
        assert checks["wir.gps_fix"]["status"] == "WARN"
        assert checks["fc.prearm"]["status"] == "WARN"
        assert _fail_ids(detail) == set()

    def test_no_flight_controller_fails_with_mission_planner_instructions(self, api_client, auth_headers, udp_port_env, monkeypatch):
        from tests.fc_mock import free_udp_port

        udp_port_env(free_udp_port())
        monkeypatch.setattr("aerofleet.hardware.fc_discovery.list_serial_ports", lambda: [])
        detail = _wait(api_client, auth_headers, _start(api_client, auth_headers))
        assert detail["status"] == "FAILED"
        assert "MAVLink Mirror" in detail["error"] and "14550" in detail["error"]



class TestHealthyAircraftFullWorkflow:
    """Inspection -> motor test A..D with ESC corroboration -> operator
    confirmations -> manual checklist -> verdict PASS."""

    def test_full_workflow(self, api_client, auth_headers, operator_headers, udp_port_env):
        with running_mock("healthy") as port:
            udp_port_env(port)
            iid = _start(api_client, operator_headers)
            detail = _wait(api_client, operator_headers, iid)
            assert detail["status"] == "READY"
            assert _fail_ids(detail) == set()
            assert detail["motor_layout"]["key"] == "quad_x"

            # A read-only user can see the report but cannot spin motors.
            assert api_client.get(f"{BASE}/inspections/{iid}", headers=auth_headers).status_code == 200
            denied = api_client.post(f"{BASE}/inspections/{iid}/motor-test", headers=auth_headers,
                                     json={"motor": "A", "props_removed_confirmed": True})
            assert denied.status_code == 403

            for letter in "ABCD":
                resp = api_client.post(f"{BASE}/inspections/{iid}/motor-test", headers=operator_headers,
                                       json={"motor": letter, "throttle_pct": 10, "duration_s": 0.5,
                                             "props_removed_confirmed": True})
                assert resp.status_code == 200, resp.text
                result = resp.json()["result"]
                assert result["accepted"] is True
                assert result["esc_corroboration"]["status"] == "corroborated", result["esc_corroboration"]
                confirm = api_client.post(f"{BASE}/inspections/{iid}/motor-test/{letter}/confirm",
                                          headers=operator_headers, json={"result": "correct"})
                assert confirm.status_code == 200

        # Quad X (AP_MotorsMatrix.cpp): A = motor 1 front-right CCW spins ESC 1; B = motor 4 spins ESC 4.
        detail = api_client.get(f"{BASE}/inspections/{iid}", headers=operator_headers).json()
        results = detail["motor_tests"]["results"]
        assert results["A"]["motor_number"] == 1 and results["A"]["esc_corroboration"]["spun_esc"] == [1]
        assert results["B"]["motor_number"] == 4 and results["B"]["esc_corroboration"]["spun_esc"] == [4]
        assert results["A"]["expected_direction"] == "CCW" and results["A"]["position"] == "front-right"

        # Measured and wizard checks can't be ticked off from the checklist.
        for cid in ("fs.fence_altitude", "mot.motor_test"):
            resp = api_client.post(f"{BASE}/inspections/{iid}/checklist", headers=operator_headers,
                                   json={"items": [{"check_id": cid, "result": "confirmed"}]})
            assert resp.status_code == 422, cid

        manual_ids = [c["id"] for c in detail["report"]["checks"] if c["kind"] == "manual" and c["status"] == "MANUAL"]
        items = [{"check_id": cid, "result": "confirmed", "note": "checked on the pad"} for cid in manual_ids]
        resp = api_client.post(f"{BASE}/inspections/{iid}/checklist", headers=operator_headers, json={"items": items})
        assert resp.status_code == 200, resp.text
        rep = resp.json()["report"]
        assert rep["manual_pending"] == []
        assert rep["verdict"] == "PASS"
        attested = next(c for c in rep["checks"] if c["id"] == "air.props")
        assert attested["status"] == "MANUAL" and attested["resolved"] is True  # attested, not "measured PASS"
        assert attested["attestation"]["by"].startswith("operator_")

        # Reporting a manual item as failed flips the verdict.
        resp = api_client.post(f"{BASE}/inspections/{iid}/checklist", headers=operator_headers,
                               json={"items": [{"check_id": "air.frame_integrity", "result": "failed", "note": "cracked arm"}]})
        assert resp.json()["report"]["verdict"] == "FAIL"


# ─────────────────────────────────────────────────────────────────────────
#  Motor-test safety gates. These share ONE ready inspection of a healthy
#  mock through a module-scoped TestClient (an inspection takes several
#  seconds of real MAVLink). Kept LAST in this module: a later
#  function-scoped api_client would re-run app startup and replace the
#  in-memory database this shared client's inspection lives in.
# ─────────────────────────────────────────────────────────────────────────

def _register(client, prefix, operator=False):
    import uuid

    from aerofleet.data.database import get_db_session
    from aerofleet.data.models.models import User

    username = f"{prefix}_{uuid.uuid4().hex[:8]}"
    client.post("/api/v1/auth/register",
                json={"username": username, "email": f"{username}@example.com", "password": "TestPass123!"})
    if operator:
        with get_db_session() as db:
            db.query(User).filter(User.username == username).first().is_operator = True
    token = client.post("/api/v1/auth/login", data={"username": username, "password": "TestPass123!"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def gate_env():
    from fastapi.testclient import TestClient

    from aerofleet.api.app import app
    from aerofleet.api.rate_limit import limiter

    with TestClient(app) as client:
        limiter.reset()
        op = _register(client, "gateop", operator=True)
        with running_mock("healthy") as port:
            # Explicit connection (auto=false) — also covers the manual-connection path.
            resp = client.post(f"{BASE}/inspections", headers=op, json={
                "auto": False, "connection": f"udpin:127.0.0.1:{port}", "uin": "UA-GATE",
                "weight_kg": 12.5, "sample_seconds": 2.0})
            iid = resp.json()["inspection_id"]
            detail = _wait(client, op, iid)
            assert detail["status"] == "READY", detail.get("error")
            assert detail["source"] == "manual"
            yield client, op, iid


def _spin(client, headers, iid, **body):
    payload = {"motor": "A", "props_removed_confirmed": True, "throttle_pct": 10, "duration_s": 0.5}
    payload.update(body)
    return client.post(f"{BASE}/inspections/{iid}/motor-test", headers=headers, json=payload)


class TestMotorTestGates:
    def test_refused_without_props_off_confirmation(self, gate_env):
        client, op, iid = gate_env
        for flag in (None, False):
            body = {"motor": "A", "throttle_pct": 10, "duration_s": 0.5}
            if flag is not None:
                body["props_removed_confirmed"] = flag
            resp = client.post(f"{BASE}/inspections/{iid}/motor-test", headers=op, json=body)
            assert resp.status_code == 400
            assert "propellers" in resp.json()["detail"]
        detail = client.get(f"{BASE}/inspections/{iid}", headers=op).json()
        assert not (detail["motor_tests"] or {}).get("log")  # nothing was sent to the vehicle

    def test_non_operator_is_refused(self, gate_env):
        client, _op, iid = gate_env
        assert _spin(client, _register(client, "gateuser"), iid).status_code == 403

    def test_unknown_motor_letter(self, gate_env):
        client, op, iid = gate_env
        assert _spin(client, op, iid, motor="E").status_code == 422  # a quad has A-D only

    def test_one_motor_at_a_time(self, gate_env):
        from aerofleet.hardware.fc_inspection_worker import HARDWARE_LOCK

        client, op, iid = gate_env
        with HARDWARE_LOCK:  # another motor test holding the flight controller
            resp = _spin(client, op, iid)
        assert resp.status_code == 409 and "one motor at a time" in resp.json()["detail"]

    def test_confirm_requires_a_spin_first(self, gate_env):
        client, op, iid = gate_env
        resp = client.post(f"{BASE}/inspections/{iid}/motor-test/D/confirm", headers=op, json={"result": "correct"})
        assert resp.status_code == 409

    def test_throttle_and_duration_are_capped(self, gate_env):
        client, op, iid = gate_env
        start = time.monotonic()
        resp = _spin(client, op, iid, motor="b", throttle_pct=80, duration_s=30)
        elapsed = time.monotonic() - start
        assert resp.status_code == 200, resp.text
        r = resp.json()["result"]
        assert r["letter"] == "B"
        assert r["throttle_pct"] == 15.0 and r["throttle_pct_requested"] == 80
        assert r["duration_s"] == 3.0 and r["capped"] is True
        assert elapsed < 12, "a 30 s request must not run for 30 s"

    def test_refused_when_armed(self, gate_env):
        client, op, _iid = gate_env
        with running_mock("healthy", "--start-armed") as port:
            resp = client.post(f"{BASE}/inspections", headers=op, json={
                "auto": False, "connection": f"udpin:127.0.0.1:{port}", "sample_seconds": 2.0})
            armed_iid = resp.json()["inspection_id"]
            assert _wait(client, op, armed_iid)["status"] == "READY"
            resp = _spin(client, op, armed_iid)
        assert resp.status_code == 409
        assert "ARMED" in resp.json()["detail"]
