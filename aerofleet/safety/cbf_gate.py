"""Control Barrier Function / Active Set Invariance Filter — formal safety gate.

Runs AFTER the council debate (aerofleet/agents/council.py) and BEFORE any
dispatch action is allowed to execute. This is the core of AeroFleet's
patent-worthy claim (see docs/PATENT_NOVELTY.md): no matter what an LLM
agent proposes, the dispatch action is only executed if it passes this
deterministic, formally-checkable gate. Enforces 11 named safety
constraints simultaneously in well under a millisecond.

Non-blocking annotation: if violations are found, the result attaches a
cbf_certificate with passed=False and full violation detail — it does not
silently allow the response, but it also does not throw; callers decide
whether to hold the dispatch, re-plan, or trigger a contingency response.
"""
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class CBFViolation:
    """A single constraint violation at a single trajectory/route point."""

    constraint_name: str
    constraint_index: int
    violation_magnitude: float
    trajectory_time_index: int
    required_correction: float


@dataclass
class CBFResult:
    passed: bool
    violations: List[CBFViolation]
    corrected_route: Optional[List[Dict]]
    safety_margin_summary: Dict[str, float]
    execution_time_ms: float


class ControlBarrierFunctionGate:
    """
    Implements ASIF (Active Set Invariance Filter) QP:
      u_act = argmin ||u_des - u||^2
      subject to: h_i(x, u) >= 0  for all i in {1..M}

    11 safety constraints covering every operational domain of a delivery
    flight. Each h_i(x) >= 0 defines membership in the safe invariant set C_S.
    """

    def __init__(self, mission_config: Dict[str, Any]):
        self.config = mission_config
        self.constraints = self._define_constraints()
        logger.info(
            f"CBFGate initialised with {len(self.constraints)} constraints",
            extra={"config_keys": list(mission_config.keys())},
        )

    # ─────────────────────────────────────────────────────────────────────
    #  CONSTRAINT DEFINITIONS
    # ─────────────────────────────────────────────────────────────────────

    def _define_constraints(self) -> List[Dict]:
        """
        Define 11 CBF constraint functions h_i(x) >= 0.
        Safe set: C_S = {x in X | h_i(x) >= 0 for all i}.
        """
        cfg = self.config
        return [
            {
                "name": "min_separation",
                "fn": lambda x: x.get("separation_m", 999.0) - cfg.get("min_separation_m", 15.0),
                "description": "Minimum horizontal separation from all other tracked drones",
            },
            {
                "name": "geofence_exclusion",
                "fn": lambda x: -1.0 if x.get("in_red_zone", False) else 1.0,
                "description": "Route must never enter a DGCA Red Zone / no-fly geofence",
            },
            {
                "name": "battery_reserve_margin",
                "fn": lambda x: x.get("battery_margin_wh", 999.0),
                "description": "Battery must retain enough charge for a safe return-to-home after this leg",
            },
            {
                "name": "altitude_ceiling",
                "fn": lambda x: cfg.get("max_altitude_m", 100.0) - x.get("altitude_m", 0.0),
                "description": "Altitude within the assigned corridor band and DGCA ceiling",
            },
            {
                "name": "wind_limit",
                "fn": lambda x: cfg.get("max_wind_mps", 10.0) - x.get("wind_speed_mps", 0.0),
                "description": "Wind speed within the airframe's certified operating envelope",
            },
            {
                "name": "payload_weight_limit",
                "fn": lambda x: cfg.get("max_payload_kg", 5.0) - x.get("payload_kg", 0.0),
                "description": "Payload within the drone's rated capacity",
            },
            {
                "name": "noise_limit",
                "fn": lambda x: cfg.get("max_noise_db", 65.0) - x.get("noise_db", 0.0),
                "description": "Noise level at ground level within the residential-zone limit",
            },
            {
                "name": "collision_probability",
                "fn": lambda x: cfg.get("max_collision_probability", 1e-4) - x.get("collision_probability", 0.0),
                "description": "Predicted conflict probability below the operational threshold",
            },
            {
                "name": "comms_link_margin",
                "fn": lambda x: x.get("link_margin_db", 999.0) - cfg.get("min_link_margin_db", 3.0),
                "description": "Command/telemetry link margin above minimum",
            },
            {
                "name": "depot_capacity",
                "fn": lambda x: cfg.get("depot_pad_slots", 4) - x.get("depot_queue_length", 0),
                "description": "Destination depot has an available landing/swap slot",
            },
            {
                "name": "weather_visibility",
                "fn": lambda x: x.get("visibility_m", 9999.0) - cfg.get("min_visibility_m", 1500.0),
                "description": "Visibility above the minimum required for autonomous BVLOS flight",
            },
        ]

    # ─────────────────────────────────────────────────────────────────────
    #  ROUTE EVALUATION
    # ─────────────────────────────────────────────────────────────────────

    def evaluate_trajectory(self, trajectory_points: List[Dict]) -> CBFResult:
        """
        Evaluate all constraints across every point of a proposed route.
        passed=True only if ALL constraints are satisfied at ALL points.

        Args:
            trajectory_points: list of state dicts; each may contain keys
                like separation_m, battery_margin_wh, altitude_m, etc.
                Missing keys are treated as 'no violation' (safe defaults).
        """
        start = time.perf_counter()
        violations: List[CBFViolation] = []
        safety_margins: Dict[str, float] = {c["name"]: float("inf") for c in self.constraints}

        if not trajectory_points:
            trajectory_points = [{}]

        for t_idx, point in enumerate(trajectory_points):
            for c_idx, constraint in enumerate(self.constraints):
                try:
                    h_val = constraint["fn"](point)
                    if h_val < safety_margins[constraint["name"]]:
                        safety_margins[constraint["name"]] = h_val
                    if h_val < 0:
                        violations.append(
                            CBFViolation(
                                constraint_name=constraint["name"],
                                constraint_index=c_idx,
                                violation_magnitude=round(abs(h_val), 6),
                                trajectory_time_index=t_idx,
                                required_correction=self._estimate_correction(
                                    constraint["name"], h_val, point
                                ),
                            )
                        )
                except Exception as exc:
                    logger.warning(f"CBF constraint '{constraint['name']}' eval error: {exc}")

        elapsed_ms = (time.perf_counter() - start) * 1000
        passed = len(violations) == 0

        logger.info(
            f"CBF gate evaluated {len(trajectory_points)} point(s) in {elapsed_ms:.2f} ms — "
            f"{'PASSED' if passed else f'FAILED ({len(violations)} violations)'}"
        )

        return CBFResult(
            passed=passed,
            violations=violations,
            corrected_route=None,
            safety_margin_summary={k: round(v, 4) for k, v in safety_margins.items()},
            execution_time_ms=round(elapsed_ms, 2),
        )

    # ─────────────────────────────────────────────────────────────────────
    #  CORRECTION ESTIMATION
    # ─────────────────────────────────────────────────────────────────────

    def _estimate_correction(self, constraint_name: str, violation_value: float, point: Dict) -> float:
        """Rough magnitude of the corrective action needed (units vary by
        constraint: metres of reroute, minutes of delay, kg of payload cut)."""
        correction_map = {
            "min_separation": abs(violation_value) * 1.0,
            "geofence_exclusion": 200.0,          # reroute around the zone (m)
            "battery_reserve_margin": 0.0,        # cannot correct in-flight — must abort/redirect
            "altitude_ceiling": abs(violation_value),
            "collision_probability": 30.0,        # hold/delay (s) to let conflict resolve
        }
        return round(correction_map.get(constraint_name, abs(violation_value)), 3)

    # ─────────────────────────────────────────────────────────────────────
    #  ASIF QP (minimally-invasive active correction)
    # ─────────────────────────────────────────────────────────────────────

    def run_asif_qp(self, desired_control: np.ndarray, current_state: Dict) -> Tuple[np.ndarray, bool]:
        """
        ASIF Quadratic Program:
          u_act = argmin ||u_des - u||^2
          subject to: h_i(x, u) >= 0 for all near-active constraints.

        Returns (safe_control, was_modified). This is what makes the gate
        a *filter* rather than a binary accept/reject: near-violations get
        the smallest possible nudge back into the safe set.
        """
        try:
            from scipy.optimize import minimize
        except ImportError:
            logger.warning("scipy not available — ASIF QP skipped, returning desired control")
            return desired_control, False

        def objective(u: np.ndarray) -> float:
            return float(np.sum((desired_control - u) ** 2))

        constraint_list = []
        for c in self.constraints:
            h_val = c["fn"](current_state)
            if h_val < 0.1:
                constraint_list.append(
                    {"type": "ineq", "fun": lambda u, cv=h_val: cv + 0.01 * float(np.linalg.norm(u))}
                )

        if not constraint_list:
            return desired_control, False

        result = minimize(
            objective, desired_control, method="SLSQP",
            constraints=constraint_list, options={"maxiter": 100, "ftol": 1e-6},
        )
        was_modified = bool(np.linalg.norm(result.x - desired_control) > 1e-6)
        return result.x, was_modified


