# AeroFleet 2.0 — Master Plan

Status board for the rebuild. Update the checkboxes and the "Progress log" at the bottom after
every working session. Product definition: `docs/aerofleet2/AeroFleet_2.0_Final_Definition.docx`
(same content online: https://claude.ai/code/artifact/be7708f9-01ec-4308-a11f-458367a94c0d).
Handoff notes for a new assistant/model: `docs/aerofleet2/CONTEXT.md`.

## What AeroFleet 2.0 is

A ground-based pre-flight assurance tool for multi-drone operations. It never controls a drone in
flight. Four features, all deterministic code:

1. Fleet plan deconfliction and multi-drone mission export.
2. Pre-flight rule and battery-margin check, including wind at cruise altitude.
3. Configuration drift check from an uploaded parameter file (vs fleet baseline and last inspection).
4. Planned-versus-flown reconciliation from an uploaded flight log.

VR: rehearse the whole fleet plan; replay planned vs flown. Language models: advisory only (review
panel debating the likely cause of an already-flagged finding; plain-language intake; report text).

## Hard rules (do not break)

- No LLM calculates, checks or approves anything. Every number and verdict comes from code.
- No in-flight control. No arm/takeoff/goto. MAVLink, if used at all, is read-only.
- No drone hardware is required for any feature: everything works from uploaded files.
- Never fabricate results. Run it, then report the measured number.
- Do not claim "mathematically guaranteed", "tamper-proof" or "secure". See the definition doc.

## Build order

### Phase 1 — Parameter files and configuration drift  (sales wedge + paper data)
- [x] 1.1 Parameter-file parser (`aerofleet/assurance/params.py`): Mission Planner / QGC / MAVProxy text formats
- [x] 1.2 Drift engine (`aerofleet/assurance/drift.py`): diff vs baseline and vs previous, safety-critical catalogue, severity
- [x] 1.3 Unit tests (`tests/unit/test_assurance_params.py`, `test_assurance_drift.py`)
- [x] 1.4 API (`aerofleet/api/routes/assurance.py`, prefix `/api/v1/assurance/fleets/{fleet}`): `POST|GET /baseline`, `POST /approvals`, `POST /drones/{id}/params`, `GET /drones/{id}/drift`, `GET /drift` (fleet summary)
- [x] 1.5 DB tables `param_snapshots`, `fleet_baselines` (in `aerofleet/data/models/models.py`)
- [x] 1.6 59 FC checks on an uploaded file (`aerofleet/assurance/static_checks.py`, `GET .../drones/{id}/checks`): evaluated / needs_live / manual, verdict covers evaluated only
- [x] 1.7 Desktop screen `tauri-app/src/pages/FleetAssurance.tsx` (nav: Fleet Assurance): baseline, upload, fleet table, drift detail with approvals, file-only check summary
- [x] 1.8 Catalogue checked against the official ArduPilot Copter and PX4 parameter lists (`research/drift_catalogue_check.py`, results in `research/results/drift_catalogue_check.md`). The seeded-change test was dropped: a dictionary diff catches every change by construction. False-alarm rate moves to 2.4 (needs two files from the same drone).

### Phase 2 — Flight logs and planned-versus-flown
- [x] 2.1 Log reader `aerofleet/assurance/flightlog.py`: ArduPilot `.tlog` (tested on a generated log) and `.bin` (same code path, NOT yet run on a real onboard log) → track, parameters, mode changes
- [x] 2.1b Reader run on 5 real ArduCopter `.BIN` and 2 real `.tlog` files from autotest.ardupilot.org (firmware-written logs of simulated flights). Fixes from it: vehicle clock instead of the recorder's clock, multi-boot logs, heartbeats from non-autopilot components ignored, vehicle type recorded, in-flight setting changes kept, learned hover throttle excluded from drift
- [x] 2.1c (part) In-flight setting changes shown in the flight review and flagged in the review list
- [ ] 2.1d PX4 `.ulg` (needs `pyulog`); read the mission stored inside a `.BIN` (CMD records) so planned-versus-flown can work from one file
- [x] 2.2 Reconciliation `aerofleet/assurance/reconcile.py`: `.waypoints` parser; per-point horizontal/vertical deviation; off-route / off-altitude / no-fly-zone episodes; manual-control takeovers; CONFORMED / DEVIATED
- [x] 2.3 API: `POST /fleets/{fleet}/drones/{id}/flights` (files `plan` + `log`; optional `city`, `corridor_m`, `altitude_m`), `GET /fleets/{fleet}/flights`, `GET .../flights/{review_id}`; table `flight_reviews`; log parameters are stored as a snapshot so drift covers the flown configuration
- [x] 2.3b Flights section in `tauri-app/src/pages/FleetAssurance.tsx`: choose mission + log, Compare, review list, episode table
- [ ] 2.3c PDF export of a flight review; test the `city` no-fly-zone option through the API (only unit-tested so far)
- [ ] 2.4 Public-log mining script for the paper (parameter prevalence across many public logs); also the drift false-alarm rate between consecutive logs of the same vehicle

### Phase 3 — Deconfliction and VR rehearsal
- [x] 3.1 `aerofleet/assurance/deconflict.py`: time-parameterised plans, pairwise conflicts, greedy fix (launch delay; cruise-height change only when vertical separation is allowed), independent re-check, launch schedule. Standalone on `.waypoints` plans (does not use `fleet/conflict_forecast.py`)
- [x] 3.2 `POST /api/v1/assurance/plans/deconflict` (files `plans[]`, form field `options` JSON): conflicts before/after, changes, launch schedule, and each mission file back (height rewritten when changed). Stateless
- [x] 3.2b "Will these missions conflict?" section in the Fleet Assurance screen: choose several mission files, optional vertical separation, schedule table, per-mission download
- [x] 3.3 Scale test `research/deconflict_scale.py` → `research/results/deconflict_scale.md` (10–300 missions, 3 seeds, two separation rules)
- [ ] 3.3b Follow-ups from the scale test: allow longer delays / a second pass, model depot pad throughput explicitly, report conflicts per flight hour, try rerouting
- [ ] 3.4 VR: fleet-plan rehearsal (before/after fix) and planned-vs-flown replay (Unity app, `unity/AeroFleetVR`)

### Phase 4 — Wind at altitude
- [x] 4.1 `aerofleet/assurance/wind.py` + `POST /api/v1/assurance/plans/wind-check`: Open-Meteo profile (10/80/120/180 m, verified with a live call) interpolated to cruise height; per-leg wind triangle; PASS / FAILS_AT_ALTITUDE / FAIL; manual profile for offline use
- [x] 4.1b Wind section in the Fleet Assurance screen
- [ ] 4.1c Feed the wind margin into the existing pre-flight compliance report
- [x] 4.2 `research/wind_altitude_study.py` → `research/results/wind_altitude_study.md` (30 days of hourly model wind for Pune)

### Phase 5 — Signing and the review panel
- [x] 5.1 `aerofleet/assurance/ledger.py` + table `assurance_ledger`: Ed25519-signed, hash-chained entry for every baseline, approval, drift upload and flight review; `GET /api/v1/assurance/ledger`, `GET .../ledger/verify`; key in the per-install config dir (`AEROFLEET_REPORT_KEY_FILE` overrides)
- [x] 5.1b Signed-record section in the app: last 10 entries, Check the record, Export for an auditor (entries + public key as JSON)
- [ ] 5.1c Record deconfliction and wind checks in the signed record too (they are stateless today)
- [x] 5.2 `aerofleet/assurance/review_panel.py`: facts per episode in five slices (log reader now extracts battery + GPS numbers), fixed cause list, reply shape, own-evidence citation check, counts-only second round, fixed aggregation, NEEDS_HUMAN_REVIEW on disagreement, no-AI rule comparator. Tested with a scripted stand-in model only
- [ ] 5.2b Wire the panel to flight reviews: store facts at upload, run as a background job (a real model takes minutes), endpoint + screen section, record the result in the signed ledger
- [x] 5.3 (harness) `research/panel_eval/` — 60 cases, rule vs one agent vs panel, compromised-reviewer attack, planted-text test (0 of 40 reached a prompt). Per-model results files; runner scripts `research/college_pc_panel_eval.ps1|.sh`; instructions `docs/aerofleet2/PANEL_EVAL_RUNBOOK.md`
- [ ] 5.3b USER runs it on the college PC (qwen2.5:7b, llama3.2, and qwen2.5:14b if it fits) and sends back `research/results/panel_eval`. Decision rule is in the runbook: panel goes in the app only if it beats the no-AI rule

### Phase 6 — Park the old live path
- [x] 6.1 `AEROFLEET_LIVE_CONTROL` (default off; `aerofleet/assurance/live_control.py`): arm, post-dispatch take-off/go-to and the bench motor test are refused; dispatch plans with simulated drones only; disarm, emergency stop and RTL/hold fallbacks stay available; `GET /api/v1/assurance/policy`
- [x] 6.2 App opens on Fleet Assurance; Council Room and the telemetry/agent-roster side panel are hidden unless Settings ▸ Show legacy screens is on (`tauri-app/src/lib/policy.ts`); Arm button only when live control is on; header subtitle updated
- [ ] 6.2b Still showing legacy framing: Ops Center, Dispatch Console, Incident Forensics, Fleet Policy, Scenario Lab pages — decide per page: keep, rename or move behind the legacy toggle
- [ ] 6.3 Update README and docs to the 2.0 framing

### Demand and publication (not code)
- [ ] D1 Check whether Indian agri/service fleets run ArduPilot/PX4 and whether AirData serves them
- [ ] D2 Public "upload a log, get a report" release to ArduPilot/PX4 forums; count uploads for 6 weeks
- [ ] D3 Free audit offer to 20 Indian makers/service firms; go only if ≥3 send logs or ≥100 public uploads
- [ ] D4 Literature check for the primary paper (misconfiguration prevalence in field logs)
- [ ] D5 VR-vs-desktop study (12–16 people); protocol draft exists in `research/user_study_protocol.md`

## Progress log

- 2026-10-08: Definition finalised. Master plan and context file written. Phase 1.1–1.3 built and tested.
- 2026-10-08: Phase 1.4–1.5 done: storage + API for baseline, approvals, upload and drift; 5 integration tests (`tests/integration/test_assurance_api.py`). Next: 1.6.
- 2026-10-08: Phase 1.6 done. Next: 1.7 desktop UI panel (tauri-app/src/components), then 1.8.
- 2026-10-08: Phase 1.7 done and checked in the browser. Note: the dev backend's database is `/tmp/aerofleet.db` (wiped on reboot, so test users vanish). Next: 1.8 drift catch-rate test, then Phase 2.
- 2026-10-08: Phase 1.8 done. 20 of 113 catalogue names were older-firmware spellings (ArduPilot renamed RTL_ALT, ANGLE_MAX, ARMING_CHECK, WPNAV_* ...); both spellings now covered, plus gaps found by the documentation cross-check. Phase 1 complete. Next: 2.1 log reader.
- 2026-10-08: Phase 2.1–2.2 done (11 unit tests). Next: 2.3 API + report (upload plan + log per drone, store result, show in the Fleet Assurance screen), then 2.1b real `.bin` logs.
- 2026-10-08: Phase 2.3 API done (3 new integration tests, 9 in the file). Next: 2.3b screen.
- 2026-10-08: Phase 2.3b done and checked in the browser; fixed a stale-reply race when the fleet changes. Both wedge features now work end to end in the dev app. The Mac app bundle has NOT been rebuilt since phase 1. Next: 2.1b real `.bin` logs (needs sample downloads), then 2.4 or Phase 3.
- 2026-10-08: Mac app rebuilt and installed to /Applications (includes Fleet Assurance: drift + flight reviews). Not launched or checked inside the bundle; the dev build was checked in the browser.
- 2026-10-08: Phase 3.1 done (7 unit tests). Design note: default rule is horizontal-only, like the CBF gate, so height changes are offered only with `v_sep_m` set. Delays are a launch schedule, not edits to the mission file. Next: 3.2 API + multi-drone export, 3.3 scale test.
- 2026-10-08: Phase 3.3 done. Fix time ~1 s for 300 missions. All conflicts cleared up to 10 missions (same height) and up to 50 (layered heights + vertical separation) in a 10-min window from 6 depots; beyond that the 5-min delay cap leaves missions unresolved (depots saturate). Next: 3.2 API + multi-drone export, then 3.4 VR rehearsal.
- 2026-10-08: Phase 3.2 API done (3 new integration tests; 12 in the file). Next: 3.2b screen, then 3.4 VR rehearsal (Unity + APK build, the most expensive step left).
- 2026-10-08: Phase 3.2b done, checked in the browser. The check showed the fix never combined a height change with a delay; added. Layered case after the change: all cleared up to 50, 0.3 unresolved at 100 (was 3.3), 139.7 at 300 (was 154.3); fix time 3.4 s at 300. Same-height table unchanged. Mac app not rebuilt since phase 2. Next: Phase 4 (wind) or 3.4 (VR rehearsal).
- 2026-10-08: Mac app rebuilt and installed again; it now includes all three Fleet Assurance sections (drift, flight reviews, deconfliction). Not launched or checked inside the bundle.
- 2026-10-12: Phase 6.1 done (6 tests, 1 skipped). ENVIRONMENT PROBLEM found: after a macOS upgrade the venv's scipy no longer loads, so scikit-learn fails and creating an order on the road graph (legacy dispatch, and the VR dispatch tests) raises ImportError. Assurance code is unaffected. Fix = reinstall scipy/scikit-learn in `.venv` (a download; ask the user first). Next: 6.2 hide council/live-control UI, or Phase 4.
- 2026-10-12: scipy reinstall did NOT fix the import (the newest scipy for Python 3.10 ships a binary macOS 27 will not load). Worked around the one place it mattered: `CityGraph.nearest_node` now does its own great-circle search in numpy. Full suite: 579 passed, 2 failed (the known test_config baseline). Still degraded: `safety/cbf_gate.py` skips its optional scipy QP projection (it logs a warning). Real fix = rebuild `.venv` on Python ≥ 3.11 (large download; ask first). Phase 6.2 done, checked in the browser. Mac app not rebuilt.
- 2026-10-12: Phase 4.1–4.2 done (6 unit + 2 integration tests). Pune, 720 hours: median wind 2.2 m/s at 10 m vs 3.5 at 100 m (ratio 1.58, p90 2.04). A 3 km out-and-back at 100 m with a 20% battery margin fails only at altitude in 11.9% of mission-hours (27.5% at a 10% margin, 5.7% at 30%). Next: 4.1b screen, 5.1 signing.
- 2026-10-12: Phase 5.1 done (8 integration tests). Next: 4.1b / 5.1b screens, then 5.2 review panel, 2.1b real `.bin` logs, 3.4 VR rehearsal. Mac app not rebuilt since 8 Oct.
- 2026-10-12: 4.1b + 5.1b screens done and checked in the browser (live forecast call worked). Fixed: with no hour given the wind check used the first forecast hour (midnight UTC) instead of the current hour.
- 2026-10-12: Mac app rebuilt and installed with all five Fleet Assurance sections, the 2.0 navigation and the live-control switch. Not launched or checked inside the bundle.
- 2026-10-12: Phase 5.2 core done (16 unit tests + 1 for battery/GPS extraction). NOT yet run against a real language model — that is 5.3. Next: 5.2b wiring, then 5.3 evaluation.
- 2026-10-12: Phase 2.1b done on real logs (downloaded to the scratch folder, not committed). A real parameter list has 1,431 entries: 49 safety-critical, 125 flight-limit, 231 tuning, 84 ignored. The 59 checks evaluate 25 from a full list (17 pass, 2 warn, 6 fail on simulator defaults). One real log showed the geofence enabled and its ceiling cut from 100 m to 50 m at 10.2 s, restored at 63.2 s: final values alone hide that. Panel evaluation still running.
- 2026-10-12: In-flight setting changes on screen; checked end to end with a real `.BIN` uploaded through the API (448 positions, 8 safety-critical changes listed with times, ledger entry written). Mac app not rebuilt since this and the 5.2/2.1b changes.
- 2026-10-12: Panel evaluation on the Mac stopped at 24/60 with llama3.2: rule 18 right / 0 wrong; one agent 4 / 0; panel 2 right / 17 wrong; one compromised reviewer could steer 13 of 24. Handed to the college PC (runbook written). 5.2b (wiring the panel into the app) is ON HOLD until those results are back.
