#!/usr/bin/env python3
"""Pre-flight check for a live (non-mocked) council demo against a real
Ollama server — run this BEFORE the actual demo, not during it.

This project's live LLM path (aerofleet/agents/local_agent.py) has never
once been exercised in this project's history — every prior verification
used USE_MOCK_AGENTS=true. This script is the first thing that should run
on new hardware (e.g. a college GPU machine) to catch problems — a missing
model, a wrong tag, a VRAM-too-small failure, an unreachable host — with a
clear error message, instead of discovering them mid-demo.

For each distinct model in aerofleet.agents.factory.AgentFactory
.DEFAULT_MODEL_MAP (env-var overrides via AGENT_MODEL_<ID> are also
respected, same resolution order the real app uses), this script:
  1. Confirms the model is present locally (`ollama list`) — if not,
     prints the exact `ollama pull <model>` command instead of pulling it
     automatically (pulls can be tens of GB; better to let you watch it
     and confirm disk/network budget yourself).
  2. Sends one minimal real chat completion and times it, so "the model is
     present" and "the model actually answers" are checked separately —
     a model can be pulled but still fail to run (OOM, corrupt pull, wrong
     quantization for the installed Ollama version).

Usage:
    python tools/preflight_llm_check.py [--host http://localhost:11434]
    OLLAMA_HOST=http://<tailscale-ip>:11434 python tools/preflight_llm_check.py
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Dict, List, Tuple

# Runs standalone, same as tools/mock_mavlink_vehicle.py — needs the repo
# root on sys.path when invoked as `python tools/preflight_llm_check.py`
# rather than `python -m tools.preflight_llm_check`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROBE_PROMPT = "Reply with exactly one word: OK"


def _required_models() -> Dict[str, List[str]]:
    """agent_id -> resolved model, inverted to model -> [agent_ids using it]
    so a model shared by several agents (e.g. phi4-mini-reasoning) is only
    checked once."""
    from aerofleet.agents.factory import AgentFactory

    model_to_agents: Dict[str, List[str]] = {}
    for agent_id in AgentFactory.DEFAULT_MODEL_MAP:
        model = AgentFactory._resolve_model(agent_id)
        model_to_agents.setdefault(model, []).append(agent_id)
    return model_to_agents


def _list_local_models(client) -> List[str]:
    resp = client.list()
    raw = getattr(resp, "models", None) or resp.get("models", [])
    return [getattr(m, "model", None) or m.get("name", "") for m in raw]


def _check_one_model(client, model: str, agents: List[str]) -> Tuple[bool, str]:
    label = f"{model:<28} (used by: {', '.join(agents)})"
    try:
        start = time.perf_counter()
        response = client.chat(
            model=model,
            messages=[{"role": "user", "content": PROBE_PROMPT}],
            options={"num_predict": 16},
        )
        elapsed = time.perf_counter() - start
        content = (
            response.message.content if hasattr(response, "message") else response["message"]["content"]
        )
        print(f"  [OK]   {label} — responded in {elapsed:.1f}s: {content.strip()[:60]!r}")
        return True, ""
    except Exception as exc:
        print(f"  [FAIL] {label}")
        print(f"         {type(exc).__name__}: {exc}")
        return False, str(exc)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default=os.environ.get("OLLAMA_HOST", "http://localhost:11434"))
    args = parser.parse_args()

    import ollama

    print(f"Connecting to Ollama at {args.host} ...")
    try:
        client = ollama.Client(host=args.host, timeout=15.0)
        local_models = _list_local_models(client)
    except Exception as exc:
        print(f"[FAIL] Could not reach Ollama at {args.host}: {exc}")
        print("       Is `ollama serve` running? Is the host/port correct?")
        return 1

    print(f"Connected. {len(local_models)} model(s) already present locally.\n")

    model_to_agents = _required_models()
    missing = [m for m in model_to_agents if not any(m in local or local.startswith(m) for local in local_models)]

    if missing:
        print(f"{len(missing)} required model(s) not found locally — pull these first:\n")
        for m in missing:
            print(f"    ollama pull {m}")
        print()

    present = [m for m in model_to_agents if m not in missing]
    print(f"Probing {len(present)} present model(s) with a real inference call:\n")

    results = [(_check_one_model(client, m, model_to_agents[m])) for m in present]
    n_ok = sum(1 for ok, _ in results if ok)

    print(f"\n{'=' * 60}")
    print(f"Result: {n_ok}/{len(present)} present models responded; {len(missing)} not yet pulled.")
    if missing or n_ok < len(present):
        print("NOT ready for a live demo yet — see failures/missing models above.")
        return 1
    print("All configured models are present and responding. Ready for a live demo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
