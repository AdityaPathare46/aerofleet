# Testing AeroFleet on the College PC — Runbook

What "testing the system's accuracy" actually means here, and the exact steps for tomorrow. This
doesn't need any cloud service — everything below runs entirely on the college PC itself.

## What "accuracy" means for this system

AeroFleet doesn't have a single "accuracy %" the way a classifier does. There are two genuinely
different things worth measuring, and they need different tools:

1. **Does the CBF safety gate ever approve something it shouldn't, or reject something safe?**
   Deterministic, no LLM involved — covered by the existing pytest suite (`tests/`, 252+ tests)
   plus a new property-based suite generating 3,000+ real, distinct dispatch cases from real city
   zone data (`tests/property/test_dispatch_invariants.py`). Both run in well under a minute
   combined, no GPU needed.

2. **Are the LLM agents themselves reasoning well?** The part that actually needs the GPU and real
   models — `scenario_engine/incident_forensics_evaluation.py` (12 cases, minutes) for a quick
   check, or `scenario_engine/mass_forensics_evaluation.py` (5,000 cases, batched across multiple
   days) for a real, citable, publication-quality number.

**Full detail, including exactly why the old `scenario_engine.runner` suite mentioned in earlier
versions of this doc is no longer the right tool, is in `docs/TESTING_STRATEGY.md` — read that
first if anything below is unclear.** Short version: that suite evaluates the council's output
against hand-labeled numbers, which was correct back when the council made decisions; it doesn't
anymore (the CBF gate does, deterministically, before the council ever runs) — so it's now testing
a role the council doesn't have.

## Running the real tests

```bash
# 1. Deterministic safety layer — pytest, no LLM needed
pytest tests/ -q

# 2. Deterministic decision layer at scale — 3,000+ generated cases, no LLM needed
pytest tests/property/test_dispatch_invariants.py -q -m property

# 3. The actual LLM-dependent measurement (12 cases, minutes) — needs Ollama + the 4 roster models
python -m scenario_engine.incident_forensics_evaluation

# 4. The publication-scale version (5,000 cases, batched — run this, then re-run the SAME
#    command again on later days to continue where it left off; safe to Ctrl-C any time)
python -m scenario_engine.mass_forensics_evaluation
```

Command 3 writes a JSON report to `scenario_reports/` with per-factor precision/recall/F1 — **read
the module's own docstring before citing a number from it**: run with `USE_MOCK_AGENTS=true` it's
a pipeline sanity check only (scores perfectly by construction on the regex-mappable factors), and
the number worth keeping is from re-running it with that env var unset, against the real models.

Command 4 writes batch reports plus a running `index.html` to `scenario_reports/mass_forensics/` —
same mock-mode caveat applies, and it's enforced structurally (a study's ledger refuses to mix
mock and real results). At 8 LLM calls per incident across 4 models, 5,000 incidents is tens of
GPU-hours — this will **not** finish in one sitting even on the 5090. That's expected: it's built
to be killed and resumed across as many days as it takes. See `docs/TESTING_STRATEGY.md`'s section
2 for the full design (category taxonomy, batching, checkpoint format).

## Sequence for tomorrow

1. Clone the repo: `git clone https://github.com/AdityaPathare46/aerofleet.git`
2. Install Ollama + the 4 roster models — either via the desktop app's **Setup Wizard** (opens
   automatically on first launch; see below) or manually per `AI_MODEL_SETUP_GUIDE.md`.
3. `pytest tests/ -q` — confirms the deterministic safety layer is intact (~2 min, no GPU needed).
4. `pytest tests/property/test_dispatch_invariants.py -q -m property` — 3,000+ generated cases
   against real city zone data, still no GPU needed (~1 min).
5. `python -m scenario_engine.incident_forensics_evaluation` — the real, GPU-dependent measurement
   of the LLM agents' own reasoning. Keep the JSON it writes to `scenario_reports/` — that's your
   actual, non-fabricated evidence for tomorrow.
6. Kick off `python -m scenario_engine.mass_forensics_evaluation` (no `--dry-run`, `USE_MOCK_AGENTS`
   unset) and let it run in the background — this is the 5,000-case publication number, and it
   won't finish tonight. Re-run the exact same command on later days to keep going from where it
   stopped; `scenario_reports/mass_forensics/index.html` shows real progress at any point, even
   partway through.
7. Build and install the real desktop app (see **Building a real installer** below) rather than
   running the dev server, then demo the VR Safety View's two modes — Live and Incident Replay
   (dispatch an order into a real DGCA red zone to generate an incident to replay, per
   `docs/PATENT_NOVELTY.md`'s Claim 4 reference implementation).

## Building a real installer

`npm run tauri dev` (what runs during development) is a dev server, not an installable app. For an
actual `.exe`/`.msi` installer:

```bash
cd tauri-app
npm install
npm run tauri build
```

This must run **on the target OS** — a Windows build has to run on Windows, a macOS build on macOS.
Tauri does not reliably cross-compile a Windows installer from a Mac (or vice versa), so building it
once on this Mac only produces a macOS `.app`/`.dmg`, not something installable on the college PC.

On Windows, this produces (under `tauri-app/src-tauri/target/release/bundle/`):
- `nsis/AeroFleet_<version>_x64-setup.exe` — a normal double-click installer (NSIS-based).
- `msi/AeroFleet_<version>_x64_en-US.msi` — an MSI package, if your institution's policy prefers
  those for install tracking.

First build compiles the whole Rust dependency tree from scratch and can take 10–20+ minutes
depending on the PC; rebuilds after that are much faster. Requires the Rust toolchain
(`rustup.rs`) and, on Windows, the "Desktop development with C++" Visual Studio Build Tools
workload — both one-time installs, see
[Tauri's prerequisites guide](https://tauri.app/start/prerequisites/) if `npm run tauri build`
errors out asking for them.

**Expect a SmartScreen warning on first run** — the build isn't code-signed (needs a paid Windows
code-signing certificate, not set up), so Windows will show "Windows protected your PC" the first
time the installer or the app itself runs. Click **More info** → **Run anyway**. This is normal for
an unsigned build, not a sign anything actually failed — same underlying cause as the macOS
build needing `xattr -cr` on first launch there (see `landing/README.md`'s Gatekeeper section for
the full explanation, since both installers on the landing page hit the same class of issue).

## The Setup Wizard (new)

The desktop app now shows a guided setup screen automatically the first time it launches on a
machine that's missing Ollama or any roster model — it installs Ollama and pulls each of the 4
models one at a time, with a live progress list, instead of requiring four separate manual
`ollama pull` commands. See `tauri-app/src/components/SetupWizard.tsx`.

One correction to plan around: **Ollama's own Windows/macOS installer does a per-user install and
does not require Administrator/elevated privileges** — it installs to `%LOCALAPPDATA%` on Windows,
not `Program Files`. So there's no UAC "run as administrator" prompt to expect from this flow. The
one case where a college lab PC might still block it: some locked-down lab images restrict *any*
new installer via Application Control policy regardless of install location — if that happens, the
error will be from Windows/the AV policy, not from AeroFleet, and the fallback is
`get_linux_install_command`'s manual-copy path pattern (Settings > Local Ollama shows this on
Linux; on a blocked Windows machine, install Ollama from ollama.com yourself first, then the
wizard's model-pull steps will proceed normally since only the Ollama *installer* step needs any
elevated trust decision at all).
