"""
Scenario Runner — headless, fully automated training loop.

Runs all scenarios against the agent pipeline, evaluates each output,
retries failures with corrective prompts, and persists learnings to ChromaDB.

Usage:
    # Run all scenarios continuously until all pass
    python -m scenario_engine.runner --type all --continuous

    # Run historical scenarios only
    python -m scenario_engine.runner --type historical

    # Run a specific scenario by ID
    python -m scenario_engine.runner --id HIST-001

    # Dry-run (no LLM calls, just load and validate scenario files)
    python -m scenario_engine.runner --dry-run
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

from scenario_engine.registry import ScenarioRegistry
from scenario_engine.schemas import Scenario, ScenarioType
from scenario_engine.evaluator import ScenarioEvaluator, EvaluationResult
from scenario_engine.prompt_injector import inject_correction
from scenario_engine.reporter import ScenarioReporter
from agent_memory.memory_store import get_memory_store
from agent_memory.schemas import MemoryRecord, MemoryOutcome

logger = logging.getLogger(__name__)


class ScenarioRunner:
    """
    Headless scenario training engine.

    For each scenario:
      1. Call the agent council pipeline with the scenario parameters
      2. Evaluate the output against expected values
      3. If FAIL: inject correction into mission plan and retry
      4. Persist all learnings (failures + successes) to ChromaDB
      5. Log progress to the reporter
    """

    def __init__(
        self,
        registry: Optional[ScenarioRegistry] = None,
        dry_run: bool = False,
    ):
        self.registry = registry or ScenarioRegistry()
        self.evaluator = ScenarioEvaluator()
        self.reporter = ScenarioReporter()
        self.memory = get_memory_store()
        self.dry_run = dry_run

        if not dry_run:
            self._init_council()

    def _init_council(self) -> None:
        """Initialize the council pipeline (lazy import to avoid startup cost)."""
        try:
            from aerofleet.agents.council import CouncilOfExperts
            self._council = CouncilOfExperts()
            logger.info("CouncilOfExperts initialized for scenario runner.")
        except Exception as exc:
            logger.error(f"Could not initialize CouncilOfExperts: {exc}")
            self._council = None

    # ─────────────────────────────────────────────────────────────────────
    #  PUBLIC API
    # ─────────────────────────────────────────────────────────────────────

    def run_scenario(self, scenario: Scenario) -> EvaluationResult:
        """
        Run a single scenario to completion (pass or max retries reached).

        Args:
            scenario: The scenario to run

        Returns:
            Final EvaluationResult (may be FAIL if max retries exceeded)
        """
        logger.info(
            f"\n{'='*60}\n"
            f"▶ SCENARIO: {scenario.id} — {scenario.name}\n"
            f"  Type: {scenario.scenario_type.value} | "
            f"Difficulty: {scenario.difficulty.value}\n"
            f"{'='*60}"
        )

        if self.dry_run:
            logger.info(f"[DRY RUN] Scenario {scenario.id} validated OK.")
            return EvaluationResult(
                scenario_id=scenario.id,
                scenario_name=scenario.name,
                all_pass=True,
                pass_count=10,
                total_count=10,
            )

        if self._council is None:
            logger.error("Council not available — skipping scenario.")
            return EvaluationResult(
                scenario_id=scenario.id,
                scenario_name=scenario.name,
                all_pass=False,
                failed_metrics=["council_unavailable"],
            )

        mission_plan = dict(scenario.parameters)
        last_result: Optional[EvaluationResult] = None

        for attempt in range(1, scenario.max_retries + 1):
            logger.info(f"  Attempt {attempt}/{scenario.max_retries}...")
            start_time = time.time()

            # Run the agent council
            try:
                agent_output = self._run_pipeline(mission_plan)
            except Exception as exc:
                logger.error(f"  Pipeline error on attempt {attempt}: {exc}")
                agent_output = {}

            elapsed = time.time() - start_time

            # Evaluate
            result = self.evaluator.evaluate(scenario, agent_output)
            last_result = result

            logger.info(
                f"  Attempt {attempt}: {result.pass_count}/{result.total_count} "
                f"metrics passed ({elapsed:.1f}s)"
            )

            if result.all_pass:
                # ── SUCCESS ──────────────────────────────────────────────
                self._store_success(scenario, result, agent_output, attempt)
                self.reporter.record_pass(scenario, result, attempt)
                logger.info(f"  ✅ PASSED on attempt {attempt}")
                return result
            else:
                # ── FAILURE → inject corrections for next attempt ────────
                self._store_failure(scenario, result, agent_output, attempt)
                self.reporter.record_attempt(scenario, result, attempt)

                if attempt < scenario.max_retries:
                    mission_plan = inject_correction(mission_plan, result, attempt)
                    logger.info(
                        f"  ❌ FAILED — injecting corrections for attempt {attempt + 1}. "
                        f"Failed: {result.failed_metrics}"
                    )

        # Max retries exceeded
        logger.error(
            f"  💀 EXHAUSTED {scenario.max_retries} attempts for {scenario.id}. "
            f"Last state: {last_result.failed_metrics if last_result else 'unknown'}"
        )
        self.reporter.record_exhausted(scenario, last_result)
        return last_result

    def run_all(
        self,
        scenario_type: Optional[ScenarioType] = None,
        tags: Optional[List[str]] = None,
        continuous: bool = False,
    ) -> Dict[str, Any]:
        """
        Run all (or filtered) scenarios.

        Args:
            scenario_type: Filter by type (historical/synthetic/edge_case)
            tags: Filter by tags
            continuous: If True, keep re-running until all pass

        Returns:
            Summary dict with pass/fail counts
        """
        scenarios = self.registry.get_all()
        if scenario_type:
            scenarios = [s for s in scenarios if s.scenario_type == scenario_type]
        if tags:
            scenarios = [s for s in scenarios if any(t in s.tags for t in tags)]

        logger.info(
            f"\n🚀 Starting scenario run: {len(scenarios)} scenarios "
            f"({'continuous' if continuous else 'single pass'})\n"
        )

        run_count = 0
        while True:
            run_count += 1
            if continuous:
                logger.info(f"\n--- TRAINING PASS {run_count} ---")

            results = {}
            passed = 0
            failed = 0

            for scenario in scenarios:
                result = self.run_scenario(scenario)
                results[scenario.id] = result
                if result.all_pass:
                    passed += 1
                else:
                    failed += 1

            summary = {
                "run_pass": run_count,
                "total_scenarios": len(scenarios),
                "passed": passed,
                "failed": failed,
                "pass_rate_pct": passed / len(scenarios) * 100 if scenarios else 0,
            }
            self.reporter.print_summary(summary)

            if not continuous or failed == 0:
                break

            logger.info(
                f"\n🔄 {failed} scenarios still failing — starting training pass {run_count + 1}...\n"
            )

        return summary

    # ─────────────────────────────────────────────────────────────────────
    #  PRIVATE HELPERS
    # ─────────────────────────────────────────────────────────────────────

    def _run_pipeline(self, mission_plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call the CouncilOfExperts pipeline and return a structured output dict.

        The council returns (final_plan, transcript). We use final_plan.
        """
        final_plan, _transcript = self._council.run_grand_debate(mission_plan)
        return final_plan if isinstance(final_plan, dict) else {}

    def _store_failure(
        self,
        scenario: Scenario,
        result: EvaluationResult,
        agent_output: Dict[str, Any],
        attempt: int,
    ) -> None:
        """Persist a failure record to ChromaDB memory."""
        if not self.memory.is_available:
            return
        # Store one record per failing agent domain (approximated by metric)
        record = MemoryRecord(
            agent_id="council",  # Will be refined per-agent in future
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            outcome=MemoryOutcome.FAILURE,
            error_types=result.failed_metrics,
            error_details=result.summary_text(),
            correction_applied=result.error_report_for_retry(),
            mission_parameters=scenario.parameters,
            metrics_delta={
                m.name: m.error_pct or 0
                for m in result.metrics if not m.passed and m.error_pct is not None
            },
            attempt_number=attempt,
        )
        self.memory.record_failure(record)

    def _store_success(
        self,
        scenario: Scenario,
        result: EvaluationResult,
        agent_output: Dict[str, Any],
        attempt: int,
    ) -> None:
        """Persist a success record to ChromaDB memory."""
        if not self.memory.is_available:
            return
        record = MemoryRecord(
            agent_id="council",
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            outcome=MemoryOutcome.PASS,
            error_types=[],
            error_details="All metrics passed.",
            correction_applied="n/a",
            mission_parameters=scenario.parameters,
            metrics_delta={},
            attempt_number=attempt,
        )
        self.memory.record_success(record)


