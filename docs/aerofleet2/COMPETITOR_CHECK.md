# Competitor check, 20 Oct 2026

Based on public web pages only, read on 20 Oct 2026; no product was tried. "Not found" means it was not on
the pages read, not proven absent.

| Product | What it has | Overlap with AeroFleet |
|---|---|---|
| **Airdata** (airdata.com/features) | Log upload incl. ArduPilot .bin/.tlog, maintenance, battery health, threshold alerts, missions linked to flights, LAANC (US) | High on fleet logging. Not found: checking a flight against its plan, tracking setting changes, signed records |
| **FlyFreely** (knowledge.flyfreely.io/flight-conformance) | "Conformance" check of uploaded logs: max distance, max height, flight area, landing battery; breaches reviewed at reconciliation | **Closest to "did it fly the plan"**, but it checks an area and limits, not the route; log formats not stated; no settings checks |
| **Auterion Suite** (docs.auterion.com) | PX4 fleet monitoring; shows each flight's parameter values and errors; maintenance, pilots, assets; paid | Shows parameters per flight. Not found: baseline comparison across a fleet |
| **Mission Planner "Compare Params"**, **Parachute** (PyPI CLI) | Compare/diff two parameter files; Parachute backs up and diffs ArduPilot params | Covers the raw drift diff for one drone. No fleet baseline, no severity, no approvals, no in-flight changes |
| **NPNT / Digital Sky** (India) | Regulator-signed permission artefact checked by firmware before arming | Overlaps the "signed" idea on the permission side, not on post-flight records |

## What is left that no product above was found to do

1. One approved settings baseline per fleet, with each difference graded from the firmware references
   (block / review / ignore) and operator approvals of exact values.
2. Settings changed **during** a flight, read from the log (e.g. the fence change in
   `FenceRelativeToTerrainMaxAlt-00000430.BIN`).
3. A route-level comparison with the exact mission file (cross-track and height error per leg, manual takeovers),
   not only area or height limits.

Everything else (logging, maintenance, conflicts, wind, signed records) exists elsewhere or is a minor add-on.

## Still to check

- Ask Airdata and FlyFreely directly whether they check route conformance or parameter changes for ArduPilot.
- Ask one or two ArduPilot fleet operators whether settings drift has caused them a problem (the open question
  behind the whole product).
