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
- [ ] 2.1b Run the reader on real `.bin` logs; add PX4 `.ulg` (needs `pyulog`, not installed)
- [x] 2.2 Reconciliation `aerofleet/assurance/reconcile.py`: `.waypoints` parser; per-point horizontal/vertical deviation; off-route / off-altitude / no-fly-zone episodes; manual-control takeovers; CONFORMED / DEVIATED
- [x] 2.3 API: `POST /fleets/{fleet}/drones/{id}/flights` (files `plan` + `log`; optional `city`, `corridor_m`, `altitude_m`), `GET /fleets/{fleet}/flights`, `GET .../flights/{review_id}`; table `flight_reviews`; log parameters are stored as a snapshot so drift covers the flown configuration
- [x] 2.3b Flights section in `tauri-app/src/pages/FleetAssurance.tsx`: choose mission + log, Compare, review list, episode table
- [ ] 2.3c PDF export of a flight review; test the `city` no-fly-zone option through the API (only unit-tested so far)
- [ ] 2.4 Public-log mining script for the paper (parameter prevalence across many public logs); also the drift false-alarm rate between consecutive logs of the same vehicle

### Phase 3 — Deconfliction and VR rehearsal
- [ ] 3.1 Automatic fix on top of `fleet/conflict_forecast.py`: altitude-band change or timed delay; re-verify
- [ ] 3.2 Multi-drone `.waypoints` export (`integrations/mission_planner.py` does one drone today)
- [ ] 3.3 Scale test: 10–300 planned drones over Pune; conflicts per flight hour, added delay
- [ ] 3.4 VR: fleet-plan rehearsal (before/after fix) and planned-vs-flown replay (Unity app, `unity/AeroFleetVR`)

### Phase 4 — Wind at altitude
- [ ] 4.1 Forecast wind at cruise height (Open-Meteo has 80/120/180 m winds; verify) into the battery margin
- [ ] 4.2 One-month Pune study: passes on ground wind but fails at altitude

### Phase 5 — Signing and the review panel
- [ ] 5.1 Signed, hash-chained reports (ordinary signatures; no TEE)
- [ ] 5.2 Review panel: per-agent evidence slices, schema-constrained replies, claim check, fixed aggregation rule
- [ ] 5.3 Evaluation: panel vs single agent vs no AI; poisoned-log attack success rate (`scenario_engine/prompt_injector.py`)

### Phase 6 — Park the old live path
- [ ] 6.1 Disable arm/takeoff/goto in `api/routes/orders.py` behind a default-off flag; keep code
- [ ] 6.2 Hide the 16-agent dispatch council and live-control UI from the desktop app
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
