"""
Scenario Reporter — generates human-readable pass/fail reports during training runs.
"""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

from scenario_engine.schemas import Scenario
from scenario_engine.evaluator import EvaluationResult

logger = logging.getLogger(__name__)

_REPORTS_DIR = Path(__file__).parent.parent / "scenario_reports"


class ScenarioReporter:
    """
    Tracks and logs scenario run results during a training session.
    Writes a final report to scenario_reports/ after each full run.
    """

    def __init__(self):
        self._session_start = datetime.utcnow().isoformat()
        self._attempts: List[Dict[str, Any]] = []
        self._passes: List[str] = []
        self._exhausted: List[str] = []
        _REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    def record_attempt(
        self, scenario: Scenario, result: EvaluationResult, attempt: int
    ) -> None:
        self._attempts.append({
            "scenario_id": scenario.id,
            "attempt": attempt,
            "pass_count": result.pass_count,
            "total_count": result.total_count,
            "failed_metrics": result.failed_metrics,
        })

    def record_pass(
        self, scenario: Scenario, result: EvaluationResult, attempt: int
    ) -> None:
        self._passes.append(scenario.id)
        logger.info(
            f"  🏆 {scenario.id} PASSED in {attempt} attempt(s) — "
            f"{result.pass_count}/{result.total_count} metrics"
        )

    def record_exhausted(
        self, scenario: Scenario, last_result: Optional[EvaluationResult]
    ) -> None:
        self._exhausted.append(scenario.id)
        failed = last_result.failed_metrics if last_result else ["unknown"]
        logger.error(
            f"  💀 {scenario.id} EXHAUSTED retries. "
            f"Still failing: {failed}"
        )

    def print_summary(self, summary: Dict[str, Any]) -> None:
        """Print a training pass summary to the console."""
        lines = [
            f"\n{'='*60}",
            f"📊 TRAINING PASS {summary.get('run_pass', '?')} SUMMARY",
            f"{'='*60}",
            f"  Total Scenarios : {summary['total_scenarios']}",
            f"  Passed          : {summary['passed']} ✅",
            f"  Failed          : {summary['failed']} ❌",
            f"  Pass Rate       : {summary['pass_rate_pct']:.1f}%",
            f"{'='*60}\n",
        ]
        for line in lines:
            logger.info(line)

        # Write to file
        report_path = _REPORTS_DIR / f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.txt"
        try:
            with open(report_path, "w") as f:
                f.write("\n".join(lines))
                f.write(f"\nPassed IDs: {self._passes}\n")
                f.write(f"Exhausted IDs: {self._exhausted}\n")
            logger.info(f"  Report saved: {report_path}")
        except Exception as exc:
            logger.warning(f"Could not write report: {exc}")
