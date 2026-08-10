"""
Scenario Evaluator — checks council/agent output against expected outputs
on ALL dimensions for a drone-dispatch scenario.

Target: 100% accuracy on every metric. Each metric has a configurable tolerance
that can be tightened toward 0 over time as agents improve.

Dimensions checked:
  1. ETA accuracy
  2. Battery margin
  3. Delivery cost estimate
  4. Peak noise level
  5. Communication link margin
  6. CBF safety gate (all constraints pass)
  7. DGCA regulatory compliance
  8. Safety flags (no unexpected anomalies)
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from scenario_engine.schemas import Scenario, ExpectedOutputs

logger = logging.getLogger(__name__)


@dataclass
class MetricResult:
    """Result of checking a single evaluation metric."""
    name: str
    passed: bool
    expected: Optional[float]
    actual: Optional[float]
    tolerance: Optional[float]
    error_pct: Optional[float]
    message: str


@dataclass
class EvaluationResult:
    """Complete evaluation result for one agent pipeline run against a scenario."""
    scenario_id: str
    scenario_name: str
    all_pass: bool
    metrics: List[MetricResult] = field(default_factory=list)
    failed_metrics: List[str] = field(default_factory=list)
    pass_count: int = 0
    total_count: int = 0

    def summary_text(self) -> str:
        """Generate human-readable summary for logging and error injection."""
        lines = [
            f"Scenario: {self.scenario_name} ({self.scenario_id})",
            f"Result: {'✅ ALL PASS' if self.all_pass else '❌ FAILED'}",
            f"Score: {self.pass_count}/{self.total_count} metrics passed",
        ]
        if self.failed_metrics:
            lines.append(f"Failed metrics: {', '.join(self.failed_metrics)}")
        for m in self.metrics:
            icon = "✅" if m.passed else "❌"
            lines.append(f"  {icon} {m.name}: {m.message}")
        return "\n".join(lines)

    def error_report_for_retry(self) -> str:
        """
        Generate a targeted error report to inject into the agent retry prompt.

        This is what the agent reads when retrying — it explains EXACTLY what
        was wrong and what corrections are needed.
        """
        if self.all_pass:
            return ""

        lines = [
            "## ⚠️ PREVIOUS ATTEMPT FAILED — CORRECTIONS REQUIRED\n",
            f"Scenario: {self.scenario_name}\n",
            "The following metrics were INCORRECT in your previous output:",
        ]
        for m in self.metrics:
            if not m.passed:
                error_str = f"{m.error_pct:.2f}%" if m.error_pct is not None else "N/A (not output)"
                lines.append(
                    f"\n### ❌ {m.name}\n"
                    f"  - Expected: {m.expected}\n"
                    f"  - You output: {m.actual}\n"
                    f"  - Error: {error_str} (tolerance: ±{m.tolerance}%)\n"
                    f"  - Fix: {m.message}"
                )
        lines.append(
            "\n**You MUST correct ALL of the above before outputting your answer. "
            "Show your calculations explicitly (ReAct format: Thought → Action → Observation).**"
        )
        return "\n".join(lines)


class ScenarioEvaluator:
    """
    Evaluates agent pipeline output against scenario ground truth.

    Instantiate once and call evaluate() for each run.
    """

    def evaluate(
        self,
        scenario: Scenario,
        agent_output: Dict[str, Any],
    ) -> EvaluationResult:
        """
        Run all metric checks and return a complete EvaluationResult.

        Args:
            scenario: The scenario being tested (contains expected outputs)
            agent_output: The raw dict output from the agent council pipeline

        Returns:
            EvaluationResult with pass/fail for each dimension
        """
        exp = scenario.expected
        metrics: List[MetricResult] = []

        # 1. ETA
        if exp.eta_minutes is not None:
            metrics.append(self._check_numeric(
                name="ETA (minutes)",
                expected=exp.eta_minutes,
                actual=self._extract(agent_output, ["eta_minutes", "eta_min"]),
                tolerance_pct=exp.eta_tolerance_pct,
                fix_hint=(
                    f"Your ETA is wrong. Expected ~{exp.eta_minutes} min. "
                    "Recalculate as distance_km / avg_speed_kmh * 60, using the route distance "
                    "over the city street graph, not straight-line distance."
                ),
            ))

        # 2. Battery Margin
        if exp.battery_margin_wh is not None:
            metrics.append(self._check_absolute(
                name="Battery Margin (Wh)",
                expected=exp.battery_margin_wh,
                actual=self._extract(agent_output, ["battery_margin_wh", "margin_wh"]),
                tolerance_abs=exp.battery_margin_tolerance_wh,
                fix_hint=(
                    f"Expected battery margin: ~{exp.battery_margin_wh} Wh. "
                    "Recompute: usable_wh - reserve_wh - (distance_km * wh_per_km * "
                    "(1 + payload_factor * payload_kg)) for the full round trip."
                ),
            ))

        # 3. Cost
        if exp.cost_usd is not None:
            metrics.append(self._check_numeric(
                name="Delivery Cost (USD)",
                expected=exp.cost_usd,
                actual=self._extract(agent_output, ["cost_usd", "estimated_cost_usd", "total_cost_usd"]),
                tolerance_pct=exp.cost_tolerance_pct,
                fix_hint=(
                    f"Expected cost: ~${exp.cost_usd}. "
                    "Break down: energy cost, drone amortisation per km, fixed depot ops cost."
                ),
            ))

        # 4. Peak Noise
        if exp.peak_noise_db is not None:
            metrics.append(self._check_absolute(
                name="Peak Noise (dB)",
                expected=exp.peak_noise_db,
                actual=self._extract(agent_output, ["peak_noise_db", "noise_db"]),
                tolerance_abs=exp.noise_tolerance_db,
                fix_hint=(
                    f"Expected peak noise: ~{exp.peak_noise_db} dB at ground level. "
                    "Check the altitude-band assignment — lower bands are louder at ground level."
                ),
            ))

        # 5. Comm Link Margin
        if exp.comm_link_margin_db is not None:
            metrics.append(self._check_absolute(
                name="Comm Link Margin (dB)",
                expected=exp.comm_link_margin_db,
                actual=self._extract(agent_output, ["comm_link_margin_db", "link_margin_db", "comm_margin_db", "link_budget_db"]),
                tolerance_abs=exp.comm_tolerance_db,
                fix_hint=(
                    f"Expected link margin: ≥{exp.comm_link_margin_db} dB. "
                    "Calculate Friis transmission equation: "
                    "Pr = Pt + Gt + Gr - FSPL - losses. Margin = Pr - Sensitivity."
                ),
            ))

        # 6. CBF All Pass
        cbf_actual = self._extract_bool(agent_output, ["cbf_all_pass", "safety_gate_pass", "cbf_pass"])
        metrics.append(MetricResult(
            name="CBF Safety Gate",
            passed=(cbf_actual is True) == exp.cbf_all_pass,
            expected=float(exp.cbf_all_pass),
            actual=float(cbf_actual) if cbf_actual is not None else None,
            tolerance=0,
            error_pct=None,
            message=(
                "CBF safety gate passed." if cbf_actual
                else "❌ CBF constraints violated — one or more safety conditions failed. "
                     "Review h_i(x) >= 0 for all constraints and fix the violating dispatch plan."
            ),
        ))

        # 7. DGCA Compliance
        dgca_actual = self._extract_bool(agent_output, ["dgca_compliant", "regulatory_compliant", "compliant"])
        metrics.append(MetricResult(
            name="DGCA Compliance",
            passed=(dgca_actual is True) == exp.dgca_compliant,
            expected=float(exp.dgca_compliant),
            actual=float(dgca_actual) if dgca_actual is not None else None,
            tolerance=0,
            error_pct=None,
            message=(
                "DGCA compliance verified." if dgca_actual
                else "❌ DGCA compliance failed — check zone colour, UIN/UAOP registration, altitude ceiling."
            ),
        ))

        # 8. Safety Flags
        actual_flags = agent_output.get("safety_flags", [])
        expected_flags = exp.safety_flags
        flags_pass = set(actual_flags) == set(expected_flags)
        metrics.append(MetricResult(
            name="Safety Flags",
            passed=flags_pass,
            expected=None,
            actual=None,
            tolerance=None,
            error_pct=None,
            message=(
                f"Safety flags match: {actual_flags}"
                if flags_pass
                else f"❌ Flag mismatch. Expected: {expected_flags}, Got: {actual_flags}"
            ),
        ))

        # Aggregate
        failed = [m.name for m in metrics if not m.passed]
        result = EvaluationResult(
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            all_pass=len(failed) == 0,
            metrics=metrics,
            failed_metrics=failed,
            pass_count=sum(1 for m in metrics if m.passed),
            total_count=len(metrics),
        )

        if result.all_pass:
            logger.info(f"✅ PASS: {scenario.id} — {scenario.name}")
        else:
            logger.warning(
                f"❌ FAIL: {scenario.id} — {scenario.name} | "
                f"Failed: {failed}"
            )

        return result

    # ─────────────────────────────────────────────────────────────────────
    #  METRIC HELPERS
    # ─────────────────────────────────────────────────────────────────────

    def _check_numeric(
        self,
        name: str,
        expected: float,
        actual: Optional[float],
        tolerance_pct: float,
        fix_hint: str,
    ) -> MetricResult:
        """Check a numeric metric within a percentage tolerance band."""
        if actual is None:
            return MetricResult(
                name=name, passed=False, expected=expected, actual=None,
                tolerance=tolerance_pct, error_pct=None,
                message=f"❌ Agent did not output '{name}'. {fix_hint}",
            )
        error_pct = abs(actual - expected) / expected * 100 if expected != 0 else 0
        passed = error_pct <= tolerance_pct
        return MetricResult(
            name=name,
            passed=passed,
            expected=expected,
            actual=actual,
            tolerance=tolerance_pct,
            error_pct=error_pct,
            message=(
                f"Within tolerance ({error_pct:.2f}% ≤ {tolerance_pct}%)" if passed
                else f"❌ {error_pct:.2f}% error exceeds {tolerance_pct}% tolerance. {fix_hint}"
            ),
        )

    def _check_absolute(
        self,
        name: str,
        expected: float,
        actual: Optional[float],
        tolerance_abs: float,
        fix_hint: str,
    ) -> MetricResult:
        """Check a metric within an absolute tolerance band."""
        if actual is None:
            return MetricResult(
                name=name, passed=False, expected=expected, actual=None,
                tolerance=tolerance_abs, error_pct=None,
                message=f"❌ Agent did not output '{name}'. {fix_hint}",
            )
        diff = abs(actual - expected)
        passed = diff <= tolerance_abs
        error_pct = diff / expected * 100 if expected != 0 else 0
        return MetricResult(
            name=name,
            passed=passed,
            expected=expected,
            actual=actual,
            tolerance=tolerance_abs,
            error_pct=error_pct,
            message=(
                f"Within tolerance (|{actual:.1f} - {expected:.1f}| = {diff:.2f} ≤ {tolerance_abs})"
                if passed
                else f"❌ Absolute error {diff:.2f} exceeds tolerance {tolerance_abs}. {fix_hint}"
            ),
        )

    @staticmethod
    def _extract(output: Dict[str, Any], keys: List[str]) -> Optional[float]:
        """Try to extract a numeric value from the agent output by trying multiple key names."""
        for key in keys:
            val = output.get(key)
            if val is not None:
                try:
                    return float(val)
                except (TypeError, ValueError):
                    continue
        return None

    @staticmethod
    def _extract_bool(output: Dict[str, Any], keys: List[str]) -> Optional[bool]:
        """Try to extract a boolean value from the agent output."""
        for key in keys:
            val = output.get(key)
            if val is not None:
                return bool(val)
        return None
