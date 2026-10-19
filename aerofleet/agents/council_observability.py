"""Council Observability — structured metrics for multi-agent council runs.

AeroFleet 2.0 exposes the council's internal deliberation as first-class
observable data, not buried in log files. Every council run produces:
  - Per-agent verdict and confidence
  - Pheromone weight evolution per debate round
  - Inter-agent agreement/disagreement score
  - Specialists triggered and why
  - Convergence curve (did the council reach consensus?)

This module is attached to CouncilOfExperts.run_grand_debate() output
and persisted alongside the compliance report in the mission record.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import time


@dataclass
class AgentVerdict:
    agent_id: str
    agent_name: str
    round_num: int
    verdict: str          # GREEN | YELLOW | RED
    confidence: float     # 0.0 – 1.0 parsed from agent output
    key_concern: str      # one-sentence summary
    pheromone_weight: float


@dataclass
class DebateRound:
    round_num: int
    agents_active: int
    verdicts: List[AgentVerdict]
    specialists_triggered: List[str]
    consensus_score: float   # 0 (no consensus) – 1 (full consensus)
    duration_s: float


@dataclass
class CouncilObservability:
    """Full observability record for one council run."""
    mission_id: str
    total_rounds: int
    total_agents: int
    specialists_triggered: List[str]
    rounds: List[DebateRound]
    final_consensus_score: float
    converged: bool
    inter_agent_disagreement_score: float  # 0 = all agree, 1 = max disagreement
    dominant_concern: str  # which concern drove the most pheromone growth
    total_llm_calls: int
    total_duration_s: float


def _parse_verdict(text: str) -> str:
    """Extract GREEN/YELLOW/RED verdict from agent ReAct output."""
    upper = text.upper()
    if "RED" in upper:
        return "RED"
    if "YELLOW" in upper:
        return "YELLOW"
    return "GREEN"


def _parse_confidence(text: str) -> float:
    """Estimate confidence from agent output (simple heuristic)."""
    if "uncertain" in text.lower() or "unclear" in text.lower():
        return 0.4
    if "high confidence" in text.lower() or "clearly" in text.lower():
        return 0.9
    return 0.7


def _consensus_score(verdicts: List[str]) -> float:
    """Compute consensus: 1.0 = all same, 0.0 = maximally split."""
    if not verdicts:
        return 1.0
    counts = {"GREEN": 0, "YELLOW": 0, "RED": 0}
    for v in verdicts:
        counts[v] = counts.get(v, 0) + 1
    majority = max(counts.values())
    return majority / len(verdicts)


def _disagreement_score(all_verdicts: List[str]) -> float:
    """1 - consensus across all rounds."""
    return round(1.0 - _consensus_score(all_verdicts), 3)


def extract_observability(
    mission_id: str,
    transcript: List[Dict[str, Any]],
    agent_weights_history: Optional[List[Dict[str, float]]] = None,
) -> CouncilObservability:
    """Extract structured observability data from a council debate transcript.

    Args:
        mission_id: The mission plan ID this council run is for
        transcript: The raw debate transcript from CouncilOfExperts.run_grand_debate()
        agent_weights_history: Optional list of pheromone weight dicts per round

    Returns:
        CouncilObservability with all metrics
    """
    rounds_data: Dict[int, List[Dict]] = {}
    specialists_triggered: List[str] = []
    total_llm_calls = 0

    for entry in transcript:
        phase = entry.get("phase", 0)
        role = entry.get("role", "")
        name = entry.get("name", "")
        text = entry.get("text", "")
        round_num = entry.get("round", phase)

        # Count LLM calls (agent responses, not system messages)
        if role == "AGENT":
            total_llm_calls += 1
            if round_num not in rounds_data:
                rounds_data[round_num] = []
            rounds_data[round_num].append({
                "agent_id": name.upper().replace(" ", "_"),
                "agent_name": name,
                "text": text,
                "round_num": round_num,
            })

        # Detect specialist triggers
        if "Specialist" in name or "Triggered" in text:
            if name not in specialists_triggered:
                specialists_triggered.append(name)

    # Build per-round data
    debate_rounds: List[DebateRound] = []
    all_verdicts_flat: List[str] = []

    for round_num in sorted(rounds_data.keys()):
        entries = rounds_data[round_num]
        verdicts_this_round: List[AgentVerdict] = []
        round_verdicts: List[str] = []

        weights = (agent_weights_history[round_num] if agent_weights_history and round_num < len(agent_weights_history) else {})

        for e in entries:
            verdict_str = _parse_verdict(e["text"])
            round_verdicts.append(verdict_str)
            all_verdicts_flat.append(verdict_str)

            key_concern = ""
            lines = e["text"].split("\n")
            for line in lines:
                if line.startswith("Verdict:") or line.startswith("VERDICT"):
                    key_concern = line[:120]
                    break
            if not key_concern and lines:
                key_concern = lines[-1][:120]

            verdicts_this_round.append(AgentVerdict(
                agent_id=e["agent_id"],
                agent_name=e["agent_name"],
                round_num=round_num,
                verdict=verdict_str,
                confidence=_parse_confidence(e["text"]),
                key_concern=key_concern,
                pheromone_weight=weights.get(e["agent_id"], 1.0),
            ))

        debate_rounds.append(DebateRound(
            round_num=round_num,
            agents_active=len(entries),
            verdicts=verdicts_this_round,
            specialists_triggered=[s for s in specialists_triggered if round_num > 0],
            consensus_score=round(_consensus_score(round_verdicts), 3),
            duration_s=0.0,  # populated from transcript timestamps if available
        ))

    final_consensus = debate_rounds[-1].consensus_score if debate_rounds else 1.0
    converged = final_consensus >= 0.8

    # Dominant concern: agent with most pheromone growth
    if agent_weights_history and len(agent_weights_history) > 1:
        first = agent_weights_history[0]
        last = agent_weights_history[-1]
        dominant = max(last.keys(), key=lambda k: last.get(k, 1.0) - first.get(k, 1.0), default="Unknown")
    else:
        dominant = "N/A"

    return CouncilObservability(
        mission_id=mission_id,
        total_rounds=len(debate_rounds),
        total_agents=max((len(r.verdicts) for r in debate_rounds), default=0),
        specialists_triggered=specialists_triggered,
        rounds=debate_rounds,
        final_consensus_score=final_consensus,
        converged=converged,
        inter_agent_disagreement_score=_disagreement_score(all_verdicts_flat),
        dominant_concern=dominant,
        total_llm_calls=total_llm_calls,
        total_duration_s=0.0,
    )
