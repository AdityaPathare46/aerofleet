"""
Dry-run verification script for the v3.0 modules.

Tests:
1. scenario_engine — can load YAML scenario files
2. agent_memory — can initialize ChromaDB store
3. scenario_engine.evaluator — basic check runs without errors

Run from the project root:
    python verify_v3.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("Space Mission Architect v3.0 — Module Verification")
print("=" * 60)

# ── 1. Test Scenario Registry ──────────────────────────────────────────
print("\n[1] Testing scenario_engine.registry...")
try:
    from scenario_engine.registry import ScenarioRegistry
    registry = ScenarioRegistry()
    summary = registry.summary()
    print(f"    ✅ Registry loaded: {summary}")
except Exception as e:
    print(f"    ❌ Registry failed: {e}")

# ── 2. Test Scenario Schema Parsing ───────────────────────────────────
print("\n[2] Testing scenario YAML parsing...")
try:
    from scenario_engine.schemas import scenario_from_dict, ScenarioType
    test_data = {
        "id": "TEST-001",
        "name": "Verification Test",
        "type": "synthetic",
        "source": "test",
        "description": "Quick test",
        "parameters": {"mission_type": "test", "target": "Mars"},
        "expected_outputs": {
            "delta_v_ms": 6000,
            "cbf_all_pass": True,
            "legal_compliant": True,
        },
        "tags": ["test"],
        "difficulty": "baseline",
    }
    sc = scenario_from_dict(test_data)
    print(f"    ✅ Scenario parsed: {sc.id} — {sc.name}")
except Exception as e:
    print(f"    ❌ Schema parsing failed: {e}")

# ── 3. Test Evaluator ──────────────────────────────────────────────────
print("\n[3] Testing scenario_engine.evaluator...")
try:
    from scenario_engine.evaluator import ScenarioEvaluator
    evaluator = ScenarioEvaluator()
    agent_output = {
        "delta_v_ms": 6000,
        "cbf_all_pass": True,
        "legal_compliant": True,
        "safety_flags": ["nominal"],
    }
    result = evaluator.evaluate(sc, agent_output)
    print(f"    ✅ Evaluator ran: {result.pass_count}/{result.total_count} metrics passed")
except Exception as e:
    print(f"    ❌ Evaluator failed: {e}")

# ── 4. Test Agent Memory Store ─────────────────────────────────────────
print("\n[4] Testing agent_memory.memory_store...")
try:
    from agent_memory.memory_store import AgentMemoryStore
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmpdir:
        store = AgentMemoryStore(persist_path=Path(tmpdir))
        stats = store.get_stats()
        print(f"    ✅ Memory store initialized: {stats}")
except ImportError as e:
    print(f"    ⚠️  chromadb not installed in this environment: {e}")
    print(f"       Run: pip install chromadb  (in your venv)")
except Exception as e:
    print(f"    ❌ Memory store failed: {e}")

# ── 5. Test Memory Loader ──────────────────────────────────────────────
print("\n[5] Testing agent_memory.memory_loader...")
try:
    from agent_memory.memory_loader import build_memory_context, _build_query
    query = _build_query("orbital_dynamics", {"mission_type": "mars_orbiter", "target": "Mars"})
    print(f"    ✅ Memory query built: '{query}'")
    ctx = build_memory_context("orbital_dynamics", {"mission_type": "test"})
    print(f"    ✅ Memory context built: {len(ctx)} chars")
except ImportError as e:
    print(f"    ⚠️  chromadb not installed: {e}")
except Exception as e:
    print(f"    ❌ Memory loader failed: {e}")

# ── 6. Test Prompt Injector ────────────────────────────────────────────
print("\n[6] Testing scenario_engine.prompt_injector...")
try:
    from scenario_engine.prompt_injector import inject_correction
    from scenario_engine.evaluator import EvaluationResult
    mock_result = EvaluationResult(
        scenario_id="TEST-001",
        scenario_name="Test",
        all_pass=False,
        failed_metrics=["Delta-V (m/s)"],
        pass_count=9,
        total_count=10,
    )
    corrected_plan = inject_correction({"target": "Mars"}, mock_result, attempt_number=1)
    assert "_scenario_correction" in corrected_plan
    print(f"    ✅ Correction injected successfully")
except Exception as e:
    print(f"    ❌ Prompt injector failed: {e}")

print("\n" + "=" * 60)
print("Verification complete.")
print("=" * 60)
