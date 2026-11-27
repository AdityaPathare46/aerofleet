"""Proof that no AI model is in AeroFleet 2.0's decision path.

Follows every import (including imports inside functions) from the product's entry points, through the whole
aerofleet package, and fails if the product can reach the earlier prototype's AI agents, the language-model review
panel kept for the paper's experiment (aerofleet/assurance/review_panel.py), or any machine-learning or
language-model library. Static, so it also covers code paths no other test happens to run.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "aerofleet"
ENTRY = [ROOT / "aerofleet/api/routes/assurance.py", ROOT / "aerofleet/api/routes/spray.py",
         ROOT / "aerofleet/api/routes/vr.py", ROOT / "aerofleet/api/routes/vr_study.py",
         ROOT / "aerofleet/api/routes/evidence.py", ROOT / "aerofleet/evidence.py"] + sorted(
    p for p in (PKG / "assurance").glob("*.py") if p.name != "review_panel.py" and not p.name.startswith("._"))
FORBIDDEN_INTERNAL = ("aerofleet.agents", "aerofleet.assurance.review_panel", "agent_memory")
FORBIDDEN_LIBS = {"openai", "anthropic", "ollama", "langchain", "langchain_core", "transformers", "torch", "tensorflow",
                  "llama_cpp", "google.generativeai", "sklearn", "xgboost", "lightgbm"}


def _module_file(name: str):
    rel = Path(*name.split("."))
    for cand in (ROOT / rel.with_suffix(".py"), ROOT / rel / "__init__.py"):
        if cand.exists():
            return cand
    return None


def _imports(path: Path):
    tree = ast.parse(path.read_text(), str(path))
    pkg = ".".join(path.relative_to(ROOT).with_suffix("").parts[:-1])
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:                                   # relative import
                parts = pkg.split(".")[: len(pkg.split(".")) - node.level + 1]
                base = ".".join(parts + ([base] if base else []))
            yield base
            yield from (f"{base}.{a.name}" for a in node.names)    # `from pkg import module`


def reachable(entry=None):
    seen_files, names, stack = set(), set(), list(entry or ENTRY)
    while stack:
        f = stack.pop()
        if f in seen_files:
            continue
        seen_files.add(f)
        for name in _imports(f):
            names.add(name)
            if name.startswith("aerofleet") and (mf := _module_file(name)) is not None:
                stack.append(mf)
    return seen_files, names


def test_the_decision_path_reaches_no_ai_agent_panel_or_ml_library():
    files, names = reachable()
    internal = sorted(n for n in names if n.startswith(FORBIDDEN_INTERNAL))
    libs = sorted(n for n in names if n.split(".")[0] in FORBIDDEN_LIBS or n in FORBIDDEN_LIBS)
    assert not internal, f"AI code reachable from the product: {internal}"
    assert not libs, f"ML / language-model libraries reachable from the product: {libs}"
    assert len(files) > 15                                    # the walk really covered the product, not just one file


def test_the_guard_would_catch_a_violation():
    """The same walk started from the earlier prototype's agent code does find a language-model library, and the
    panel module is not among the files the product reaches, so the check above is able to fail."""
    _, legacy = reachable([PKG / "agents" / "llm_backend.py"])
    assert "ollama" in legacy                                 # the old local-LLM agent, two imports away
    files, _ = reachable()
    assert (PKG / "assurance" / "review_panel.py") not in files and not any("agents" in f.parts for f in files)
