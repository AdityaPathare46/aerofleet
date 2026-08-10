"""
Persistent memory record schemas for agent episodic memory.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum


class MemoryOutcome(str, Enum):
    """Outcome of a scenario attempt stored in memory."""
    FAILURE = "FAILURE"
    PASS = "PASS"
    CORRECTION = "CORRECTION"  # A failure that was subsequently corrected


@dataclass
class MemoryRecord:
    """
    A single episodic memory record for an agent.

    Stored in ChromaDB as a document (text) + metadata dict.
    The document text is what gets semantically searched at retrieval time.
    """
    agent_id: str               # e.g. "orbital_dynamics", "propulsion_manager"
    scenario_id: str            # e.g. "HIST-001", "SYN-042"
    scenario_name: str          # Human-readable scenario name
    outcome: MemoryOutcome      # FAILURE, PASS, CORRECTION
    error_types: List[str]      # e.g. ["delta_v_underestimate", "cbf_violation"]
    error_details: str          # Detailed description of what went wrong
    correction_applied: str     # What was injected in the retry prompt that fixed it
    mission_parameters: Dict[str, Any]  # The scenario's input parameters
    metrics_delta: Dict[str, float]     # { "delta_v_error_pct": 8.3, ... }
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    attempt_number: int = 0
    chroma_id: Optional[str] = None     # Set after insertion

    def to_document_text(self) -> str:
        """
        Generate the text document that ChromaDB will embed and search.

        This surfaces the key facts so semantic retrieval works well.
        """
        return (
            f"Agent: {self.agent_id}. "
            f"Scenario: {self.scenario_name} ({self.scenario_id}). "
            f"Outcome: {self.outcome.value}. "
            f"Errors: {', '.join(self.error_types)}. "
            f"Detail: {self.error_details}. "
            f"Correction: {self.correction_applied}."
        )

    def to_chroma_metadata(self) -> Dict[str, Any]:
        """Return ChromaDB-compatible metadata dict (primitive values only)."""
        return {
            "agent_id": self.agent_id,
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "outcome": self.outcome.value,
            "error_types": ",".join(self.error_types),
            "correction_applied": self.correction_applied,
            "timestamp": self.timestamp,
            "attempt_number": self.attempt_number,
        }
