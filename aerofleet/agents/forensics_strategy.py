"""How the incident-forensics domain agents are prompted and decoded — one switch per
intervention, so each can be measured on its own (research/forensics_v2/).

Every switch targets a failure mode measured in the 1,000-case study
(research/real_llm_results.md):

  prompt_version="v1"   the original prompt + regex extractor, to reproduce the baseline exactly
  prompt_version="v2"   valid-JSON example, "another factor's constraint is not your evidence",
                        brace-balancing extractor, factor pinning            (parse failures, drift)
  structured_output     Ollama JSON-schema constrained decoding; the model reasons inside a
                        "reasoning" field, so chain-of-thought survives   (82% of misses = parsing)
  evidence_ownership    each violated constraint is listed with the factor it belongs to
                        (the system's own constraint schema, available at runtime)
                                                                   (61% of false alarms = cross-attribution)
  few_shot              worked examples built from a *training* split of generated cases
                        (never the evaluation cases)          (over-attribution on single-factor/control)
  temperature           0 for reproducible runs

Nothing here touches the dispatch path — the council only ever investigates a decision the CBF
gate has already made.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional, Tuple

from aerofleet.agents.incident_taxonomy import CONSTRAINT_TO_FACTOR

# The original domain task, kept verbatim so the baseline can be reproduced (commit 73f043c and earlier).
DOMAIN_ASSESSMENT_TASK_TEMPLATE_V1 = """
INCIDENT FORENSICS TASK — this is NOT a normal dispatch review. A decision
has ALREADY been made and is FINAL (either the CBF gate rejected a
dispatch, or a fault/emergency-landing occurred). Your job is retrospective
investigation, not a new recommendation.

You are assessing ONE factor: {description}

Respond with your normal Thought/Action/Observation/Verdict format, but end
with a fenced JSON block exactly in this shape:
```json
{{"factor": "{factor_name}", "contributed": "CONTRIBUTED" | "NOT_CONTRIBUTED" | "UNCERTAIN", "confidence": 0.0-1.0, "evidence": "cite the actual numbers from the incident context above"}}
```
Base "evidence" only on the numbers actually given to you in the incident
context — never invent a figure. If the incident context doesn't contain
enough information to assess your factor, use "UNCERTAIN" with a low
confidence and say what's missing, rather than guessing.
"""

STRUCTURED_TASK_SUFFIX = """
Answer with a single JSON object (the response format is enforced). Think step by step inside
"reasoning" first — which numbers belong to YOUR factor, and whether any of them is violated —
then give the verdict. "factor" must be exactly "{factor_name}".
"""


def domain_json_schema(factor_name: str) -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "reasoning": {"type": "string"},
            "factor": {"type": "string", "enum": [factor_name]},
            "contributed": {"type": "string", "enum": ["CONTRIBUTED", "NOT_CONTRIBUTED", "UNCERTAIN"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "evidence": {"type": "string"},
        },
        "required": ["reasoning", "factor", "contributed", "confidence", "evidence"],
    }


@dataclass(frozen=True)
class FewShotExample:
    factor: str
    margins: Dict[str, float]
    verdict: str
    evidence: str


@dataclass(frozen=True)
class ForensicsStrategy:
    name: str = "v2"
    prompt_version: str = "v2"             # "v1" | "v2"
    structured_output: bool = False
    evidence_ownership: bool = False
    few_shot: Tuple[FewShotExample, ...] = field(default_factory=tuple)
    temperature: Optional[float] = None    # None = backend default

    def with_(self, **changes) -> "ForensicsStrategy":
        return replace(self, **changes)

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "prompt_version": self.prompt_version, "structured_output": self.structured_output,
                "evidence_ownership": self.evidence_ownership, "few_shot_examples": len(self.few_shot),
                "temperature": self.temperature}


def evidence_ownership_block(frozen_context: Dict[str, Any]) -> str:
    """Which factor each CBF margin in the frozen context belongs to, and whether it is violated."""
    margins = ((frozen_context or {}).get("cbf_certificate") or {}).get("safety_margins") or {}
    if not margins:
        return "\nCONSTRAINT OWNERSHIP: no CBF margins were recorded for this incident.\n"
    lines = []
    for name, value in sorted(margins.items()):
        owner = CONSTRAINT_TO_FACTOR.get(name, "no domain factor")
        state = "VIOLATED" if isinstance(value, (int, float)) and value < 0 else "within limit"
        lines.append(f"  - {name} = {value} → {state} · belongs to: {owner}")
    return ("\nCONSTRAINT OWNERSHIP (from AeroFleet's CBF constraint schema — use it to decide which "
            "numbers are evidence for YOUR factor):\n" + "\n".join(lines) + "\n")


def few_shot_block(examples: Tuple[FewShotExample, ...], factor_name: str) -> str:
    mine = [e for e in examples if e.factor == factor_name]
    if not mine:
        return ""
    parts = ["\nWORKED EXAMPLES (other incidents, for calibration — not this one):"]
    for i, e in enumerate(mine, 1):
        parts.append(f"Example {i}: CBF margins {json.dumps(e.margins)}")
        parts.append("Answer: " + json.dumps({"factor": factor_name, "contributed": e.verdict, "evidence": e.evidence}))
    return "\n".join(parts) + "\n"


def from_env() -> ForensicsStrategy:
    """AEROFLEET_FORENSICS_STRATEGY: a JSON object of ForensicsStrategy fields (without few_shot),
    for switching the running backend's behaviour without code changes."""
    raw = os.environ.get("AEROFLEET_FORENSICS_STRATEGY")
    if not raw:
        return ForensicsStrategy()
    data = json.loads(raw)
    data.pop("few_shot", None)
    return ForensicsStrategy(**data)
