# AeroFleet 2.0 — Context for whoever continues this (human or AI model)

Read this first, then `docs/aerofleet2/MASTER_PLAN.md` (the checklist: do the first unchecked item).

## 1. What is being built and why

AeroFleet started as an AI multi-agent drone *dispatch* system with a VR safety view. A senior
engineer's review called it irrelevant: no real use case, and LLMs in places where plain code
belongs. After a data-driven review the project was re-scoped (October 2026) to **AeroFleet 2.0: a
ground-based pre-flight assurance tool for multi-drone fleets**. Full definition:
`docs/aerofleet2/AeroFleet_2.0_Final_Definition.docx`.

Decisions already made — do not reopen them without the user asking:
- Ground only. No in-flight control. No drone hardware needed (everything from uploaded files).
- LLMs never calculate, check or approve. They only debate the *likely cause* of a finding the code
  already flagged (review panel), turn plain-language requests into structured missions, and write
  report text. Each panel agent sees only its own evidence slice; code verifies every cited fact.
- Removed from the product (code may stay, parked): live MAVLink commands, live telemetry loop,
  digital twin, D2D mesh, the 16-agent dispatch council + pheromone dashboard, the TEE design, the
  insurance-discount claim, the AI-written threat report.
- First buyer hypothesis: Indian drone makers / service firms with large scattered fleets. Unproven.
  The sales wedge is features 3 and 4 (drift + planned-vs-flown from uploaded files).
- Primary paper: prevalence of unsafe configuration and plan deviation in public flight logs.
- Rejected directions (already critiqued, don't re-propose): CFM compute-freshness thesis, pilot-school
  trainer, spray-day planner as primary, urban blood delivery, UTM capacity testbed as primary.

## 2. Repo map (root: this repository)

- `aerofleet/` Python backend (FastAPI). `api/routes/*` endpoints; `city/` graph, zones, routing,
  trajectories; `fleet/` state, dispatch, `conflict_forecast.py`; `safety/cbf_gate.py` the
  deterministic 11-limit check; `hardware/compliance_rules.py` 59 flight-controller checks,
  `fc_inspector.py` snapshot type; `integrations/mission_planner.py` `.waypoints` export;
  `agents/` the LLM council (legacy) and forensics; `vr/` desktop↔headset pairing + LAN gateway.
- `aerofleet/assurance/` **new 2.0 code goes here** (params, drift; later logs, reconcile, deconflict).
- `scenario_engine/` scenario runner, incident generator, `prompt_injector.py`.
- `tauri-app/` desktop app (React + Tauri). `unity/AeroFleetVR/` mirror of the Quest/desktop VR app;
  the live Unity project is at `/Volumes/UnityWork/UnityProjects/Aerofleet` (rsync Scripts → mirror).
- `research/` experiments and write-ups; `docs/` guides; `tests/` pytest.

## 3. How to run things (macOS, this machine)

- Python: `.venv/bin/python`. Backend: `.venv/bin/python -m uvicorn aerofleet.api.app:app --host 127.0.0.1 --port 8000`
  (startup takes ~1–2 min: it loads city graphs).
- Tests: `.venv/bin/python -m pytest tests/unit/test_assurance_*.py -q --no-cov -p no:cacheprovider`.
  Full suite ≈ 6–7 min. **Known baseline: 2 failures in `tests/unit/test_config.py`** (conftest sets
  ENVIRONMENT=test); they pass in isolation and are not regressions.
- Desktop app dev server: `npm run dev --prefix tauri-app` (port 1420). Build:
  `CARGO_TARGET_DIR=<a folder on the internal disk> npx tauri build --bundles app` — the repo lives
  on an exFAT drive that creates `._*` files which break cargo; then `codesign --force --deep -s -`.
- Quest APK: Unity menu AeroFleet ▸ Build ▸ Quest APK (10–40 min; blocks the editor).

## 4. Working rules the user has set

- Verify by running; never invent numbers. Say plainly what was not checked.
- Commit and push verified work to `main` with detailed messages ending
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (adjust the model name if you are a different model).
- Never commit: `aerofleet/README.md`, `aerofleet/parse_results.py`, `aerofleet/results (1).jsonl`,
  `docs/SPACE_MISSION_ARCHITECT_README.md`, `research/aerofleet_midterm_review.pptx`.
- No tokens/keys in files or command lines. Test credentials only on localhost.
- Ask before large downloads or destructive operations.
- The user prefers short, plain-language answers and wants critical, honest review over agreement.

## 5. State of earlier work (still in the repo)

- VR app works in Unity play mode end to end (controls, depots, inspection, 2-min preview, route
  planning, drone builder); the user has not yet confirmed the latest APK on the headset.
- LLM accuracy baseline: 1,000-case forensics run, macro-F1 0.468, ~291 s/case, 82% of misses were
  unparseable replies (`research/real_llm_results.md`). A follow-up experiment (`research/forensics_v2/`,
  runner scripts `research/college_pc_forensics_v2.*`) was meant to run on the college PC; results
  were never sent back.
- VR dispatch from the headset exists behind a desktop permission; under 2.0 it becomes "plan
  rehearsal", not dispatch (Phase 6).

## 6. Unverified claims to check before relying on them

- Whether Indian agri/service fleets use ArduPilot/PX4 logs, and whether AirData already serves them.
- Open-Meteo provides wind at 80/120/180 m (believed, not checked).
- Novelty of the primary paper (short search only). Prior work to read: FSE'21 autopilot bug study
  (569 bugs), the 178-abnormal-log study, ArduCrash dataset, RouthSearch.
- Regulatory citations: UAOP may no longer exist under Drone Rules 2021; verify every rule reference.
- The drift severity catalogue (`aerofleet/assurance/drift.py`) was written from memory of the ArduPilot
  Copter and PX4 parameter references, not checked name-by-name against a firmware version.
- Intel SGX availability on client CPUs (the old TEE note claimed it; likely wrong).

## 7. How to continue

1. Open `MASTER_PLAN.md`, take the first unchecked item, read the files it names.
2. Build it small, with unit tests in `tests/unit/test_assurance_*.py`.
3. Run the tests, commit, push, tick the box, add one line to the Progress log.
