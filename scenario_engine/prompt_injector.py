"""
Prompt Injector — injects structured error context into agent retry prompts.

When a scenario fails, the evaluator generates a detailed error report.
The prompt injector appends this to the mission plan dict that gets passed
back to the council, ensuring agents are told EXACTLY what they got wrong
and what corrections are needed.
"""

import logging
from typing import Dict, Any

from scenario_engine.evaluator import EvaluationResult

logger = logging.getLogger(__name__)


def inject_correction(
    mission_plan: Dict[str, Any],
    eval_result: EvaluationResult,
    attempt_number: int,
) -> Dict[str, Any]:
    """
    Inject a structured error correction block into the mission plan dict.

    This dict is passed back to the CouncilOfExperts.run_grand_debate() on retry.
    The error block is visible to all agents as part of the mission context.

    Args:
        mission_plan: The original mission parameters dict
        eval_result: The EvaluationResult from the failed attempt
        attempt_number: Which retry attempt this is (1-indexed)

    Returns:
        A new mission plan dict with the correction block injected
    """
    corrected_plan = dict(mission_plan)

    error_report = eval_result.error_report_for_retry()
    if not error_report:
        return corrected_plan  # Nothing to inject (shouldn't happen)

    # Inject a special block that all agents will see
    corrected_plan["_scenario_correction"] = {
        "attempt": attempt_number,
        "failed_metrics": eval_result.failed_metrics,
        "pass_count": eval_result.pass_count,
        "total_count": eval_result.total_count,
        "error_report": error_report,
        "instruction": (
            f"ATTEMPT {attempt_number} FAILED. "
            f"Read the error report below carefully and correct ALL listed issues. "
            f"You must pass ALL {eval_result.total_count} metrics to complete this scenario."
        ),
    }

    logger.info(
        f"Correction injected for scenario {eval_result.scenario_id} "
        f"(attempt {attempt_number}): {eval_result.failed_metrics}"
    )

    return corrected_plan


def build_retry_system_prompt(
    base_system_prompt: str,
    eval_result: EvaluationResult,
    attempt_number: int,
) -> str:
    """
    Prepend a correction block to an agent's system prompt for retry attempts.

    Args:
        base_system_prompt: The agent's original system prompt
        eval_result: The EvaluationResult from the failed attempt
        attempt_number: Which retry attempt this is (1-indexed)

    Returns:
        Modified system prompt with corrections prepended
    """
    error_block = (
        f"\n\n{'='*60}\n"
        f"## 🔴 CORRECTION REQUIRED — ATTEMPT {attempt_number}\n"
        f"{'='*60}\n"
        f"{eval_result.error_report_for_retry()}\n"
        f"{'='*60}\n\n"
        "You MUST address all failures above before outputting your evaluation.\n"
        "Show all calculations using ReAct format:\n"
        "  Thought: [what you need to calculate]\n"
        "  Action: [formula/calculation]\n"
        "  Observation: [result]\n\n"
    )
    return error_block + base_system_prompt
