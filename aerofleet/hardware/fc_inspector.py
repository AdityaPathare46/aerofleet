"""Read-only inspection of one ArduPilot flight controller over MAVLink.

Connects (same pymavlink connection-string conventions and GCS system id
255 as aerofleet/hardware/mavlink_link.py), then:

1. waits for the *vehicle's* HEARTBEAT (GCS/companion heartbeats ignored);
2. asks for the telemetry the compliance rules need with
   MAV_CMD_SET_MESSAGE_INTERVAL — a runtime stream-rate request like every
   ground station makes, not a saved parameter; it resets on reboot;
3. requests AUTOPILOT_VERSION (MAV_CMD_REQUEST_MESSAGE, falling back to
   MAV_CMD_REQUEST_AUTOPILOT_CAPABILITIES);
4. downloads the full parameter list (PARAM_REQUEST_LIST, then
   PARAM_REQUEST_READ by index for anything dropped, up to 3 retry rounds);
5. samples telemetry for ``sample_seconds``;
6. asks the autopilot to re-run its own arming checks
   (MAV_CMD_RUN_PREARM_CHECKS) and collects the "PreArm: ..." STATUSTEXTs.

The result is an immutable :class:`FCSnapshot`. Nothing in steps 1-6 changes
vehicle configuration. The one actuating operation, :meth:`FCInspector.motor_test`,
is separate and is only reachable through the operator-gated API endpoint,
which enforces its own safety gates before calling it.
"""
from __future__ import annotations


import time
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from aerofleet.hardware.fc_discovery import (
    SOURCE_MANUAL,
    in_use_message,
    is_busy_error,
)
from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)

ProgressCallback = Callable[[int, str], None]

# message name -> MAVLink message id, requested at 4 Hz (250 ms).
REQUESTED_STREAMS: Tuple[Tuple[str, int], ...] = (
    ("SYS_STATUS", 1), ("BATTERY_STATUS", 147), ("GPS_RAW_INT", 24), ("EKF_STATUS_REPORT", 193),
    ("VIBRATION", 241), ("RC_CHANNELS", 65), ("SERVO_OUTPUT_RAW", 36),
    ("ESC_TELEMETRY_1_TO_4", 11030), ("ESC_TELEMETRY_5_TO_8", 11031), ("POWER_STATUS", 125),
    ("RADIO_STATUS", 109), ("GLOBAL_POSITION_INT", 33),
)
_STREAM_INTERVAL_US = 250_000

# Latest-value telemetry kept in the snapshot.
_TRACKED = {name for name, _ in REQUESTED_STREAMS} | {"HEARTBEAT"}

_UINT16_MAX = 65535

# MAV_RESULT names for readable ACK reporting.
MAV_RESULT_NAMES = {
    0: "ACCEPTED", 1: "TEMPORARILY_REJECTED", 2: "DENIED", 3: "UNSUPPORTED", 4: "FAILED",
    5: "IN_PROGRESS", 6: "CANCELLED",
}
FIRMWARE_TYPE_NAMES = {0: "dev", 64: "alpha", 128: "beta", 192: "rc", 255: "official"}


class FCInspectionError(Exception):
    """Could not complete an inspection step (connection, no heartbeat...)."""


class FCPortBusyError(FCInspectionError):
    """The serial port is held by another program — almost always Mission Planner."""