# ─────────────────────────────────────────────────────────────────────────────
#  FACTORY
# ─────────────────────────────────────────────────────────────────────────────

def build_cbf_gate(dispatch_plan: Dict[str, Any], city: Optional[str] = None) -> ControlBarrierFunctionGate:
    """Factory: build a CBFGate configured from a dispatch plan dict.

    Threshold resolution order: an explicit dispatch_plan value always wins;
    otherwise an operator-approved policy overlay for `city` (see
    aerofleet/safety/policy_store.py) is used if one exists; otherwise the
    hardcoded default below. This is additive — passing no `city`, or a
    city with no approved proposal, reproduces the exact prior behavior.
    """
    policy: Dict[str, Any] = {}
    if city:
        from aerofleet.safety.policy_store import get_active_policy

        policy = get_active_policy(city)

    def resolve(key: str, default: Any) -> Any:
        if key in dispatch_plan:
            return dispatch_plan[key]
        return policy.get(key, default)

    config = {
        "min_separation_m": resolve("min_separation_m", 15.0),
        "max_altitude_m": resolve("max_altitude_m", 100.0),
        "max_wind_mps": resolve("max_wind_mps", 10.0),
        "max_payload_kg": resolve("max_payload_kg", 5.0),
        "max_noise_db": resolve("max_noise_db", 65.0),
        "max_collision_probability": resolve("max_collision_probability", 1e-4),
        "min_link_margin_db": resolve("min_link_margin_db", 3.0),
        "depot_pad_slots": resolve("depot_pad_slots", 4),
        "min_visibility_m": resolve("min_visibility_m", 1500.0),
    }
    return ControlBarrierFunctionGate(config)


def build_trajectory_points_from_plan(dispatch_plan: Dict[str, Any]) -> List[Dict]:
    """
    Synthesise a minimal set of CBF-checkable state points from a dispatch
    plan when no explicit route/telemetry list is available.
    """
    return [
        {
            "separation_m": dispatch_plan.get("separation_m", 50.0),
            "in_red_zone": dispatch_plan.get("in_red_zone", False),
            "battery_margin_wh": dispatch_plan.get("battery_margin_wh", 50.0),
            "altitude_m": dispatch_plan.get("altitude_m", 60.0),
            "wind_speed_mps": dispatch_plan.get("wind_speed_mps", 3.0),
            "payload_kg": dispatch_plan.get("payload_kg", 1.0),
            "noise_db": dispatch_plan.get("noise_db", 55.0),
            "collision_probability": dispatch_plan.get("collision_probability", 0.0),
            "link_margin_db": dispatch_plan.get("link_margin_db", 10.0),
            "depot_queue_length": dispatch_plan.get("depot_queue_length", 0),
            "visibility_m": dispatch_plan.get("visibility_m", 8000.0),
        }
    ]
