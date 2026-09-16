# AeroFleet

**A deterministic, formally-verified drone-fleet dispatch and safety system for city airspace,
with an asynchronous LLM advisory layer — architecturally excluded from every safety-critical
decision, not merely outranked by one — confined to explanation, slow-cadence policy tuning, and
post-hoc incident forensics.**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg?style=for-the-badge)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg?style=for-the-badge)](https://fastapi.tiangolo.com/)
[![React 18](https://img.shields.io/badge/React-18-61dafb.svg?style=for-the-badge)](https://react.dev/)
[![Tauri 2](https://img.shields.io/badge/Tauri-2.0-ffc131.svg?style=for-the-badge)](https://tauri.app/)
[![OSMnx](https://img.shields.io/badge/OSMnx-real%20city%20data-7cb342.svg?style=for-the-badge)](https://osmnx.readthedocs.io/)
[![DGCA 2021](https://img.shields.io/badge/Regulatory-DGCA%202021-orange.svg?style=for-the-badge)]()
[![Patent Draft — unreviewed](https://img.shields.io/badge/Patent-Draft%20(unreviewed)-gold.svg?style=for-the-badge)](docs/PATENT_NOVELTY.md)
[![MIT License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)

---

## Executive Summary

**What this actually is, stated first and plainly:** dispatch itself — which drone flies, what
route, whether it's allowed to launch — is decided entirely by deterministic code (a greedy
candidate ranking plus a Control Barrier Function safety gate). There is no learning, no
training, no model fine-tuning anywhere in this system. The LLM council never selects a drone,
never computes a route or battery margin, and never overrides or is consulted by the safety gate.
Its job, in full, is: write a natural-language explanation of a decision that has already
happened, draft a slow-cadence (6-hour) suggestion for a human to review, and auto-investigate a
rejection after the fact. If that sounds like a smaller claim than "AI runs the fleet," that's
deliberate — it's also the true one, and it's the one this codebase actually enforces
structurally rather than by convention. See [Use of LLMs](#the-11-agent-fleet-dispatch-council)
below for exactly where the line is drawn and why.

Real drone-delivery and UTM systems already exist (Zipline, Wing, Matternet). AeroFleet isn't
trying to out-build them on delivery logistics — it targets a narrower, more defensible
engineering question: **how do you get the reasoning quality of an LLM council without ever
trusting an LLM's arithmetic for something safety-critical?**

> LLM agents propose. A deterministic, formally-checkable Control Barrier Function gate
> disposes. Every dispatch action — regardless of which agent or model produced it — is
> independently re-verified before it is allowed to execute. The council's job is never the
> decision itself — it's what happens after: explaining a decision on request, and
> investigating one automatically when the gate had to say no.

**What the council actually decides**, stated plainly because the answer is smaller and more
honest than "AI runs the fleet": nothing about whether a delivery launches — that's the CBF
gate, alone, deterministic, sub-millisecond. What the 11-agent council *does* decide is what
happened and why whenever that gate rejects something. The moment a dispatch is refused, the
**Fleet Incident Forensics Council** auto-triggers — no one asks for it — and each of 7
domain-expert agents (Battery, Airspace, Weather, Comms, Route, Ops, Autonomy Validator)
independently assesses whether *its* domain contributed, citing the actual frozen numbers from
that moment, before a synthesis agent combines their findings into a structured root-cause
report and, only when the evidence supports it, a proposed safety-threshold adjustment that a
human operator must explicitly approve before it ever takes effect. This is the same job a
mixed panel of specialists does after a real incident review — see **Incident Forensics**
below for the design and the real precedent it's grounded in. Worth stating honestly: the CBF
gate's own certificate already names which constraint failed and by how much, so the council's
value here is *synthesizing a coherent narrative and cross-domain judgment call* (a systemic
factor, a recommended action) from that structured data — not discovering a hidden cause the
gate didn't already know. It is a reporting and judgment layer, not a detective story.

This project began as **Space Mission Architect**, a 17-agent LLM council for space mission
planning. Faculty feedback identified two problems: (1) orbital trajectory math needs ~10-digit
precision no LLM can guarantee, and (2) the original model roster included Chinese-origin models
that had to be dropped. The pivot to **city-scale drone fleet dispatch**, suggested by the HOD,
keeps the exact same answer to problem (1) — the CBF gate was always the thing making numerical
guarantees, not the LLMs — and gave a clean opportunity to fix problem (2): every model in the
default roster is now open-weight and non-Chinese (Meta Llama, Mistral AI, Google Gemma,
Microsoft Phi). "City-scale" describes the architecture's design target (multi-city registry,
real street-graph routing, real DGCA zone data per city) — the demo fleet itself is intentionally
small (a handful of depots, ~18 drones) for a runnable local dev environment, not a claim of
tested behavior at real metro-area drone counts.

See [`docs/PATENT_NOVELTY.md`](docs/PATENT_NOVELTY.md) for the full novelty/claims writeup —
an unreviewed student draft, not filed, not reviewed by patent counsel; treat every claim in it
as a novelty argument to be stress-tested, not a settled fact.

---

## Architecture

The LLM council is **never on the dispatch decision or action path** — not "outranked by the
gate," architecturally excluded from it. Dispatch is decided and executed by a single
synchronous, deterministic path; the council only ever runs afterward, asynchronously, and only
if a human explicitly asks for an explanation. See "Restructuring the LLM's Role" below for why.

```
Delivery Order
      │
      ▼
Deterministic Candidate Generation (fleet/dispatch.py)
  — nearest feasible drone by battery margin, payload, ETA
      │
      ▼
Control Barrier Function Safety Gate (safety/cbf_gate.py)   ◄── SOLE AUTHORITY
  — 11 formally-defined constraints, h_i(x) ≥ 0
  — minimally-invasive ASIF-QP correction, not just accept/reject
  — synchronous, sub-millisecond, zero LLM calls anywhere in this path
      │
      ▼
Dispatch Executed (or Rejected) + Digital Twin Updated — response returns instantly
      │
      ┆  (optional, human-triggered, fully decoupled — never awaited by the path above)
      ▼
Council of Experts — Post-Hoc Explanation (agents/council.py, agents/explanation_worker.py)
  — 11 core agents + 5 trigger-based specialists debate the *already-final* decision
  — pheromone-weighted iterative convergence, up to 5 rounds
  — runs on a background worker thread; polled for via GET /orders/{id}, never streamed inline
  — deterministic airspace pre-screen (safety/conflict_screening.py) still trims agent count
    when the pre-screen finds low risk, keeping this cheap even though it's no longer on
    dispatch's critical path
```

If anything fails mid-flight, `fault_tolerance/multi_fault_handler.py` classifies the fault by
type and priority, and `safety/emergency_landing.py` diverts the drone to the nearest
pre-mapped safe zone automatically — the "Contingency Management" requirement from the original
brief, implemented end to end.

### Restructuring the LLM's Role (2026-08-07)

Faculty feedback in a project review meeting was direct: **LLMs cannot be used for real-time
decision-making or action, because inference latency is fundamentally incompatible with it.**
That's correct, and investigating it turned up an actual bug, not just a design smell to
preempt: `dispatch_order`'s council branch called the council's ~80-LLM-call grand-debate
routine **synchronously, with no `await`, inside an `async def` FastAPI handler**. Since nothing
in that call chain ever yielded control, it didn't just make one caller wait — it blocked the
single-threaded asyncio event loop that serves every concurrent request on the server for the
whole debate. Alongside it, the frontend's "watch the council deliberate live" WebSocket path
turned out to be dead code (`broadcast()` had no callers anywhere), and the dispatch button
didn't even call `/dispatch` — only order creation.

The fix, not a patch: dispatch is now unconditionally deterministic and instant — no `use_council`
flag, no LLM branch, nothing to opt out of. The council was fully decoupled into an optional,
async, post-hoc explanation step that runs on a background worker (`run_in_executor`, off the
event loop) and is polled for, never streamed. This also directly strengthens
[`docs/PATENT_NOVELTY.md`](docs/PATENT_NOVELTY.md)'s Claim 1: the council isn't merely
overridable by the safety gate anymore, it's architecturally excluded from the decision/action
path entirely.

---

## Incident Forensics — the actual answer to "what does the AI decide" (2026-08-10)

Async explanation-on-request is real and still there, but on its own it's a thin claim — the
honest description of it is "the council writes a paragraph if someone clicks a button." The
**Fleet Incident Forensics Council** is the substantive version: **auto-triggered**, not
requested, the moment the CBF gate actually rejects a dispatch. Nobody in this loop asks for an
investigation; one starts itself.

Each of 7 domain-expert agents — Battery, Airspace Safety, Weather, Comms, Route, Ops, Autonomy
Validator — independently assesses whether *its* domain contributed to the rejection, citing the
exact frozen numbers (the real CBF certificate, the real dispatch plan) from that moment, not a
re-derived approximation. A synthesis agent combines their findings into a structured root-cause
report, and — only when the evidence actually supports one — a proposed safety-threshold
adjustment. That proposal is never applied automatically: an operator has to explicitly promote
it into the same human-approval queue every other policy change already goes through
(`aerofleet/api/routes/policy.py`).

The taxonomy is methodologically inspired by aviation's Human Factors Analysis and Classification
System (HFACS) — adapted, not copied, since HFACS classifies *human* pilot error and AeroFleet has
no pilot in the loop. Grounded in two real, distinct precedents: **"UAV Accident Forensics via
HFACS-LLM Reasoning"** (*Drones* 9(10):704, 2025 — the same target journal this project's own
research aims at) does single-LLM, HFACS-guided classification over UAV incident narratives,
evaluated against expert-labeled ground truth (macro-F1 0.58–0.76 across 18 categories, 7 models);
separately, the SRE/microservices literature ("Flow-of-Action," RCACopilot-style systems) has the
multi-agent, domain-specialist root-cause-analysis architecture. Nothing found researching this
combines both for a UAV fleet specifically — that combination, plus the human-gated promotion
mechanism, is this project's actual claim (see `docs/PATENT_NOVELTY.md`'s Claim 11).

Evaluated the same way the precedent paper is: `scenario_engine/incident_forensics_evaluation.py`
runs a labeled synthetic-incident set through the real investigation pipeline and reports
per-category precision/recall/F1, macro-averaged — not a single aggregate number. Run it yourself:

```bash
python -m scenario_engine.incident_forensics_evaluation
```

Full design doc: [`aerofleet/agents/incident_taxonomy.py`](aerofleet/agents/incident_taxonomy.py)'s
module docstring has the complete rationale and citations.

---

## The 11-Agent Fleet Dispatch Council

Every agent below shares one model — `phi4-mini-reasoning` (Microsoft, 3.8B, ~3.2GB, reasoning-
tuned) — chosen specifically to run on ordinary hardware (any 8GB+ RAM laptop, CPU-only, no
dedicated GPU server needed). A prior version of this roster split 4 different models across
agents by role; that mixture needed ~80GB combined and, on constrained hardware, caused real
VRAM-thrashing that dominated latency. See `AI_MODEL_SETUP_GUIDE.md` and
`aerofleet/agents/factory.py`'s `DEFAULT_MODEL_MAP`.

| # | Agent | Role |
|---|-------|------|
| 1 | **Fleet Dispatcher** | Lead — synthesises the final decision |
| 2 | **Route Planner** | Path & ETA over the real city street graph |
| 3 | **Battery & Power Engineer** | Energy budget, reserve margin |
| 4 | **Airspace Safety Officer** | Separation, geofence, conflict risk |
| 5 | **Weather Agent** | Wind, visibility, precipitation limits |
| 6 | **Comms / RF Link Agent** | Command & telemetry link budget |
| 7 | **Cost Economist** | Per-delivery economics |
| 8 | **Ops Scheduler** | Depot & battery-swap-station timing |
| 9 | **DGCA Compliance Advisor** | India Drone Rules 2021 / Digital Sky |
| 10 | **Autonomy Validator** | Cross-checks every other agent's numbers |
| 11 | **Payload / Delivery Specialist** | Delivery objectives, release mechanism |

**Specialist agents** (trigger-based — only invoked when a condition in that debate actually
warrants it, not on every dispatch): Conflict Avoidance Planner, Battery Swap Planner, AI
Governance Validator (MAD-BAD-SAD framework), Cyber Security Auditor, Edge Compute Feasibility
Agent. The Cyber Security Auditor in particular is grounded in a real, cited vulnerability
taxonomy (Breda et al. 2023) retargeted at drone C2/GNSS links — GNSS spoofing and unencrypted
command links are genuine, documented BVLOS threat vectors, not a leftover from the project's
original space-mission domain.

**Why route each domain through an LLM at all, rather than just print the number `agents/tools.py`
already computed?** Every core agent above is fed real, deterministic telemetry from `tools.py`
(route distance, battery margin, DGCA zone lookups, cost) — the LLM's job is synthesis and
judgment across that data, not recomputing it. That's a real, honestly-scoped value only for
*non-critical* narrative and cross-domain reasoning (the CBF gate never depends on any of it) — a
fair question to ask, and the honest answer, is whether that synthesis is worth the latency and
inference cost versus a human just reading the raw structured numbers directly. This project's
position is that it's worth it specifically for the two async, non-blocking use cases (explanation,
incident forensics) where a written narrative for a human reader has real value, and not worth it
anywhere the gate itself needs an answer, which is why it never touches the gate at all.

All models are configurable per-agent via `AGENT_MODEL_<ID>` environment variables. Set
`USE_MOCK_AGENTS=true` to run the whole pipeline against a deterministic rule-based backend
instead of live Ollama — used for offline development, CI, and demos where the GPU server isn't
reachable.

---

## Deployment-Flexible LLM Backend

The council's LLM inference layer is switchable at runtime, without restarting the API process,
between three connection modes — configured via the desktop app's **Settings** panel or the
`/api/v1/settings/llm` API:

- **Local Ollama** — inference on the same machine. The Settings panel can detect whether Ollama
  is installed and, on Windows/macOS, download and install it automatically (official installer,
  checksum-verified against GitHub Releases before execution — see
  `tauri-app/src-tauri/src/ollama_installer.rs`), then pull every roster model. Linux gets the
  official `curl | sh` command to copy and run yourself — piping a fetched script into a shell
  unattended was judged a step too far to automate silently.
- **Tailscale / LAN** — inference on a different machine reachable over a private network; enter
  its address once and every subsequent request routes there.
- **API (OpenRouter)** — a hosted API key instead of any local/network Ollama server at all.

Whichever mode is active, the Control-Barrier-Function gate (Claim 1) evaluates identically —
switching inference backend cannot alter or weaken the safety-authority boundary. See Claim 5 in
[`docs/PATENT_NOVELTY.md`](docs/PATENT_NOVELTY.md).

---

## VR Safety View

`tauri-app/src/pages/VRSafetyView.tsx` is a WebXR scene (headset via the in-app "Enter VR" button,
or orbit it on a flat screen) with two modes, because "put drones in VR" on its own isn't a
justification — several consumer drone apps already do that. The two modes are the actual answer
to *why VR specifically, not just a 3D chart*:

- **Live** — the CBF gate's per-drone safety margins as literal 3D geometry: a translucent
  separation envelope around each flying drone, an altitude-ceiling plane, a battery-reserve
  gauge, polled from `GET /api/v1/safety/live-margins` (a read-only supervisory view that never
  influences the actual gate). The justification here is ordinary but real: stereoscopic depth is
  a genuine perceptual advantage over a flat projection for judging *how close* two 3D points
  actually are near a separation boundary — a monoscopic screen collapses exactly the depth axis
  that matters for that judgment.
- **Incident Replay** — the mode built specifically to give VR a job a 2D dashboard can't do as
  well. Every CBF rejection auto-triggers the Fleet Incident Forensics Council (multi-agent LLM
  investigation, see below), which produces a natural-language root-cause narrative. Incident
  Replay pulls that incident's `frozen_context` (`GET /api/v1/incidents/{id}/vr-scene`) — the real
  origin/destination coordinates and the exact CBF constraint violations recorded at rejection
  time — and reconstructs the rejection geometry in 3D, with the council's own summary and
  recommended action shown alongside it. The point: an operator can spatially walk through what
  actually happened and check it against what the LLM *said* happened, rather than trusting a
  paragraph of AI-generated text on faith. That verification role — using VR to audit an AI
  system's claims against ground truth, not just to visualize live telemetry — is the load-bearing
  part of this feature. See Claim 4 in the patent doc for the honest scope of what is and isn't
  novel about that.

---

## City Simulation

`aerofleet/city/graph.py` pulls the **real OpenStreetMap street network** for a configurable city
via `osmnx` — bounded to a ~4km radius around a geocoded centre point (realistic delivery range;
fetching a whole metro area via `graph_from_place` is slow/unreliable against the public Overpass
API), cached to disk, and routes drones along it. This mirrors the real-world proposal that drone
corridors follow existing road right-of-way rather than cut over private property. If OSM/network
access isn't available, it falls back to a synthetic grid city automatically.

Two cities are registered out of the box (`aerofleet/city/registry.py`) — **Pune** and **Mumbai** —
each with its own real airport coordinates seeding a DGCA Red Zone (Pune Airport / Lohegaon;
Chhatrapati Shivaji Maharaj International). Add more by adding an entry to `CITY_REGISTRY`; every
API route accepts a `?city=` query param.

`aerofleet/city/airspace.py` models DGCA-style Red/Yellow/Green airspace zones plus a stack of
**altitude bands** — the CBF gate's geofence constraint checks the full 3D corridor volume, not a
flat 2D no-fly polygon (see Claim 3 in the patent doc). The desktop app's Airspace Map renders this
over **real satellite imagery** (Esri World Imagery) using MapLibre GL, with a toggle that extrudes
depots, drones, and geofences into their actual altitude bands for a genuine 3D corridor view.

---

## Repository Structure

```
aerofleet/
├── agents/           # Council orchestration, roster, tools, specialists
│   ├── council.py         # Pre-screen → debate → CBF gate orchestration
│   ├── factory.py         # 11-agent roster + model routing
│   ├── tools.py            # Deterministic route/battery/geofence/weather/cost/DGCA checks
│   ├── specialist_agents.py
│   ├── local_agent.py      # Live Ollama client (local + Tailscale connection modes)
│   ├── openrouter_agent.py # Hosted-API connection mode, same interface as local_agent
│   ├── runtime_settings.py # Runtime-switchable connection-mode singleton
│   └── mock_agent.py       # Deterministic offline backend
├── city/              # Real OSM street graph + DGCA airspace/altitude-band model
├── fleet/              # Drone/Depot/Battery/Order models, dispatch engine, digital twin
├── hardware/           # Real MAVLink drone connections (ArduPilot/PX4) + telemetry polling
├── safety/             # CBF gate, airspace conflict pre-screen, emergency landing
├── fault_tolerance/    # Multi-fault handler (priority + conflict resolution)
├── explainability/      # Decision-provenance trace graph (reused as-is)
├── event_bus/           # Async priority event bus (reused as-is)
├── api/                 # FastAPI app: orders, routing, fleet, geofence, agents, safety,
│                         #   hardware, settings, ws
└── data/                 # SQLAlchemy models (drones, depots, orders, deliveries, geofences)

scenario_engine/        # YAML scenario → council run → multi-metric evaluator (reused pattern)
tauri-app/               # React 18 + MapLibre GL + react-three-fiber desktop UI (native, Tauri 2/Rust)
│   └── src-tauri/src/ollama_installer.rs  # Windows/macOS Ollama install automation
docs/PATENT_NOVELTY.md  # Full patent claims draft
docs/HARDWARE_SETUP.md  # Connecting real ArduPilot/PX4 hardware
```

**Why this reads as ops software, not "another AI dashboard" or a flight-planner clone**
(Mission Planner / QGroundControl): the UI is organised around the fleet-dispatch decision loop —
Ops Center, Dispatch Console, **Council Room** (async, post-hoc multi-agent explanations), Airspace Map,
**VR Safety View**, Hardware, Scenario Lab, Depot Network, **Settings** — not single-vehicle
waypoint editing. Neither Mission Planner nor QGroundControl has an AI reasoning layer, a formal
safety gate independent of that reasoning, a multi-city fleet-dispatch model, or any
immersive/VR supervisory view — they're single-vehicle waypoint tools; this is a fleet-dispatch
council + safety-gate system that happens to also talk MAVLink to real hardware. Visual language
is a soft off-white "fresh ops console" palette (teal accent, 6-16px rounded corners, single-layer
shadows), not the generic dark-navy-and-electric-blue template most AI products ship with.

**Legacy code removal:** every space-domain-only holdover from the original pre-pivot project has
now been removed — the top-level `src/` v1 Streamlit monolith (~20 files), and every space-domain-only
`aerofleet/` subpackage (`cislunar/`, `core/`, `digital_twin/`, `evaluation/`, `explainability/`,
`knowledge/`, `planning/`, `rl_trajectory/`, `robotics/`, `simulation/`, `ssa/`, `stm/`, `ui/`, plus
the three route files that mounted none of them). Each was checked against a live import trace of
the running FastAPI app before deletion, not assumed dead.

---

## Getting Started

```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Point at your Ollama server (remote box over Tailscale, or local — CPU is fine)
export OLLAMA_HOST=http://localhost:11434
ollama pull phi4-mini-reasoning

# Or skip Ollama entirely for a quick offline demo:
export USE_MOCK_AGENTS=true

uvicorn aerofleet.api.app:app --reload --port 8000
# → http://localhost:8000/docs
```

```bash
# Deterministic decision layer at scale — 3,000+ generated cases, no LLM needed
pytest tests/property/test_dispatch_invariants.py -q -m property

# The LLM agents' own reasoning quality — needs Ollama + the roster models running
python -m scenario_engine.incident_forensics_evaluation
```

(`scenario_engine.runner` still exists but evaluates the council's output against hand-labeled
values from back when the council made dispatch decisions — it doesn't anymore, the CBF gate does,
deterministically, before the council ever runs. See `docs/TESTING_STRATEGY.md` for the full
picture of what's actually worth running and why.)

```bash
# Desktop app — web dev server (view in any browser at http://localhost:1420)
cd tauri-app && npm install && npm run dev

# Native desktop window (requires Rust — https://rustup.rs)
npm run tauri dev
```

> **On an external/non-APFS drive?** If `npm run tauri dev` panics with
> `stream did not contain valid UTF-8`, your filesystem doesn't support macOS extended
> attributes and is shadow-writing `._*` files into Cargo's build output. Redirect the build
> output to your native drive instead: `CARGO_TARGET_DIR=/tmp/aerofleet-tauri-target npm run tauri dev`.

The Airspace Map renders **real satellite imagery** (Esri World Imagery) with live drone/depot/
geofence overlays over Pune and Mumbai, with a 3D toggle that extrudes altitude bands and no-fly
zones for a genuine 3D corridor view — no API key required.

```bash
# Or run everything (Postgres, Redis, API) with Docker instead:
docker compose up --build
```

---

## Real Drone Hardware

Beyond simulation, AeroFleet can connect to and command real ArduPilot/PX4 flight controllers
over MAVLink (`aerofleet/hardware/`) — telemetry polling, arm/disarm, takeoff, guided-mode
routing, full mission upload, return-to-launch, and a fleet-wide emergency-stop kill switch, all
exposed via the desktop app's **Hardware** panel and `/api/v1/hardware/*`. Every command that
originates from the normal dispatch pipeline still passes through the CBF gate first — the
hardware layer executes decisions, it doesn't make them. See
[`docs/HARDWARE_SETUP.md`](docs/HARDWARE_SETUP.md) for connection strings, flight-controller-side
config, and the safety disclaimer that applies to all of this (short version: a safety pilot with
RC override and the flight controller's own failsafes remain mandatory — this software
coordinates the fleet, it doesn't replace them). `tools/mock_mavlink_vehicle.py` lets you exercise
the entire pipeline without real hardware.

### ArduPilot Mission Planner export

AeroFleet doesn't vendor Mission Planner's codebase (a full Windows-native C#/.NET application —
merging it into this Python/TypeScript stack wouldn't build or run as one thing). Instead, an
approved dispatch can be exported as a standard **QGC WPL 110** `.waypoints` file — the same format
Mission Planner and QGroundControl both read — via `GET /api/v1/orders/{id}/mission-planner-waypoints`
or the Dispatch Console's **Export for Mission Planner** button, once the CBF gate has approved the
route (only an approved dispatch has a real route worth exporting). `aerofleet/hardware/mavlink_link.py`
already speaks the exact same MAVLink connection-string format
(`udp:`/`tcp:`/serial) Mission Planner uses, so the two tools can point at the same vehicle. AeroFleet
still makes the only decision that matters (the CBF gate); Mission Planner is downstream
flight-planning/monitoring tooling, not a second decision-maker. See
`aerofleet/integrations/mission_planner.py`.

---

## Decentralized Safety Mesh (D2D)

Every dispatch decision above is centralized — the CBF gate runs server-side against `FleetState`.
That's a real single point of failure: if the central link degrades, a drone in flight has no way
to know where any other drone is. `aerofleet/safety/d2d_mesh.py` adds a decentralized backstop —
drones periodically broadcast position/velocity/heading to nearby peers (modeled on India's
incoming AIS-230 V2V standard's broadcast content and DGCA's existing Remote ID mandate, not on
C-V2X's road-vehicle-only 5.9 GHz spectrum), and a link-state machine falls back to a peer-derived
safety evaluation when the central link degrades past a threshold — using the *exact same,
unmodified* `ControlBarrierFunctionGate`, just fed differently-sourced data. Verified with a real
5,000-trial empirical study (`scenario_engine/d2d_degradation_study.py`): 91.3% verdict-equivalence
between the centralized and decentralized paths.

**On the conflict-catch rate specifically, read this before citing a number.** The
*operationally-relevant* figure is the natural-rate sample: only 5 true conflicts occurred during
the simulated outage window out of 5,000 trials — genuine drone-separation events are rare, which
is realistic, but too few to state a catch-rate with any statistical confidence (60% catch rate,
95% CI a practically-useless [0.23, 0.88]). **We do not currently have a statistically defensible
estimate of the real-world catch rate.** A second, separately-reported number exists specifically
to demonstrate the *methodology* for getting one: importance-sampled trials that deliberately bias
geometry toward near-miss/violation encounters (standard rare-event sampling practice) produce 454
true conflicts and a 79.5% catch rate, 95% Wilson CI [0.76, 0.83] — but that number describes
performance under an artificially adversarial distribution, not expected real-flight performance,
and should never be quoted as the latter. See
[`docs/D2D_MESH_RESEARCH_DESIGN.md`](docs/D2D_MESH_RESEARCH_DESIGN.md) for the full methodology.
Both figures come from the same
unmodified CBF gate; D2D catches 0% with no backstop at all, by construction, in either sample.

---

## Regulatory Framework

Modeled around India's **DGCA Drone Rules 2021** (Digital Sky, Green/Yellow/Red airspace zones,
UIN/UAOP registration, 120m/400ft default altitude ceiling) — chosen as the reference framework
since it's directly citable in an academic report. `city/airspace.py`'s zone model is pluggable;
swapping in FAA Part 107 / Remote ID rules is a config change, not a rewrite.

Pune and Mumbai's Red/Yellow zones are built from `city/restricted_sites.py` — real, named,
publicly-known sites (airports, military installations, BARC Trombay, etc.), not one generic
circle per city. Radii follow DGCA's stated rule distances where the rule gives one (5 km Red /
12 km Yellow lateral band from an airport perimeter; the Indian Navy's own published 3 km
no-fly perimeter); where DGCA hasn't published an exact figure for a site category, a
conservative, clearly-labeled estimate is used. Altitude ceiling drops from the normal 100 m
operational default (kept below DGCA's 120 m legal limit as a deliberate safety margin) to 60 m
inside a Yellow band, exactly matching the DGCA rule — and `dispatch_order` now actually checks
a delivery's real destination against these zones before approving it, rather than assuming
every destination is clear. This is rule-grounded, not a scrape of DGCA's live Digital Sky
platform (not publicly queryable by automated means) — see
[`aerofleet/city/restricted_sites.py`](aerofleet/city/restricted_sites.py) for the full source
notes and honesty caveats per site.

---

## Honesty Note on What's Verified

This is a final-year project pivot built in one focused engineering pass. The backend, council
orchestration, CBF gate, scenario engine, and API are implemented and unit-verifiable; see
[`PROJECT_SUMMARY.md`](PROJECT_SUMMARY.md) for exactly what was run and confirmed working versus
what still needs your own end-to-end pass (especially anything requiring the live Ollama GPU
server, which isn't reachable from every dev environment). No fabricated benchmark numbers are
published here — run the scenario suite yourself and report what you actually measure.
