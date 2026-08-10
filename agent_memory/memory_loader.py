"""
Memory Loader — injects relevant past learnings into agent context at startup.

Called by BaseAgent.__init__() so every agent begins each debate or scenario
run already aware of past corrections relevant to the current situation.
"""

import logging
from typing import Dict, Any, List, Optional

from agent_memory.memory_store import get_memory_store

logger = logging.getLogger(__name__)


def build_memory_context(
    agent_id: str,
    mission_parameters: Dict[str, Any],
    top_k: int = 5,
) -> str:
    """
    Build a memory context string to prepend to an agent's system prompt.

    Retrieves the top-K most semantically relevant past memories for this
    agent and formats them as explicit lessons to inject into the LLM call.

    Args:
        agent_id: The agent's domain identifier (e.g. "orbital_dynamics")
        mission_parameters: Current mission dict — used as the search query
        top_k: Max number of past memories to inject

    Returns:
        A formatted string ready to be prepended to the system prompt,
        or an empty string if no relevant memories exist.
    """
    store = get_memory_store()
    if not store.is_available:
        return ""

    # Build a natural-language query from the mission parameters
    query = _build_query(agent_id, mission_parameters)

    memories = store.retrieve_relevant(
        agent_id=agent_id,
        query=query,
        top_k=top_k,
    )

    if not memories:
        return ""

    # Format memories into clear lesson blocks
    lines = [
        "## PAST LEARNINGS (from previous scenario runs — apply these corrections now)\n"
    ]
    for i, mem in enumerate(memories, 1):
        meta = mem.get("metadata", {})
        outcome = meta.get("outcome", "?")
        correction = meta.get("correction_applied", "No correction recorded.")
        scenario = meta.get("scenario_name", meta.get("scenario_id", "unknown"))
        errors = meta.get("error_types", "")

        icon = "❌" if outcome == "FAILURE" else "✅"
        lines.append(
            f"{icon} **Lesson {i}** (Scenario: {scenario}):\n"
            f"   Errors made: {errors}\n"
            f"   Correction: {correction}\n"
        )

    lines.append(
        "Apply the above lessons proactively. Do NOT repeat these mistakes.\n"
    )
    context = "\n".join(lines)

    logger.debug(
        f"Memory context built for agent '{agent_id}': "
        f"{len(memories)} memories injected."
    )
    return context


def _build_query(agent_id: str, mission_parameters: Dict[str, Any]) -> str:
    """
    Convert mission parameters into a natural-language memory query.

    Focuses on the most search-relevant fields to get good semantic matches.
    """
    parts = [f"agent {agent_id}"]

    if "mission_type" in mission_parameters:
        parts.append(mission_parameters["mission_type"])
    if "target" in mission_parameters:
        parts.append(f"target {mission_parameters['target']}")
    if "payload_mass_kg" in mission_parameters:
        parts.append(f"payload {mission_parameters['payload_mass_kg']} kg")
    if "orbit_altitude_km" in mission_parameters:
        parts.append(f"orbit {mission_parameters['orbit_altitude_km']} km")
    if "launch_vehicle" in mission_parameters:
        parts.append(mission_parameters["launch_vehicle"])

    return " ".join(parts)


def get_agent_memory_summary(agent_id: str) -> Dict[str, Any]:
    """
    Return a summary of what an agent has learned — useful for diagnostics.

    Args:
        agent_id: The agent's identifier

    Returns:
        Dict with total records, recent errors, and top corrections
    """
    store = get_memory_store()
    if not store.is_available:
        return {"agent_id": agent_id, "available": False, "total_records": 0}

    all_records = store.retrieve_all_for_agent(agent_id)
    failures = [r for r in all_records if r.get("type") == "failure"]
    successes = [r for r in all_records if r.get("type") == "success"]

    # Extract most common error types
    error_counts: Dict[str, int] = {}
    for rec in failures:
        for err in rec.get("metadata", {}).get("error_types", "").split(","):
            err = err.strip()
            if err:
                error_counts[err] = error_counts.get(err, 0) + 1

    top_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "agent_id": agent_id,
        "available": True,
        "total_records": len(all_records),
        "total_failures": len(failures),
        "total_successes": len(successes),
        "top_error_types": [{"error": e, "count": c} for e, c in top_errors],
    }
