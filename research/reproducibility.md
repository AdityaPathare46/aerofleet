# Reproducibility Package

What's already real vs. what needs assembling, and the exact command to reproduce every number
this research effort produces or will produce.

## Environment — already solid, needs one addition

`requirements.txt`, `requirements-dev.txt`, `Dockerfile`, and `docker-compose.yml` already exist at
the repo root — this is most of a real reproducibility package already. Missing: a pinned Python
version file (`.python-version` — this session's own Python is 3.10.19 via `.venv`, not the
system's 3.14; state the exact version used for real results explicitly, since "3.10 vs 3.14"
silently changes dependency resolution). Add one before results are final.

## Every real/pending number, and the exact command that produces it

| Result | Command | Status |
|---|---|---|
| Deterministic dispatch invariants (834 cases) | `pytest tests/property/test_dispatch_invariants.py -q -m property` | Done — 834 passed, 0 failed |
| Regex-baseline ceiling (1,000 cases, mock) | `USE_MOCK_AGENTS=true python -m scenario_engine.mass_forensics_evaluation --dry-run --target 1000 --batch-size 250 --study-dir scenario_reports/mass_forensics_baseline` | Done — macro-F1 1.0 (see `research/baseline_comparison.md`) |
| Real LLM forensics number (1,000 cases) | `python -m scenario_engine.mass_forensics_evaluation` | **Pending — college PC, ~11-22 GPU-hours** |
| Real LLM forensics number, free-GPU variant (1,000 cases, 4 agents on a substitute model) | `research/kaggle_mass_forensics_run.ipynb` on Kaggle | **Pending — your action, chunked across weekly free quota** |
| Zone-penalty ablation (111 real pairs) | `python -m research.ablation_zone_penalty` | Done — see `research/results/` |
| Full regression suite | `pytest tests/ -q` | Done — 298 passed, 8 pre-existing baseline failures (unrelated, documented) |

## What "reproduce the paper's numbers" means for someone else

1. Clone the repo, `pip install -r requirements.txt`, `pip install -r requirements-dev.txt`.
2. For the deterministic results (property suite, ablation study): no GPU, no Ollama, runs
   anywhere. `pytest` and `python -m research.ablation_zone_penalty` respectively.
3. For the LLM forensics number: needs Ollama + the 4 roster models pulled (see
   `AI_MODEL_SETUP_GUIDE.md`) and real GPU time. `USE_MOCK_AGENTS` controls mock-vs-real — the study
   ledger structurally refuses to mix the two (see `scenario_engine/mass_forensics_evaluation.py`'s
   own mock/real-mixing guard), so there's no risk of silently reporting a mock number as real.

## Still needed for a full release-quality package

1. `.python-version` pin (above).
2. A single top-level `RESEARCH.md` or repo README section pointing at this whole `research/`
   folder, so someone auditing the paper's claims can find the evidence without hunting.
3. Once the real LLM run completes: the actual `scenario_reports/mass_forensics/` output committed
   somewhere durable (it's currently gitignored, correctly, since it's large generated output — but
   the *numbers extracted from it* for the paper need to land in a small, checked-in summary, the
   same way `research/baseline_comparison.md` already captures the mock-mode numbers rather than
   just linking to a gitignored directory).
4. A frozen `pip freeze > research/environment_lockfile.txt` at the moment final results are
   generated — `requirements.txt` pins direct dependencies but not their transitive versions;
   exact reproduction later needs the full lock, not just the direct list.
