"""Multi-Fault Handler — simultaneous multi-subsystem fault management for a drone.

Handles: motor failure, GPS loss, battery-critical, comms loss, weather
abort, payload-release failure, and geofence breach, including
simultaneous multi-subsystem failures with priority-based conflict
resolution between recovery actions.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FaultType(Enum):
    MOTOR = auto()
    GPS_LOSS = auto()
    BATTERY_CRITICAL = auto()
    COMMS_LOSS = auto()
    WEATHER_ABORT = auto()
    PAYLOAD_RELEASE_FAIL = auto()
    GEOFENCE_BREACH = auto()
    UNKNOWN = auto()


@dataclass
class ActiveFault:
    fault_id: str
    fault_type: FaultType
    severity: float          # 0-1
    onset_time: float
    affected_subsystems: List[str]
    recovery_action: Optional[str] = None
    resolved: bool = False


@dataclass
class MultiFaultReport:
    fault_count: int
    active_faults: List[ActiveFault]
    conflict_detected: bool
    resolution_priority: List[str]
    combined_recovery_plan: List[Dict[str, Any]]
    system_survivability: float  # 0=unrecoverable (forced landing), 1=fully recoverable


class MultiFaultHandler:
    """
    Simultaneous multi-fault handler with conflict resolution.

    Priority hierarchy (safety-critical first):
      1. MOTOR                 (loss of lift/control)
      2. GEOFENCE_BREACH       (imminent airspace violation)
      3. BATTERY_CRITICAL      (power survival / can it get home)
      4. COMMS_LOSS            (ground command link)
      5. GPS_LOSS              (navigation accuracy)
      6. WEATHER_ABORT         (environmental risk)
      7. PAYLOAD_RELEASE_FAIL  (delivery-specific, not flight-critical)

    Conflict Resolution:
      When two faults require contradictory actions (e.g. WEATHER_ABORT
      wants a hover-and-wait, but BATTERY_CRITICAL wants an immediate
      landing), the higher-priority fault's recovery action wins.
    """

    PRIORITY_ORDER = [
        FaultType.MOTOR,
        FaultType.GEOFENCE_BREACH,
        FaultType.BATTERY_CRITICAL,
        FaultType.COMMS_LOSS,
        FaultType.GPS_LOSS,
        FaultType.WEATHER_ABORT,
        FaultType.PAYLOAD_RELEASE_FAIL,
        FaultType.UNKNOWN,
    ]

    CONFLICTING_ACTIONS = {
        ("HOVER_AND_WAIT", "EMERGENCY_LANDING"): "EMERGENCY_LANDING",
        ("CONTINUE_MISSION", "RETURN_TO_HOME"): "RETURN_TO_HOME",
        ("MANUAL_OVERRIDE_REQUEST", "AUTONOMOUS_EMERGENCY_LANDING"): "AUTONOMOUS_EMERGENCY_LANDING",
    }

    def __init__(self) -> None:
        self._active_faults: Dict[str, ActiveFault] = {}
        logger.info("MultiFaultHandler initialised")

    def register_fault(
        self,
        fault_type: FaultType,
        severity: float,
        affected_subsystems: List[str],
        fault_id: Optional[str] = None,
    ) -> ActiveFault:
        fid = fault_id or f"{fault_type.name}-{time.monotonic():.0f}"
        fault = ActiveFault(
            fault_id=fid,
            fault_type=fault_type,
            severity=severity,
            onset_time=time.monotonic(),
            affected_subsystems=affected_subsystems,
        )
        self._active_faults[fid] = fault
        logger.warning(f"Fault registered: {fault_type.name} (severity={severity:.2f})")
        return fault

    def resolve_fault(self, fault_id: str) -> None:
        if fault_id in self._active_faults:
            self._active_faults[fault_id].resolved = True
            logger.info(f"Fault resolved: {fault_id}")

    def generate_recovery_plan(self) -> MultiFaultReport:
        active = [f for f in self._active_faults.values() if not f.resolved]

        if not active:
            return MultiFaultReport(
                fault_count=0, active_faults=[], conflict_detected=False,
                resolution_priority=[], combined_recovery_plan=[], system_survivability=1.0,
            )

        prioritised = sorted(
            active,
            key=lambda f: self.PRIORITY_ORDER.index(f.fault_type)
            if f.fault_type in self.PRIORITY_ORDER else len(self.PRIORITY_ORDER),
        )

        raw_actions = [self._get_recovery_action(f) for f in prioritised]
        resolved_actions, conflict_detected = self._resolve_conflicts(raw_actions, prioritised)
        survivability = self._compute_survivability(active)

        return MultiFaultReport(
            fault_count=len(active),
            active_faults=active,
            conflict_detected=conflict_detected,
            resolution_priority=[f.fault_id for f in prioritised],
            combined_recovery_plan=resolved_actions,
            system_survivability=round(survivability, 3),
        )

    def _get_recovery_action(self, fault: ActiveFault) -> Dict[str, Any]:
        actions = {
            FaultType.MOTOR:                 "AUTONOMOUS_EMERGENCY_LANDING",
            FaultType.GPS_LOSS:               "SWITCH_VISUAL_NAV_RTH",
            FaultType.BATTERY_CRITICAL:       "RETURN_TO_HOME",
            FaultType.COMMS_LOSS:             "AUTONOMOUS_EMERGENCY_LANDING",
            FaultType.WEATHER_ABORT:          "HOVER_AND_WAIT",
            FaultType.PAYLOAD_RELEASE_FAIL:   "RETURN_TO_DEPOT",
            FaultType.GEOFENCE_BREACH:        "IMMEDIATE_ALTITUDE_HOLD_AND_REROUTE",
            FaultType.UNKNOWN:                "AUTONOMOUS_EMERGENCY_LANDING",
        }
        return {
            "fault_id": fault.fault_id,
            "fault_type": fault.fault_type.name,
            "action": actions.get(fault.fault_type, "AUTONOMOUS_EMERGENCY_LANDING"),
            "priority": self.PRIORITY_ORDER.index(fault.fault_type),
        }

    def _resolve_conflicts(self, actions: List[Dict], faults: List[ActiveFault]) -> tuple:
        action_names = [a["action"] for a in actions]
        conflict_detected = False

        for (a1, a2), winner in self.CONFLICTING_ACTIONS.items():
            if a1 in action_names and a2 in action_names:
                conflict_detected = True
                loser = a1 if winner == a2 else a2
                for a in actions:
                    if a["action"] == loser:
                        a["action"] = winner
                        a["conflict_resolved"] = True
                        logger.warning(f"Conflict resolved: {loser} -> {winner}")

        return actions, conflict_detected

    def _compute_survivability(self, faults: List[ActiveFault]) -> float:
        if not faults:
            return 1.0
        weighted_severity = sum(
            f.severity * (1.0 / (self.PRIORITY_ORDER.index(f.fault_type) + 1))
            for f in faults
            if f.fault_type in self.PRIORITY_ORDER
        )
        return max(0.0, 1.0 - min(1.0, weighted_severity))
