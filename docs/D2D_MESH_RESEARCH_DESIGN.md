# Decentralized Drone-to-Drone (D2D) Safety Mesh — Research & System Design

**Status:** Design document, pre-implementation. Written to be reviewed before
Phase AD (below) is built, and to double as the methods-section skeleton for
a journal submission — see [Target Venue](#target-venue) at the end.

---

## 1. Motivating Research: India's V2V Mandate

The Ministry of Road Transport and Highways (MoRTH) issued a draft
notification in August 2026 for phased mandatory Vehicle-to-Vehicle (V2V)
communication in India:

- **Standard**: AIS-230 — covers radio performance, frequency stability,
  GNSS positioning, cybersecurity, and road-safety application requirements
  for factory-fitted On-Board Units (OBUs).
- **Technology**: 3GPP **Cellular-V2X (C-V2X)**, not DSRC — the MoRTH Task
  Force on Intelligent Transportation Systems explicitly recommended C-V2X
  over the older 802.11p/DSRC standard.
- **Spectrum**: 5.875–5.925 GHz, license-exempted by the Department of
  Telecommunications via G.S.R. 466(E) (June 2026) specifically to enable
  this rollout.
- **Message content**: each vehicle broadcasts speed, position, heading, and
  acceleration to nearby vehicles — India's equivalent of SAE J2735's Basic
  Safety Message (BSM) — enabling early warnings for sudden braking,
  forward-collision risk, unsafe lane changes, and approaching emergency
  vehicles.
- **Timeline**: optional compliance for fitted systems from October 2027;
  mandatory fitment for new category-L/M/N vehicles (two-wheelers through
  commercial trucks) from October 2028.
- **Scope**: V2V is the first phase of a broader Vehicle-to-Everything
  (V2X) / Cooperative-ITS program; V2I (infrastructure), V2P (pedestrian),
  and V2N (network) are slated to follow.

Sources: [Autocar India](https://www.autocarindia.com/auto-features/gadkari-proposes-mandatory-v2v-communication-by-end-of-2026-but-is-it-viable-440095),
[Business Standard — draft notification](https://www.business-standard.com/india-news/govt-issues-draft-notification-for-phased-v2v-communication-systems-126080300822_1.html),
[Business Standard — explainer](https://www.business-standard.com/technology/tech-news/what-is-v2v-india-s-connected-vehicle-system-to-make-roads-safer-from-2028-126080401077_1.html),
[BusinessToday](https://www.businesstoday.in/auto/story/indias-next-road-safety-upgrade-govt-proposes-mandatory-v2v-communication-systems-in-vehicles-from-2028-546969-2026-08-03),
[Deccan Herald](https://www.deccanherald.com/india/explained-government-to-roll-out-vehicle-to-vehicle-communication-by-2026-to-reduce-crashes-3856326).

**Honesty note on scope**: the 5.9 GHz C-V2X band DoT license-exempted is
allocated for *road vehicles*, and DGCA has not authorized UAV use of that
band. This document does not propose that AeroFleet transmit on that
spectrum. What it borrows from the V2V rollout is the *architectural
pattern* — standardized periodic broadcast of kinematic state enabling
peer-local hazard detection without a central coordinator — and applies it
to the regulatory framework that actually does govern Indian UAVs today:
**DGCA's Digital Sky / Remote ID mandate**, which already requires drones to
broadcast identity and position. The D2D layer below is positioned as a
UTM-domain instantiation of the same underlying idea C-V2X embodies for
roads, built on the spectrum/regulatory basis that actually applies to
drones.

---

## 2. System Design Review: Where AeroFleet Is Centralized Today

Before designing an addition, it's worth stating precisely what exists and
where its single point of failure is — this is the actual, current
architecture, not a simplification:

```
Drone (real: MAVLink : simulated: mock_mavlink_vehicle.py)
      │  telemetry (position, battery, link RSSI)
      ▼
DroneLinkRegistry (aerofleet/hardware/telemetry_service.py)
      │  updates the module-level FleetState singleton
      ▼
FleetState (aerofleet/fleet/state.py)  ◄── single source of truth, in-process
      │
      ├──► DispatchEngine.generate_candidates() (aerofleet/fleet/dispatch.py)
      │      — ranks drones using FleetState-derived positions/battery
      │
      ├──► AirspaceScreeningModule.screen() (aerofleet/safety/conflict_screening.py)
      │      — conflict probability against `active_drones`, a FleetState-derived list
      │
      └──► ControlBarrierFunctionGate.evaluate_trajectory() (aerofleet/safety/cbf_gate.py)
             — the sole safety authority (Claim 1(c)-(d), docs/PATENT_NOVELTY.md)
```

**The gap**: every one of those three consumers — dispatch, conflict
screening, and the CBF gate itself — is fed by the *same* server-side
`FleetState` object. If the server process, its network link to a drone, or
the drone's own uplink degrades, there is currently no fallback: a drone in
flight has no way to know where any other drone is, and the formally-verified
CBF gate that is this project's core safety claim becomes *unreachable*
exactly when a mid-flight re-evaluation might matter most (e.g. another
drone deviating from its planned route after dispatch). This is a real gap,
not a hypothetical one — nothing in the current codebase claims otherwise;
`safety/emergency_landing.py`'s contingency handling covers *single-drone*
faults (battery, GPS loss, motor failure) but not *loss of the
fleet-awareness channel* itself.

**A relevant asset already exists, unused**:
[communication_resilience.py](../aerofleet/planning/communication_resilience.py)
is a complete DTN (Delay-Tolerant Networking) store-carry-forward layer with
a `NOMINAL → DEGRADED → STORE_FORWARD → ISOLATED` link-state machine — built
for the original project's satellite inter-satellite-link domain
(`ISOLATION_TIMEOUT_S = 3600.0  # 1 orbit period`) and never ported to
drones. Its state machine is domain-agnostic; only the timeout constants and
the payload type are satellite-specific.

**A second relevant asset**: `cbf_gate.py`'s `evaluate_trajectory()` is a
**pure function of a list of state dicts** — it has no dependency on
`FleetState`, the database, or any network call; the caller is responsible
for building `trajectory_points` (dicts with keys like `separation_m`,
`battery_margin_wh`). This is the single most important architectural fact
this design leans on: **the exact same `ControlBarrierFunctionGate` class,
unmodified, can evaluate safety locally on a drone using only peer-broadcast
data**, with zero changes to the gate itself — only to what feeds it.

---

## 3. Proposed Architecture: D2D Safety Backstop

### 3.1 Principle

The D2D layer is a **backstop, not a replacement**. The server-side,
LLM-council-assisted, centrally-computed CBF gate remains the primary
decision authority under normal conditions (this is also required to keep
Claim 1 of `docs/PATENT_NOVELTY.md` intact — the council still never touches
any decision path, centralized or decentralized). D2D activates only when
the link-state machine determines the central channel is degraded or
unavailable, and even then it only ever *withholds/holds* a drone via the
same CBF formalism — it cannot originate a new dispatch or override a
central approval.

### 3.2 Message Schema — D2D Basic Safety Message (D2D-BSM)

Modeled directly on AIS-230's broadcast content and SAE J2735's BSM, scoped
to what `cbf_gate.py`'s constraints actually need:

| Field | Type | Source constraint(s) it feeds |
|---|---|---|
| `drone_id` | str | — |
| `timestamp_utc` | float | staleness check (message TTL) |
| `lat`, `lon`, `alt_m` | float | `min_separation`, `altitude_ceiling`, `geofence_exclusion` |
| `velocity_mps`, `heading_deg` | float | closest-point-of-approach projection (same math as `conflict_screening.py`'s `_find_conflicts`) |
| `battery_soc` | float | informational only — a drone shouldn't infer another's battery reserve as its own constraint, but it's useful for prioritizing which drone yields |
| `link_state` | enum (`NOMINAL`/`DEGRADED`/`STORE_FORWARD`/`ISOLATED`) | lets a receiving drone know whether the sender itself is centrally-coordinated right now |

### 3.3 Link-State-Gated Behavior

Port `CommunicationResilienceLayer` from `planning/communication_resilience.py`
into a new `aerofleet/safety/d2d_mesh.py`, replacing satellite-specific
constants with UTM-appropriate ones (a drone that hasn't heard from the
dispatch server in, e.g., 30–60 seconds — not "1 orbit period" — should
already be conservative, likely holding position or executing RTL per
existing `emergency_landing.py` logic):

```
NOMINAL        — central link healthy; CBF gate is server-side & authoritative (today's behavior)
DEGRADED       — central link intermittent; D2D-BSM broadcast/receive begins running
                 in parallel as a hot standby, but its verdict is advisory only
STORE_FORWARD  — central link down beyond a threshold; D2D-derived CBF evaluation
                 becomes authoritative for THIS drone until contact is restored
ISOLATED       — no peers heard from either; fall back to existing single-drone
                 contingency handling (emergency_landing.py) — D2D cannot invent
                 safety information it doesn't have
```

### 3.4 Local CBF Evaluation

When in `STORE_FORWARD`, a drone builds its own `trajectory_points` list
from received D2D-BSMs — computing `separation_m` the same way
`conflict_screening.py`'s `_find_conflicts` already does (proximity ×
timing-overlap) — and calls the *same*
`ControlBarrierFunctionGate.evaluate_trajectory()` used server-side. No new
safety math is introduced; the formal guarantee is the same one already
covered by Phase Y's `tests/unit/test_cbf_gate.py`, just fed
decentralized inputs instead of `FleetState`-sourced ones.

### 3.5 Simulation-First Implementation

There is no real drone-mesh radio in this project's hardware today (real
hardware integration to date is MAVLink point-to-point per drone, per
`aerofleet/hardware/mavlink_link.py`). Consistent with how every other
hardware-adjacent feature here has been built and honestly labeled, D2D
broadcast is implemented first in the simulation layer:

- `tools/mock_mavlink_vehicle.py` gains a periodic D2D-BSM emission (UDP
  broadcast/multicast on a local socket, standing in for a real mesh radio).
- A new lightweight `D2DTransceiver` in `d2d_mesh.py` subscribes to that
  socket per simulated drone, maintains a peer table with TTL eviction, and
  exposes `to_trajectory_points()` for feeding the CBF gate.
- The scenario engine (`scenario_engine/`) gets a new scenario type that
  forces `DEGRADED`/`STORE_FORWARD` transitions mid-flight and asserts the
  D2D-derived CBF verdict matches what the centralized verdict would have
  been for the same synthetic conflict geometry — the actual empirical
  result this design would need for a paper (Section 5).

---

## 4. Patent/Novelty Framing

This is additive to, not a restatement of, the existing claims in
`docs/PATENT_NOVELTY.md`. Proposed new independent claim (drafted once
implemented, not yet added to that document):

> A computer-implemented method for maintaining formally-verified UAV
> collision-avoidance guarantees under degraded central-network
> connectivity, comprising: (a) each UAV periodically broadcasting a
> kinematic state message to peer UAVs within communication range; (b) a
> link-state machine classifying central-channel health into a plurality of
> states; (c) upon transition to a degraded state, constructing a
> trajectory-point representation from only peer-broadcast messages received
> directly, without reliance on any centralized fleet-state store; (d)
> evaluating that representation against the same deterministic
> Control-Barrier-Function constraints of Claim 1(c), without modification
> to the constraint definitions themselves, such that the safety guarantee
> is invariant to whether it was evaluated centrally or peer-locally.

The distinguishing claim over prior UTM/DAA (Detect-and-Avoid) literature
would be the **provable equivalence of centralized and decentralized
verdicts** (same gate, same constraints, different data source) — most
existing decentralized UAV collision-avoidance work uses a *different*,
simplified onboard algorithm than the centralized one, creating a
verification gap this design specifically avoids.

---

## 5. What Would Make This Publishable — Honestly Assessed

A Q1 submission needs more than an architecture diagram. The empirical
contribution this design should actually produce, scoped to what's
achievable with simulation (no live Ollama, no real mesh radio, per this
project's standing constraints):

1. **Quantified verdict equivalence**: across N synthetic conflict
   scenarios in `scenario_engine/`, measure the rate at which the D2D-local
   CBF verdict matches the centralized verdict, and characterize the cases
   where it diverges (e.g. a peer's broadcast staleness under packet loss).
2. **Degradation-response latency**: time from central-link loss to a
   drone's link-state machine reaching `STORE_FORWARD` and producing its
   first local verdict, under a modeled packet-loss/latency distribution
   (reuse `communication_resilience.py`'s existing `LinkMetrics` fields).
3. **Comparison against a no-D2D baseline**: with D2D disabled, quantify how
   many synthetic conflicts in a forced-degradation scenario go undetected
   until link restoration, versus caught locally with D2D active — this is
   the actual headline result a reviewer would look for.

None of this exists yet — it's the work Phase AD (below) produces the
scaffolding for. This document is explicit that the paper's contribution is
the *architecture + its measured behavior under simulated degradation*, not
a claim about real-world C-V2X radio performance, which this project cannot
measure without hardware this team doesn't have.

---

## 6. Target Venue

Three real, verified-quartile candidates (impact factors as of the 2026 JCR
release, all Q1):

| Journal | Publisher | 2026 IF | Fit |
|---|---|---|---|
| **Drones** (MDPI) | MDPI | 4.8 (Q1, Aerospace Engineering) | **Recommended primary target.** Directly UAV-scoped, has an active "Urban Traffic Monitoring / UAVs" editorial track, realistic review-cycle expectations for a simulation-based (not flight-tested) contribution, open access. |
| IEEE Transactions on Intelligent Transportation Systems | IEEE | 9.1 (Q1) | Strongest prestige match — explicitly covers V2X/ITS, which is this design's direct inspiration. Stretch target: reviewers here typically expect either real-world field data or a much larger simulation study than a single capstone project produces; realistic as a *follow-up* submission once Section 5's empirical results exist and hardware validation (even partial, e.g. two real drones with an actual radio link) is available. |
| Transportation Research Part C: Emerging Technologies | Elsevier | 7.3 (Q1), CiteScore 14.7 | Second stretch option — very strong fit for the logistics/dispatch angle specifically (it's the venue most associated with UTM-as-logistics-system framing), same caveat as above on empirical depth expected. |

**Recommendation**: target **Drones (MDPI)** for the first submission. It's
a real Q1 venue, the scope match is exact, and its expectations are
calibrated to work like this — simulation-validated architecture with a
clear novelty statement — rather than requiring flight-test data this
project doesn't have. Treat IEEE T-ITS and Transportation Research Part C
as explicit next-paper targets once Section 5's empirical results and any
real two-drone hardware validation exist, and say so directly in this
paper's own future-work section rather than overstating current scope.

Sources: [Research.com — IEEE T-ITS](https://research.com/journal/ieee-transactions-on-intelligent-transportation-systems),
[Research.com — Transportation Research Part C](https://research.com/journal/transportation-research-part-c-emerging-technologies),
[MDPI — Drones IF announcement](https://www.mdpi.com/about/announcements/12262).

---

## 7. Implementation Plan (Phase AD)

Sequenced after Phase AC (fleet-level policy tuning, already planned and
pending), since AC has no dependency on this design and is smaller:

1. `aerofleet/safety/d2d_mesh.py` — port `CommunicationResilienceLayer`'s
   state machine (rename to UTM-appropriate constants), add
   `D2DBasicSafetyMessage` dataclass, `D2DTransceiver` (peer table, TTL
   eviction, `to_trajectory_points()`).
2. `tools/mock_mavlink_vehicle.py` — periodic D2D-BSM emission over a local
   UDP broadcast socket.
3. Wire into `aerofleet/hardware/telemetry_service.py`'s existing poll loop:
   track per-drone link state, transition on missed-heartbeat thresholds.
4. New `tests/unit/test_d2d_mesh.py` — link-state transitions, peer TTL
   eviction, `to_trajectory_points()` output shape, and the verdict-parity
   property (local CBF verdict vs. centralized verdict on identical
   synthetic geometry).
5. New scenario type in `scenario_engine/` exercising forced degradation
   (Section 5's empirical measurements).
6. Minimal frontend: a link-state indicator per drone on the existing Fleet
   Map / Hardware panel — no new page needed.
7. `docs/PATENT_NOVELTY.md` — add the new independent claim from Section 4
   once implemented and tested, following this document's exact template
   (dated restructuring/addition note, as done for Claim 1/2 in Phase AB).
8. `README.md`/`PROJECT_SUMMARY.md` — new phase entry, same honesty
   standard as every prior phase.
