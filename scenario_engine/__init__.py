"""
scenario_engine — Headless automated training pipeline for Space Mission Architect.

Runs 1000+ mission scenarios against the full agent pipeline, evaluates
accuracy on every dimension, retries failures with corrective prompts,
and persists all learnings to agent_memory (ChromaDB).

Usage:
    # Run all historical scenarios
    python -m scenario_engine.runner --type historical

    # Run all scenarios (headless, continuous until all pass)
    python -m scenario_engine.runner --type all --continuous

    # Run a specific scenario by ID
    python -m scenario_engine.runner --id HIST-001
"""
