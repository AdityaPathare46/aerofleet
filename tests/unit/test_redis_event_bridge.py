"""Unit tests for aerofleet/event_bus/redis_bus.py (Phase AH). Redis is not
running in this environment (or CI) — every test mocks the redis client
directly rather than requiring a real server, matching how this module is
actually meant to behave when AEROFLEET_REDIS_URL is unset: a transparent,
zero-behavior-change pass-through.
"""
import json
from unittest.mock import AsyncMock, patch

import pytest

from aerofleet.event_bus.async_bus import Event
from aerofleet.event_bus.redis_bus import RedisEventBridge, get_redis_client, get_redis_url

pytestmark = pytest.mark.unit


def _event(source="DRONE-1") -> Event:
    return Event(
        event_id="evt-1", event_type="telemetry.update", source=source,
        payload={"lat": 18.5, "lon": 73.8}, priority=1, timestamp=0.0,
    )


class TestNoRedisConfigured:
    def test_get_redis_url_is_none_when_unset(self, monkeypatch):
        monkeypatch.delenv("AEROFLEET_REDIS_URL", raising=False)
        assert get_redis_url() is None

    def test_get_redis_client_is_none_when_unset(self, monkeypatch):
        monkeypatch.delenv("AEROFLEET_REDIS_URL", raising=False)
        assert get_redis_client() is None

    @pytest.mark.asyncio
    async def test_bridge_reports_disabled_and_relay_is_a_no_op(self, monkeypatch):
        monkeypatch.delenv("AEROFLEET_REDIS_URL", raising=False)
        received = []
        bridge = RedisEventBridge(on_relayed_event=received.append)
        assert bridge.redis_enabled is False
        await bridge.relay_to_redis(_event())  # must not raise
        assert received == []

    @pytest.mark.asyncio
    async def test_listen_forever_returns_immediately_when_disabled(self, monkeypatch):
        monkeypatch.delenv("AEROFLEET_REDIS_URL", raising=False)
        bridge = RedisEventBridge(on_relayed_event=lambda e: None)
        await bridge.listen_forever()  # would hang forever if this didn't early-return


class TestRedisConfigured:
    @pytest.mark.asyncio
    async def test_relay_to_redis_publishes_the_event(self, monkeypatch):
        monkeypatch.setenv("AEROFLEET_REDIS_URL", "redis://localhost:6379/0")
        mock_redis = AsyncMock()
        with patch("aerofleet.event_bus.redis_bus.get_redis_client", return_value=mock_redis):
            bridge = RedisEventBridge(on_relayed_event=lambda e: None)
            assert bridge.redis_enabled is True
            await bridge.relay_to_redis(_event())

        mock_redis.publish.assert_called_once()
        channel, payload = mock_redis.publish.call_args[0]
        assert channel == "aerofleet:events"
        envelope = json.loads(payload)
        assert envelope["event"]["source"] == "DRONE-1"
        assert "origin" in envelope

    @pytest.mark.asyncio
    async def test_relay_failure_does_not_raise(self, monkeypatch):
        """A dead/unreachable Redis must never take down the caller — the
        local telemetry path (already dispatched before relay_to_redis is
        even called) must keep working."""
        monkeypatch.setenv("AEROFLEET_REDIS_URL", "redis://localhost:6379/0")
        mock_redis = AsyncMock()
        mock_redis.publish.side_effect = ConnectionError("redis unreachable")
        with patch("aerofleet.event_bus.redis_bus.get_redis_client", return_value=mock_redis):
            bridge = RedisEventBridge(on_relayed_event=lambda e: None)
            await bridge.relay_to_redis(_event())  # must not raise

    def test_handle_message_skips_self_originated_events(self, monkeypatch):
        """The core anti-ping-pong invariant: an event this same process
        relayed out must not be handed back to on_relayed_event when it
        arrives back via this process's own Redis subscription."""
        monkeypatch.setenv("AEROFLEET_REDIS_URL", "redis://localhost:6379/0")
        received = []
        with patch("aerofleet.event_bus.redis_bus.get_redis_client", return_value=AsyncMock()):
            bridge = RedisEventBridge(on_relayed_event=received.append)

        import asyncio
        from aerofleet.event_bus import redis_bus as redis_bus_module

        own_envelope = json.dumps({
            "origin": redis_bus_module._PROCESS_ID,
            "event": {
                "event_id": "e1", "event_type": "telemetry.update", "source": "D1",
                "payload": {}, "priority": 1, "timestamp": 0.0,
            },
        })
        asyncio.run(bridge._handle_message({"data": own_envelope}))
        assert received == []

    def test_handle_message_dispatches_foreign_events(self, monkeypatch):
        monkeypatch.setenv("AEROFLEET_REDIS_URL", "redis://localhost:6379/0")
        received = []
        with patch("aerofleet.event_bus.redis_bus.get_redis_client", return_value=AsyncMock()):
            bridge = RedisEventBridge(on_relayed_event=received.append)

        import asyncio

        foreign_envelope = json.dumps({
            "origin": "some-other-worker-process-id",
            "event": {
                "event_id": "e2", "event_type": "telemetry.update", "source": "D2",
                "payload": {"lat": 1.0}, "priority": 1, "timestamp": 0.0,
            },
        })
        asyncio.run(bridge._handle_message({"data": foreign_envelope}))
        assert len(received) == 1
        assert received[0].source == "D2"

    def test_handle_message_ignores_malformed_payloads(self, monkeypatch):
        monkeypatch.setenv("AEROFLEET_REDIS_URL", "redis://localhost:6379/0")
        received = []
        with patch("aerofleet.event_bus.redis_bus.get_redis_client", return_value=AsyncMock()):
            bridge = RedisEventBridge(on_relayed_event=received.append)

        import asyncio

        asyncio.run(bridge._handle_message({"data": "not json"}))
        assert received == []


class TestHardwareOwnerGate:
    def test_defaults_to_owner_when_unset(self, monkeypatch):
        monkeypatch.delenv("AEROFLEET_HARDWARE_OWNER", raising=False)
        from aerofleet.api.routes.hardware import hardware_owner_enabled
        assert hardware_owner_enabled() is True

    @pytest.mark.parametrize("value", ["0", "false", "False", "no"])
    def test_disabled_by_falsy_values(self, monkeypatch, value):
        monkeypatch.setenv("AEROFLEET_HARDWARE_OWNER", value)
        from aerofleet.api.routes.hardware import hardware_owner_enabled
        assert hardware_owner_enabled() is False

    def test_enabled_by_1(self, monkeypatch):
        monkeypatch.setenv("AEROFLEET_HARDWARE_OWNER", "1")
        from aerofleet.api.routes.hardware import hardware_owner_enabled
        assert hardware_owner_enabled() is True