# ─────────────────────────────────────────────────────────────────────────────
#  CLI ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args():
    parser = argparse.ArgumentParser(
        description="AeroFleet — Headless Scenario Training Runner"
    )
    parser.add_argument(
        "--type",
        choices=["all", "historical", "synthetic", "edge_case"],
        default="all",
        help="Filter scenarios by type (default: all)",
    )
    parser.add_argument("--id", help="Run a specific scenario by ID")
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Keep re-running failed scenarios until all pass",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate scenario files without running the agent pipeline",
    )
    parser.add_argument(
        "--tags",
        nargs="+",
        help="Filter scenarios by tags (e.g. --tags lunar crewed)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    runner = ScenarioRunner(dry_run=args.dry_run)

    if args.id:
        scenario = runner.registry.get_by_id(args.id)
        if scenario is None:
            logger.error(f"Scenario '{args.id}' not found.")
            sys.exit(1)
        result = runner.run_scenario(scenario)
        sys.exit(0 if result.all_pass else 1)
    else:
        scenario_type = ScenarioType(args.type) if args.type != "all" else None
        summary = runner.run_all(
            scenario_type=scenario_type,
            tags=args.tags,
            continuous=args.continuous,
        )
        sys.exit(0 if summary["failed"] == 0 else 1)
