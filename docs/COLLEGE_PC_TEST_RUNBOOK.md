# Testing AeroFleet on the College PC — Runbook

What "testing the system's accuracy" actually means here, and the exact steps for tomorrow. This
doesn't need any cloud service — everything below runs entirely on the college PC itself.

## What "accuracy" means for this system

AeroFleet doesn't have a single "accuracy %" the way a classifier does. There are two genuinely
different things worth measuring, and they need different tools:

1. **Does the CBF safety gate ever approve something it shouldn't, or reject something safe?**
   This is deterministic code (`aerofleet/safety/cbf_gate.py`) — it's covered by the existing
   pytest suite (`tests/`, 252 tests) and is either correct or not; there's no "accuracy percentage"
   to measure, it's pass/fail per test case. Run `pytest tests/ -q` to check this — takes under two
   minutes, no LLM/GPU needed.

2. **Does the 16-agent LLM council make sound recommendations under realistic operating
   conditions?** This is the part that actually needs the GPU and real models, and it's what
   `scenario_engine/` already exists to measure — see below.

## Running the scenario suite (the real accuracy test)

The 7 scenarios in `scenario_engine/scenarios/synthetic/` (`standard_delivery`,
`rush_hour_multi_order`, `battery_swap_bottleneck`, `depot_outage_reroute`,
`geofence_incursion_response`, `motor_failure_emergency_landing`, `storm_wind_diversion`) are
realistic dispatch conditions with expected-value checks. This is what the Ops Center dashboard's
"Scenario Suite" tile (`X/7 passed`) reflects — it reads `0/7` on a fresh session simply because
nothing has been run yet that session, not because anything is failing.

```bash
# From the project root, with Ollama running and the roster models pulled
# (see AI_MODEL_SETUP_GUIDE.md, or use the desktop app's guided Setup Wizard):
python -m scenario_engine.runner --type all
```

This calls the real council for each scenario, evaluates the output against expected values, and
retries failed scenarios with corrective prompts (up to each scenario's configured `max_retries`).
Results:

- Print live to the terminal as each scenario runs (pass/fail, which metrics failed, how long each
  attempt took — this is your real evidence of LLM inference latency on that PC's GPU too).
- Land in `scenario_reports/` as dated JSON — this is the artifact worth keeping/screenshotting,
  since it's gitignored and won't survive a fresh clone.
- A final summary: `passed`, `failed`, `pass_rate_pct` — this is the number to report as "system
  accuracy" honestly, since it's a real evaluation against defined expected values, not a made-up
  metric.

Useful variants:

```bash
# Validate scenario files load correctly without spending any GPU time — do this FIRST
python -m scenario_engine.runner --dry-run

# Just one scenario, e.g. to debug a specific failure
python -m scenario_engine.runner --id <scenario_id>

# Keep retraining/re-running until every scenario passes (can take a while — real LLM calls)
python -m scenario_engine.runner --type all --continuous
```

## Sequence for tomorrow

1. Clone the repo: `git clone https://github.com/AdityaPathare46/aerofleet.git`
2. Install Ollama + the 5 roster models — either via the desktop app's **Setup Wizard** (opens
   automatically on first launch; see below) or manually per `AI_MODEL_SETUP_GUIDE.md`.
3. `pytest tests/ -q` — confirms the deterministic safety layer is intact (~2 min, no GPU needed).
4. `python -m scenario_engine.runner --dry-run` — confirms scenario files load (~seconds).
5. `python -m scenario_engine.runner --type all` — the real accuracy run against live models.
   Screenshot the terminal summary and keep the `scenario_reports/*.json` file it writes — that's
   your actual, non-fabricated evidence for tomorrow.
6. Build and install the real desktop app (see **Building a real installer** below) rather than
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

## The Setup Wizard (new)

The desktop app now shows a guided setup screen automatically the first time it launches on a
machine that's missing Ollama or any roster model — it installs Ollama and pulls each of the 5
models one at a time, with a live progress list, instead of requiring five separate manual
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
