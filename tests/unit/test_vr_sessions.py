"""Desktop ↔ headset pairing sessions (aerofleet/vr/sessions.py)."""
import time

import pytest

from aerofleet.vr import sessions as vs

pytestmark = pytest.mark.unit


@pytest.fixture
def reg():
    return vs.VrSessionRegistry()


def _pair(reg, owner="op"):
    reg.open(owner)
    r = reg.request_pairing("Quest 3", "192.168.1.40")
    reg.decide(owner, r.request_id, approve=True)
    return reg.poll_pairing(r.request_id)["token"]


def test_pairing_needs_an_open_session(reg):
    with pytest.raises(vs.SessionError) as e:
        reg.request_pairing("Quest 3", "192.168.1.40")
    assert e.value.status == 409


def test_request_is_pending_until_the_desktop_approves(reg):
    reg.open("op")
    r = reg.request_pairing("Quest 3", "192.168.1.40")
    assert len(r.confirm_code) == 4 and r.confirm_code.isdigit()
    assert reg.poll_pairing(r.request_id) == {"status": vs.PENDING}
    assert [p["request_id"] for p in reg.get("op").public()["pending_requests"]] == [r.request_id]


def test_approval_hands_the_token_over_exactly_once(reg):
    reg.open("op")
    r = reg.request_pairing("Quest 3", "192.168.1.40")
    reg.decide("op", r.request_id, approve=True)
    first = reg.poll_pairing(r.request_id)
    assert first["status"] == vs.APPROVED and len(first["token"]) > 30
    assert "token" not in reg.poll_pairing(r.request_id)       # a second poll can't fetch it again
    assert reg.resolve_token(first["token"]) is reg.get("op", touch=False)
    assert reg.get("op").device.name == "Quest 3"


def test_denied_request_gets_no_token(reg):
    reg.open("op")
    r = reg.request_pairing("Quest 3", "192.168.1.40")
    reg.decide("op", r.request_id, approve=False)
    assert reg.poll_pairing(r.request_id) == {"status": vs.DENIED}


def test_approving_one_headset_refuses_the_other_pending_ones(reg):
    reg.open("op")
    a = reg.request_pairing("Quest 3", "192.168.1.40")
    b = reg.request_pairing("Somebody else", "192.168.1.66")
    reg.decide("op", a.request_id, approve=True)
    assert reg.poll_pairing(b.request_id)["status"] == vs.DENIED


def test_pending_requests_are_capped(reg):
    reg.open("op")
    for _ in range(vs.MAX_PENDING_REQUESTS):
        reg.request_pairing("x", "1.2.3.4")
    with pytest.raises(vs.SessionError) as e:
        reg.request_pairing("x", "1.2.3.4")
    assert e.value.status == 429


def test_scenario_version_only_moves_when_the_scenario_changes(reg):
    reg.open("op")
    v1 = reg.set_scenario("op", {"city": "pune", "mode": "live"})
    assert reg.set_scenario("op", {"city": "pune", "mode": "live"}) == v1
    assert reg.set_scenario("op", {"city": "mumbai", "mode": "live"}) == v1 + 1


def test_closing_the_session_invalidates_the_headset_token(reg):
    token = _pair(reg)
    assert reg.resolve_token(token) is not None
    reg.close("op")
    assert reg.resolve_token(token) is None


def test_session_expires_when_the_desktop_stops_polling(reg, monkeypatch):
    token = _pair(reg)
    reg._session.last_desktop_poll = time.time() - vs.DESKTOP_IDLE_S - 1
    assert reg.resolve_token(token) is None


def test_local_device_token_for_quest_link_needs_no_pairing(reg):
    reg.open("op")
    token = reg.local_device("op", "This PC (Quest Link)")
    s = reg.resolve_token(token)
    assert s is not None and s.device.via == "local"


def test_heartbeat_records_what_the_headset_shows(reg):
    token = _pair(reg)
    reg.heartbeat(token, {"mode": "live", "city": "pune"})
    dev = reg.get("op").public()["device"]
    assert dev["online"] and dev["status"]["city"] == "pune"
    assert reg.heartbeat("not-a-token", {}) is None


def test_another_operator_cannot_see_or_close_the_session(reg):
    reg.open("op")
    assert reg.get("intruder") is None
    assert reg.close("intruder") is False


def test_open_notifies_listeners_and_close_too(reg):
    events = []
    reg.on_open.append(lambda s: events.append("open"))
    reg.on_close.append(lambda s: events.append("close"))
    reg.open("op")
    reg.close("op")
    assert events == ["open", "close"]
