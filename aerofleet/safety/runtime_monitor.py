"""
Runtime Safety Monitor — continuous watchdog for mission-critical constraints.

Complements the CBF gate (batch evaluation) with:
  - Continuous per-step runtime monitoring
  - Fail-safe state machine transitions
  - Watchdog timer for agent heartbeats
  - Safety envelope tracking
"""
from __future__ import annotations
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional
logger = logging.getLogger(__name__)

class SafetyMode(Enum):
    NOMINAL = auto()
    CAUTION = auto()
    WARNING = auto()
    EMERGENCY = auto()
    SAFE_HOLD = auto()

@dataclass
class SafetyViolation:
    constraint: str
    value: float
    threshold: float
    severity: str
    timestamp: float

@dataclass
class MonitorReport:
    mode: SafetyMode
    violations: List[SafetyViolation]
    watchdog_failures: List[str]
    health_score: float
    recommended_action: str

class RuntimeSafetyMonitor:
    """
    Runtime safety monitor with fail-safe state transitions and watchdog supervision.

    Safety constraints (checked every tick):
      - separation_km >= 1.0
      - fuel_remaining_kg >= 5.0  (5 kg reserve)
      - max_Pc <= 1e-3
      - power_w >= 50.0
      - attitude_error_deg <= 15.0
      - battery_soc >= 10%
    """

    CONSTRAINTS = {
        "separation_km": {"min": 1.0, "caution": 5.0, "warning": 2.0},
        "fuel_remaining_kg": {"min": 5.0, "caution": 20.0, "warning": 10.0},
        "max_Pc": {"max": 1e-3, "caution": 1e-4, "warning": 1e-3},
        "power_w": {"min": 50.0, "caution": 100.0, "warning": 75.0},
        "attitude_error_deg": {"max": 15.0, "caution": 5.0, "warning": 10.0},
        "battery_soc_pct": {"min": 10.0, "caution": 25.0, "warning": 15.0},
    }

    WATCHDOG_TIMEOUT_S = 60.0

    def __init__(self, on_emergency: Optional[Callable] = None) -> None:
        self._mode = SafetyMode.NOMINAL
        self._on_emergency = on_emergency
        self._heartbeats: Dict[str, float] = {}
        self._violation_log: List[SafetyViolation] = []
        logger.info("RuntimeSafetyMonitor initialised")

    @property
    def mode(self) -> SafetyMode:
        return self._mode

    def heartbeat(self, agent_id: str) -> None:
        self._heartbeats[agent_id] = time.monotonic()

    def tick(self, state: Dict[str, Any]) -> MonitorReport:
        """Evaluate all safety constraints for the current state."""
        violations: List[SafetyViolation] = []
        now = time.monotonic()

        for constraint, limits in self.CONSTRAINTS.items():
            val = state.get(constraint)
            if val is None:
                continue
            val = float(val)
            severity = None

            if "min" in limits and val < limits["min"]:
                severity = "EMERGENCY"
            elif "max" in limits and val > limits["max"]:
                severity = "EMERGENCY"
            elif "warning" in limits:
                lo = limits.get("min", float("-inf"))
                hi = limits.get("max", float("inf"))
                w_lo = limits.get("warning", limits.get("min", float("-inf")))
                w_hi = limits.get("warning", limits.get("max", float("inf")))
                if val < limits.get("warning", float("inf")) and val >= limits.get("min", float("-inf")):
                    if "min" in limits and val < limits.get("caution", 9e9):
                        severity = "WARNING"

            if severity:
                threshold = limits.get("min", limits.get("max", 0))
                v = SafetyViolation(
                    constraint=constraint, value=val,
                    threshold=threshold, severity=severity, timestamp=now,
                )
                violations.append(v)
                self._violation_log.append(v)

        # Watchdog
        watchdog_failures: List[str] = []
        for agent, last_beat in self._heartbeats.items():
            if now - last_beat > self.WATCHDOG_TIMEOUT_S:
                watchdog_failures.append(agent)

        # Mode transition
        new_mode = self._compute_mode(violations, watchdog_failures)
        if new_mode != self._mode:
            logger.warning(f"Safety mode: {self._mode.name} → {new_mode.name}")
            self._mode = new_mode
            if new_mode == SafetyMode.EMERGENCY and self._on_emergency:
                self._on_emergency(violations)

        health = 1.0 - min(1.0, len(violations) * 0.2 + len(watchdog_failures) * 0.1)
        action = self._recommend_action(self._mode, violations)

        return MonitorReport(
            mode=self._mode,
            violations=violations,
            watchdog_failures=watchdog_failures,
            health_score=round(health, 3),
            recommended_action=action,
        )

    def _compute_mode(self, violations: List[SafetyViolation], wdf: List[str]) -> SafetyMode:
        emergency = [v for v in violations if v.severity == "EMERGENCY"]
        if emergency or len(wdf) > 2:
            return SafetyMode.EMERGENCY
        if violations:
            return SafetyMode.WARNING
        if wdf:
            return SafetyMode.CAUTION
        return SafetyMode.NOMINAL

    def _recommend_action(self, mode: SafetyMode, violations: List[SafetyViolation]) -> str:
        if mode == SafetyMode.EMERGENCY:
            return "SAFE_HOLD_IMMEDIATELY"
        if mode == SafetyMode.WARNING:
            if any(v.constraint == "max_Pc" for v in violations):
                return "INITIATE_CAM"
            return "REDUCE_OPERATIONS"
        if mode == SafetyMode.CAUTION:
            return "MONITOR_CLOSELY"
        return "NOMINAL_OPERATIONS"