def _freeze(obj: Any) -> Any:
    if isinstance(obj, dict):
        return MappingProxyType({k: _freeze(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return tuple(_freeze(v) for v in obj)
    return obj


def _thaw(obj: Any) -> Any:
    if isinstance(obj, Mapping):
        return {k: _thaw(v) for k, v in obj.items()}
    if isinstance(obj, tuple):
        return [_thaw(v) for v in obj]
    return obj


def _msg_to_dict(msg) -> Dict[str, Any]:
    d = {}
    for name in msg.get_fieldnames():
        v = getattr(msg, name)
        if isinstance(v, bytes):
            v = v.decode("utf-8", errors="replace").rstrip("\x00")
        elif isinstance(v, (list, tuple)):
            v = list(v)
        d[name] = v
    return d


def decode_firmware_version(flight_sw_version: int) -> Dict[str, Any]:
    """ArduPilot/PX4 pack (major<<24)|(minor<<16)|(patch<<8)|FIRMWARE_VERSION_TYPE."""
    major = (flight_sw_version >> 24) & 0xFF
    minor = (flight_sw_version >> 16) & 0xFF
    patch = (flight_sw_version >> 8) & 0xFF
    fw_type = flight_sw_version & 0xFF
    return {
        "major": major, "minor": minor, "patch": patch, "type": fw_type,
        "type_name": FIRMWARE_TYPE_NAMES.get(fw_type, f"type {fw_type}"),
        "version": f"{major}.{minor}.{patch}",
    }


@dataclass(frozen=True)
class FCSnapshot:
    """Everything one inspection observed. Immutable: mappings are
    MappingProxyType and sequences are tuples; use :meth:`to_dict` for JSON
    and :meth:`from_dict` to rebuild (e.g. for rule unit tests)."""

    connection: str
    source: str
    captured_at: float
    sample_seconds: float
    heartbeat: Mapping[str, Any]
    autopilot_version: Optional[Mapping[str, Any]]
    params: Mapping[str, float]
    param_count_expected: Optional[int]
    params_missing_count: int
    telemetry: Mapping[str, Mapping[str, Any]]
    vibration_samples: Tuple[Mapping[str, Any], ...]
    esc_rpm_max: Tuple[int, ...]
    statustexts: Tuple[Mapping[str, Any], ...]
    prearm_messages: Tuple[str, ...]
    prearm_command_result: Optional[str]
    message_counts: Mapping[str, int]
    notes: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "connection": self.connection,
            "source": self.source,
            "captured_at": self.captured_at,
            "sample_seconds": self.sample_seconds,
            "heartbeat": _thaw(self.heartbeat),
            "autopilot_version": _thaw(self.autopilot_version) if self.autopilot_version else None,
            "params": dict(self.params),
            "param_count_expected": self.param_count_expected,
            "params_missing_count": self.params_missing_count,
            "telemetry": _thaw(self.telemetry),
            "vibration_samples": _thaw(self.vibration_samples),
            "esc_rpm_max": list(self.esc_rpm_max),
            "statustexts": _thaw(self.statustexts),
            "prearm_messages": list(self.prearm_messages),
            "prearm_command_result": self.prearm_command_result,
            "message_counts": dict(self.message_counts),
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "FCSnapshot":
        return cls(
            connection=d.get("connection", ""),
            source=d.get("source", SOURCE_MANUAL),
            captured_at=float(d.get("captured_at", 0.0)),
            sample_seconds=float(d.get("sample_seconds", 0.0)),
            heartbeat=_freeze(dict(d.get("heartbeat") or {})),
            autopilot_version=_freeze(dict(d["autopilot_version"])) if d.get("autopilot_version") else None,
            params=MappingProxyType({k: float(v) for k, v in (d.get("params") or {}).items()}),
            param_count_expected=d.get("param_count_expected"),
            params_missing_count=int(d.get("params_missing_count", 0)),
            telemetry=_freeze(dict(d.get("telemetry") or {})),
            vibration_samples=_freeze(list(d.get("vibration_samples") or [])),
            esc_rpm_max=tuple(d.get("esc_rpm_max") or ()),
            statustexts=_freeze(list(d.get("statustexts") or [])),
            prearm_messages=tuple(d.get("prearm_messages") or ()),
            prearm_command_result=d.get("prearm_command_result"),
            message_counts=MappingProxyType(dict(d.get("message_counts") or {})),
            notes=tuple(d.get("notes") or ()),
        )


class FCInspector:
    def __init__(
        self,
        connection: str,
        source: str = SOURCE_MANUAL,
        sample_seconds: float = 6.0,
        progress_cb: Optional[ProgressCallback] = None,
        heartbeat_timeout_s: float = 8.0,
        param_timeout_s: float = 30.0,
        source_system: int = 255,
    ):
        self.connection = connection
        self.source = source
        self.sample_seconds = max(1.0, float(sample_seconds))
        self.heartbeat_timeout_s = heartbeat_timeout_s
        self.param_timeout_s = param_timeout_s
        self.source_system = source_system
        self._progress_cb = progress_cb
        self._conn = None
        self._target: Tuple[int, int] = (1, 1)

        self._heartbeat: Dict[str, Any] = {}
        self._autopilot_version: Optional[Dict[str, Any]] = None
        self._params: Dict[str, float] = {}
        self._param_index: Dict[int, str] = {}
        self._param_count: Optional[int] = None
        self._latest: Dict[str, Dict[str, Any]] = {}
        self._vibration: List[Dict[str, Any]] = []
        self._statustexts: List[Dict[str, Any]] = []
        self._acks: List[Tuple[int, int]] = []
        self._counts: Dict[str, int] = {}
        self._esc_rpm_max: List[int] = [0] * 8
        self._notes: List[str] = []
        self._last_gcs_hb = 0.0

    # ─────────────────────────────────────────────────────────────────
    #  Connection
    # ─────────────────────────────────────────────────────────────────

    def _progress(self, pct: int, stage: str) -> None:
        logger.debug(f"[fc-inspect] {pct}% {stage}")
        if self._progress_cb:
            try:
                self._progress_cb(pct, stage)
            except Exception as exc:  # progress reporting must never abort an inspection
                logger.warning(f"FC inspection progress callback failed: {exc}")

    def connect(self) -> Dict[str, Any]:
        from pymavlink import mavutil

        self._progress(3, f"Connecting to {self.connection}")
        try:
            self._conn = mavutil.mavlink_connection(
                self.connection, source_system=self.source_system, autoreconnect=False,
            )
        except Exception as exc:
            device = self.connection.split(",")[0]
            if is_busy_error(exc):
                raise FCPortBusyError(in_use_message(device)) from exc
            if isinstance(exc, OSError) and "address already in use" in str(exc).lower():
                raise FCInspectionError(
                    f"{self.connection} is already bound by another program on this PC — point "
                    "Mission Planner's MAVLink mirror at a free port (e.g. 14551)."
                ) from exc
            raise FCInspectionError(f"Could not open {self.connection}: {exc}") from exc

        self._progress(6, "Waiting for the vehicle heartbeat")
        deadline = time.monotonic() + self.heartbeat_timeout_s
        while time.monotonic() < deadline:
            msg = self._conn.recv_match(type="HEARTBEAT", blocking=True, timeout=0.5)
            if msg is None:
                self._send_gcs_heartbeat()
                continue
            if msg.type == mavutil.mavlink.MAV_TYPE_GCS or msg.autopilot == mavutil.mavlink.MAV_AUTOPILOT_INVALID:
                continue
            self._target = (msg.get_srcSystem(), msg.get_srcComponent())
            self._record(msg)
            self._progress(10, f"Connected to system {self._target[0]}")
            return dict(self._heartbeat)
        self.close()
        raise FCInspectionError(
            f"No vehicle HEARTBEAT on {self.connection} within {self.heartbeat_timeout_s:.0f}s — is the "
            "flight controller powered and, for a Mission Planner forward, is the MAVLink mirror connected?"
        )

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def __enter__(self) -> "FCInspector":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    @property
    def armed(self) -> Optional[bool]:
        if not self._heartbeat:
            return None
        return bool(self._heartbeat.get("base_mode", 0) & 128)  # MAV_MODE_FLAG_SAFETY_ARMED

    # ─────────────────────────────────────────────────────────────────
    #  Message plumbing
    # ─────────────────────────────────────────────────────────────────

    def _send_gcs_heartbeat(self) -> None:
        from pymavlink import mavutil

        now = time.monotonic()
        if self._conn is None or now - self._last_gcs_hb < 1.0:
            return
        self._last_gcs_hb = now
        try:
            self._conn.mav.heartbeat_send(
                mavutil.mavlink.MAV_TYPE_GCS, mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0,
            )
        except Exception:
            pass

    def _record(self, msg) -> None:
        t = msg.get_type()
        if t == "BAD_DATA":
            return
        src = msg.get_srcSystem()
        # Only the inspected vehicle's own messages — except RADIO_STATUS,
        # which SiK radios send under their own system id (51).
        if src != self._target[0] and t != "RADIO_STATUS" and self._heartbeat:
            return
        self._counts[t] = self._counts.get(t, 0) + 1
        if t == "HEARTBEAT":
            if msg.type == 6:  # MAV_TYPE_GCS
                return
            self._heartbeat = {
                "type": msg.type, "autopilot": msg.autopilot, "base_mode": msg.base_mode,
                "custom_mode": msg.custom_mode, "system_status": msg.system_status,
                "mavlink_version": msg.mavlink_version, "system_id": src,
                "component_id": msg.get_srcComponent(),
                "armed": bool(msg.base_mode & 128),
            }
            self._latest["HEARTBEAT"] = dict(self._heartbeat)
        elif t == "PARAM_VALUE":
            name = msg.param_id.rstrip("\x00") if isinstance(msg.param_id, str) else msg.param_id.decode().rstrip("\x00")
            self._params[name] = float(msg.param_value)
            if 0 <= msg.param_index < _UINT16_MAX:
                self._param_index[msg.param_index] = name
            if msg.param_count and msg.param_count < _UINT16_MAX:
                self._param_count = msg.param_count
        elif t == "AUTOPILOT_VERSION":
            d = _msg_to_dict(msg)
            d["firmware"] = decode_firmware_version(msg.flight_sw_version)
            d["board_id"] = (msg.board_version >> 16) & 0xFFFF
            d["flight_custom_version_str"] = bytes(
                b for b in (msg.flight_custom_version or []) if b
            ).decode("ascii", errors="replace")
            for k in ("uid2", "middleware_custom_version", "os_custom_version", "flight_custom_version"):
                d.pop(k, None)
            d["uid"] = f"{msg.uid:016X}"
            self._autopilot_version = d
        elif t == "STATUSTEXT":
            text = msg.text if isinstance(msg.text, str) else msg.text.decode("utf-8", errors="replace")
            self._statustexts.append({"severity": msg.severity, "text": text.rstrip("\x00"), "t": time.time()})
        elif t == "COMMAND_ACK":
            self._acks.append((msg.command, msg.result))
        elif t == "VIBRATION":
            d = _msg_to_dict(msg)
            d["t"] = time.time()
            self._vibration.append(d)
            self._latest[t] = d
        elif t in ("ESC_TELEMETRY_1_TO_4", "ESC_TELEMETRY_5_TO_8"):
            base = 0 if t.endswith("1_TO_4") else 4
            for i, rpm in enumerate(msg.rpm):
                self._esc_rpm_max[base + i] = max(self._esc_rpm_max[base + i], int(rpm))
            self._latest[t] = _msg_to_dict(msg)
        elif t in _TRACKED:
            self._latest[t] = _msg_to_dict(msg)

    def _pump(self, duration_s: float, until: Optional[Callable[[], bool]] = None) -> None:
        deadline = time.monotonic() + duration_s
        while time.monotonic() < deadline:
            if until is not None and until():
                return
            msg = self._conn.recv_match(blocking=True, timeout=min(0.2, max(0.01, deadline - time.monotonic())))
            self._send_gcs_heartbeat()
            if msg is not None:
                self._record(msg)

    def _command_long(self, command: int, params: Sequence[float]) -> None:
        p = list(params) + [0.0] * (7 - len(params))
        self._conn.mav.command_long_send(self._target[0], self._target[1], command, 0, *p[:7])

    def _command_and_ack(self, command: int, params: Sequence[float], timeout_s: float = 3.0) -> Optional[int]:
        start = len(self._acks)
        self._command_long(command, params)
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            for cmd, result in self._acks[start:]:
                if cmd == command:
                    return result
            self._pump(0.1)
        return None

    # ─────────────────────────────────────────────────────────────────
    #  Inspection steps
    # ─────────────────────────────────────────────────────────────────

    def request_streams(self) -> None:
        from pymavlink import mavutil

        self._progress(12, "Requesting telemetry streams")
        for _name, msg_id in REQUESTED_STREAMS:
            self._command_long(mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, (msg_id, _STREAM_INTERVAL_US))
            self._pump(0.02)

    def fetch_autopilot_version(self) -> Optional[Dict[str, Any]]:
        from pymavlink import mavutil

        self._progress(15, "Reading firmware and board identity")
        for attempt in range(2):
            self._command_long(mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE,
                               (mavutil.mavlink.MAVLINK_MSG_ID_AUTOPILOT_VERSION,))
            self._pump(1.5, until=lambda: self._autopilot_version is not None)
            if self._autopilot_version:
                return self._autopilot_version
        self._command_long(mavutil.mavlink.MAV_CMD_REQUEST_AUTOPILOT_CAPABILITIES, (1,))
        self._pump(1.5, until=lambda: self._autopilot_version is not None)
        if self._autopilot_version is None:
            self._notes.append("AUTOPILOT_VERSION not received — firmware version and board identity unknown.")
        return self._autopilot_version

    def fetch_params(self) -> Dict[str, float]:
        self._progress(20, "Downloading parameters")
        t, s = self._target
        self._conn.mav.param_request_list_send(t, s)
        overall_deadline = time.monotonic() + self.param_timeout_s
        last_count = -1
        idle_since = time.monotonic()
        # Phase 1 — the streamed list. Done when complete or 1.5 s without progress.
        while time.monotonic() < overall_deadline:
            self._pump(0.25)
            got = len(self._param_index)
            if self._param_count and got >= self._param_count:
                break
            if got != last_count:
                last_count = got
                idle_since = time.monotonic()
                if self._param_count:
                    self._progress(20 + int(35 * got / self._param_count), f"Downloading parameters ({got}/{self._param_count})")
            elif time.monotonic() - idle_since > (1.5 if got else 4.0):
                break

        # Phase 2 — ask again, by index, for anything dropped.
        for round_no in range(1, 4):
            if not self._param_count:
                break
            missing = [i for i in range(self._param_count) if i not in self._param_index]
            if not missing or time.monotonic() > overall_deadline:
                break
            self._progress(55, f"Re-requesting {len(missing)} missing parameters (round {round_no})")
            for i in missing:
                self._conn.mav.param_request_read_send(t, s, b"", i)
                if i % 20 == 19:
                    self._pump(0.02)
            self._pump(1.0 + 0.01 * len(missing),
                       until=lambda: all(j in self._param_index for j in missing))

        missing_count = (self._param_count - len(self._param_index)) if self._param_count else 0
        if not self._params:
            self._notes.append(
                "No parameters received. Over a Mission Planner forward this usually means \"Write\" "
                "is not ticked in its MAVLink Mirror dialog, so our requests are dropped."
            )
        elif missing_count > 0:
            self._notes.append(f"{missing_count} of {self._param_count} parameters still missing after 3 retry rounds.")
        self._progress(58, f"Parameters: {len(self._params)} received")
        return dict(self._params)

    def sample_telemetry(self) -> None:
        steps = max(1, int(self.sample_seconds / 0.5))
        for i in range(steps):
            self._pump(self.sample_seconds / steps)
            self._progress(60 + int(28 * (i + 1) / steps),
                           f"Sampling telemetry ({(i + 1) * self.sample_seconds / steps:.1f}/{self.sample_seconds:.0f} s)")

    def run_prearm_checks(self) -> Optional[str]:
        from pymavlink import mavutil

        self._progress(90, "Running the autopilot's own pre-arm checks")
        result = self._command_and_ack(mavutil.mavlink.MAV_CMD_RUN_PREARM_CHECKS, (), timeout_s=3.0)
        # ArduPilot emits the PreArm STATUSTEXTs right after the ACK.
        self._pump(1.0)
        name = MAV_RESULT_NAMES.get(result, str(result)) if result is not None else None
        if result is None:
            self._notes.append("MAV_CMD_RUN_PREARM_CHECKS was not acknowledged; PreArm results rely on "
                               "periodic STATUSTEXTs and the SYS_STATUS pre-arm health bit only.")
        return name

    def run(self) -> FCSnapshot:
        """Full read-only inspection. Always closes the connection."""
        try:
            if self._conn is None:
                self.connect()
            self.request_streams()
            self.fetch_autopilot_version()
            self.fetch_params()
            self._progress(60, "Sampling telemetry")
            self.sample_telemetry()
            prearm_result = self.run_prearm_checks()
            snapshot = self.snapshot(prearm_result)
            self._progress(97, "Snapshot captured")
            return snapshot
        finally:
            self.close()

    def snapshot(self, prearm_result: Optional[str] = None) -> FCSnapshot:
        prearm = []
        for st in self._statustexts:
            text = st["text"]
            if text.lower().startswith("prearm") and text not in prearm:
                prearm.append(text)
        missing = (self._param_count - len(self._param_index)) if self._param_count else 0
        return FCSnapshot(
            connection=self.connection,
            source=self.source,
            captured_at=time.time(),
            sample_seconds=self.sample_seconds,
            heartbeat=_freeze(dict(self._heartbeat)),
            autopilot_version=_freeze(dict(self._autopilot_version)) if self._autopilot_version else None,
            params=MappingProxyType(dict(self._params)),
            param_count_expected=self._param_count,
            params_missing_count=max(0, missing),
            telemetry=_freeze({k: dict(v) for k, v in self._latest.items()}),
            vibration_samples=_freeze([dict(v) for v in self._vibration]),
            esc_rpm_max=tuple(self._esc_rpm_max),
            statustexts=_freeze([dict(s) for s in self._statustexts]),
            prearm_messages=tuple(prearm),
            prearm_command_result=prearm_result,
            message_counts=MappingProxyType(dict(self._counts)),
            notes=tuple(self._notes),
        )

    # ─────────────────────────────────────────────────────────────────
    #  Motor test — actuating; callers (the API) enforce the safety gates
    # ─────────────────────────────────────────────────────────────────

    def motor_test(self, test_order: int, throttle_pct: float, duration_s: float) -> Dict[str, Any]:
        """Spin ONE motor via MAV_CMD_DO_MOTOR_TEST.

        param1 = test-order position (ArduCopter always interprets it as the
        sequence letter: 1 = A), param2 = 0 (MOTOR_TEST_THROTTLE_PERCENT),
        param3 = throttle %, param4 = timeout s, param5 = 1 motor,
        param6 = MOTOR_TEST_ORDER_SEQUENCE. Refuses if the heartbeat says
        armed. Records the highest ESC rpm seen per ESC channel during the
        spin (ESC telemetry is optional hardware; zeros mean "not reported")."""
        from pymavlink import mavutil

        if self._conn is None:
            self.connect()
        self._pump(0.6, until=lambda: "ESC_TELEMETRY_1_TO_4" in self._latest)
        if self.armed:
            raise FCInspectionError("Vehicle is ARMED — motor test refused.")
        self._command_long(mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, (11030, 100_000))
        self._command_long(mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, (11031, 100_000))
        esc_seen_before = "ESC_TELEMETRY_1_TO_4" in self._latest or "ESC_TELEMETRY_5_TO_8" in self._latest
        self._esc_rpm_max = [0] * 8
        start = time.time()
        result = self._command_and_ack(
            mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST,
            (float(test_order), float(mavutil.mavlink.MOTOR_TEST_THROTTLE_PERCENT), float(throttle_pct),
             float(duration_s), 1.0, float(mavutil.mavlink.MOTOR_TEST_ORDER_SEQUENCE)),
            timeout_s=3.0,
        )
        accepted = result == mavutil.mavlink.MAV_RESULT_ACCEPTED
        if accepted:
            self._pump(max(0.0, duration_s - (time.time() - start)) + 0.5)
        esc_available = esc_seen_before or "ESC_TELEMETRY_1_TO_4" in self._latest or "ESC_TELEMETRY_5_TO_8" in self._latest
        statustexts = [s["text"] for s in self._statustexts if s["t"] >= start - 0.1]
        return {
            "ack_result": MAV_RESULT_NAMES.get(result, str(result)) if result is not None else "NO_ACK",
            "accepted": accepted,
            "esc_telemetry_available": esc_available,
            "esc_rpm_max": list(self._esc_rpm_max) if esc_available else None,
            "statustexts": statustexts,
            "started_at": start,
        }
