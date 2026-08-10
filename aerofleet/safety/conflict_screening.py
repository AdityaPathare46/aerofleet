"""Airspace conflict pre-screening — runs before any council agent speaks.

Deterministic, cheap check for near-miss risk against other active drones
and geofence violations, before spending LLM compute on a full council
debate (aerofleet/agents/council.py). This mirrors the conjunction-
screening pattern used in space traffic management, retargeted at city
airspace: only escalate to the full council + the specialist Conflict
Avoidance Planner agent when this pre-screen finds a real risk.
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

CONFLICT_PROBABILITY_THRESHOLD = 1e-3


@dataclass
class ConflictEvent:
    other_drone_id: str
    time_of_closest_approach_s: float
    miss_distance_m: float
    conflict_probability: float
    required_action: str


@dataclass
class ConflictScreeningResult:
    max_conflict_probability: float
    conflicts: List[ConflictEvent]
    geofence_flags: List[str]
    airspace_telemetry: Dict
    screening_passed: bool
    conflict_avoidance_required: bool


class AirspaceScreeningModule:
    """
    Usage::
        screening = AirspaceScreeningModule()
        result = screening.screen(dispatch_plan, active_drones)
        dispatch_plan["airspace_telemetry"] = result.airspace_telemetry
    """

    def __init__(self, airspace_model=None):
        self.airspace = airspace_model

    def screen(self, dispatch_plan: Dict, active_drones: List[Dict]) -> ConflictScreeningResult:
        logger.info("Airspace pre-screening started")

        conflicts = self._find_conflicts(dispatch_plan, active_drones)
        geofence_flags = self._check_geofence_flags(dispatch_plan)

        max_pc = max((c.conflict_probability for c in conflicts), default=0.0)
        conflict_avoidance_required = max_pc > CONFLICT_PROBABILITY_THRESHOLD

        telemetry = self._build_telemetry(conflicts, geofence_flags, max_pc, conflict_avoidance_required)
        passed = not conflict_avoidance_required and len(geofence_flags) == 0

        logger.info(
            f"Airspace screening complete — max_conflict_p={max_pc:.2e}, "
            f"geofence_flags={len(geofence_flags)}, passed={passed}"
        )

        return ConflictScreeningResult(
            max_conflict_probability=max_pc,
            conflicts=conflicts,
            geofence_flags=geofence_flags,
            airspace_telemetry=telemetry,
            screening_passed=passed,
            conflict_avoidance_required=conflict_avoidance_required,
        )

    # ─────────────────────────────────────────────────────────────────────

    def _find_conflicts(self, dispatch_plan: Dict, active_drones: List[Dict]) -> List[ConflictEvent]:
        """Simplified conflict-probability model: drones whose routes pass
        close together AND arrive at that point within a short time window
        of each other are flagged, scaling with proximity and time-overlap."""
        conflicts: List[ConflictEvent] = []
        own_eta_s = float(dispatch_plan.get("eta_minutes", 5.0)) * 60.0
        min_sep_m = float(dispatch_plan.get("min_separation_m", 15.0))

        for other in active_drones:
            other_dist_m = float(other.get("distance_to_route_m", 9999.0))
            other_eta_s = float(other.get("eta_s", 9999.0))
            time_gap_s = abs(own_eta_s - other_eta_s)

            if other_dist_m < min_sep_m * 5 and time_gap_s < 30.0:
                proximity_factor = max(0.0, 1.0 - other_dist_m / (min_sep_m * 5))
                timing_factor = max(0.0, 1.0 - time_gap_s / 30.0)
                pc = round(proximity_factor * timing_factor, 4)
                if pc > 1e-4:
                    conflicts.append(
                        ConflictEvent(
                            other_drone_id=str(other.get("drone_id", "UNKNOWN")),
                            time_of_closest_approach_s=round(time_gap_s, 1),
                            miss_distance_m=round(other_dist_m, 1),
                            conflict_probability=pc,
                            required_action="HOLD" if pc > CONFLICT_PROBABILITY_THRESHOLD else "MONITOR",
                        )
                    )

        return sorted(conflicts, key=lambda c: c.conflict_probability, reverse=True)[:5]

    def _check_geofence_flags(self, dispatch_plan: Dict) -> List[str]:
        flags = []
        if dispatch_plan.get("in_red_zone", False):
            flags.append("ROUTE_CROSSES_DGCA_RED_ZONE")
        if dispatch_plan.get("in_yellow_zone", False) and not dispatch_plan.get("atc_permission", False):
            flags.append("YELLOW_ZONE_ATC_PERMISSION_MISSING")
        if float(dispatch_plan.get("altitude_m", 0)) > float(dispatch_plan.get("max_altitude_m", 100)):
            flags.append("ALTITUDE_CEILING_EXCEEDED")
        return flags

    def _build_telemetry(
        self,
        conflicts: List[ConflictEvent],
        geofence_flags: List[str],
        max_pc: float,
        conflict_avoidance_required: bool,
    ) -> Dict:
        return {
            "airspace_screening": {
                "max_conflict_probability": max_pc,
                "conflict_probability_threshold": CONFLICT_PROBABILITY_THRESHOLD,
                "conflict_avoidance_required": conflict_avoidance_required,
                "top_conflicts": [
                    {
                        "other_drone": c.other_drone_id,
                        "miss_distance_m": c.miss_distance_m,
                        "conflict_probability": c.conflict_probability,
                        "action": c.required_action,
                    }
                    for c in conflicts[:3]
                ],
                "geofence_flags": geofence_flags,
                "screening_timestamp": datetime.utcnow().isoformat(),
            }
        }
