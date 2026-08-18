# AeroFleet — Patent Novelty & Claims Draft

**Status:** Draft for internal review and a final-year-project report. This is a
starting point for a provisional patent application, not a filed patent and
not legal advice. **Have a patent professional or your institution's
Technology Transfer Office (TTO) review this before any filing.**

**Unreviewed student draft — read every claim below as a novelty argument to be stress-tested,
not a settled fact.** No prior-art clearance search beyond the authors' own literature review has
been performed. Two claims in particular (5 and 4 — see "Strongest Claim & Filing Recommendation"
below) rest on engineering patterns (pluggable LLM backends, telemetry visualization in VR/AR)
that are common enough elsewhere that a real clearance search may well turn up prior art
narrowing or eliminating them; they're presented here as honest novelty arguments, not confident
claims.

---

## Title

Neuro-Symbolic Multi-Agent System and Method for Formally-Verified City-Scale
Drone Fleet Dispatch and 3D Airspace Deconfliction

## Field of Invention

Autonomous unmanned aerial systems, artificial intelligence, urban air
mobility / UAS Traffic Management (UTM), formal safety verification,
multi-agent systems, logistics dispatch optimization, extended-reality
(VR/AR) safety visualization, distributed/hybrid large-language-model
inference deployment.

## Background & Prior Art

Commercial drone-delivery and UTM systems already exist — Zipline, Wing,
Matternet, and India-based operators such as Skye Air and ANRA/AirMap-style
airspace-management platforms. **"Drone delivery" itself is not novel.**
None of these known systems, to our knowledge, combine:

1. A multi-agent large-language-model (LLM) "council" that reasons about
   and negotiates operational tradeoffs (route, energy, weather, cost,
   regulatory) in natural language, **with**
2. A deterministic, formally-checkable safety layer that has unconditional
   final authority over every dispatch action, regardless of what any LLM
   agent concluded.

This gap matters because of a specific, well-known failure mode: LLMs are
unreliable at exact multi-digit numerical computation and cannot be trusted
as the sole authority for safety-critical geometric/physical constraints
(minimum separation, battery reserve, geofence boundaries). Existing UTM
systems avoid LLMs entirely and lose the reasoning/negotiation/explanation
benefits; existing "AI dispatch" pitches use LLMs end-to-end and inherit
their numerical unreliability. AeroFleet's architecture is designed
specifically to get both: LLM-quality reasoning over tradeoffs, with
zero trust placed in LLM arithmetic for anything safety-critical.

## Summary of Novel Contributions

1. **Deterministic Control-Barrier-Function (CBF) safety gate with an
   architecturally-excluded LLM council** — the council is not merely
   outranked by the gate, it is not invoked on the dispatch decision or
   action path at all. Every dispatch is decided and (if approved)
   executed by a synchronous, deterministic quadratic-program-based safety
   filter alone; the LLM council only ever runs afterward, asynchronously,
   optionally, and off the request-handling execution context, to explain
   a decision that already happened.
2. **Deterministic airspace pre-screen reducing the cost of that
   asynchronous explanation** — a cheap, non-LLM conflict/geofence check
   runs first; the expensive multi-agent explanation debate (and its
   associated LLM inference cost) is only run with the full agent set when
   the pre-screen finds a real risk above threshold, and never at all
   unless a human explicitly requests an explanation.
3. **Pheromone-weighted iterative council convergence** (ant-colony-inspired):
   agents that repeatedly raise unresolved objections gain deliberative
   weight across debate rounds, while agents whose concerns are resolved
   decay in weight, so the system converges without a fixed round count.
4. **3D altitude-banded corridor geofencing** — airspace exclusion zones are
   represented as a stack of altitude bands rather than a flat 2D no-fly
   polygon, giving the CBF gate a genuine 3D deconfliction constraint and
   allowing priority-based lane assignment (e.g. medical payloads get the
   clearest band) as a form of built-in traffic separation.
5. **End-to-end decision-provenance trace graph** linking every agent's
   vote, the pre-screen result, and the final CBF certificate into a single
   auditable graph — built for the kind of regulator-facing explainability
   that DGCA-style oversight (or any UTM authority) would require before
   trusting autonomous BVLOS dispatch at scale.
6. **Immersive spatial rendering of Control-Barrier-Function safety
   margins** — each of the 11 formally-verified constraints' live numeric
   margin is rendered as literal 3D geometry (a shrinking/growing
   separation envelope, an altitude-ceiling plane, a battery-reserve
   gauge) around each in-flight UAV in a WebXR scene, letting a human
   supervisor perceive proximity to a safety violation spatially rather
   than reading a dashboard number — distinct from prior "drone-in-VR"
   visualization, which shows position/telemetry, not a formal safety
   gate's own constraint state.
7. **Deployment-flexible LLM connection architecture with a
   backend-agnostic safety boundary** — the council's LLM inference layer
   is runtime-switchable between local on-device, LAN/VPN-relayed, and
   hosted-API tiers behind a single interface, while the Control-Barrier-
   Function gate of Claim 1(c)-(d) is provably independent of which tier
   produced a given explanation — switching connection tier cannot alter
   or weaken the safety-authority boundary, reinforcing Claim 1's core
   assertion (that the council is architecturally excluded from, not just
   outranked within, the decision path) at the systems level.

---

## Independent Claim 1 — Deterministic Dispatch Gate with Architecturally-Excluded, Asynchronous LLM Explanation

*(Revised — see "Restructuring Note" below. Earlier drafts of this claim had
the LLM council submit a proposal that the CBF gate re-verified **within the
same synchronous decision**, i.e. steps (c)-(e) ran inline, before step (f).
That is no longer the architecture: the council is not merely overridable by
the gate, it is not invoked on the decision/action path at all. This is a
strictly stronger claim, and the fix that produced it is described below.)*

A computer-implemented method for dispatching an unmanned aerial vehicle
(UAV) to fulfil a delivery order, comprising:

(a) receiving a delivery order specifying an origin, a destination, a
    payload mass, and a priority class;

(b) generating one or more candidate dispatch plans, each candidate plan
    assigning the order to a UAV selected from a fleet based on
    deterministically-computed battery margin, payload capacity, and
    estimated time of arrival;

(c) evaluating the candidate dispatch plan against a plurality of
    independently-defined, formally verifiable safety constraints via a
    Control-Barrier-Function gate, wherein each constraint h_i(x) >= 0 is
    evaluated deterministically, synchronously, and without reference to
    any large-language-model output;

(d) executing the dispatch plan only if step (c) determines that all
    constraints are satisfied, and otherwise withholding execution and
    returning a machine-readable violation report identifying which
    constraint(s) failed and a corrective magnitude;

(e) independently of, and only after, the irrevocable determination made in
    step (d), optionally and asynchronously submitting the already-executed
    (or already-rejected) dispatch plan together with the certificate
    produced in step (c) to a plurality of specialized large-language-model
    agents, each agent associated with a distinct operational domain
    selected from the group comprising: route feasibility, energy/battery
    margin, airspace safety, weather, cost, regulatory compliance, and
    autonomy validation, for the sole purpose of producing a natural-
    language explanation of a decision that has already been finalized;

(f) executing step (e), when invoked, on a separate execution context (e.g.
    a background worker process or thread) from the request-handling
    execution context that performs steps (a)-(d), such that invocation of
    step (e) — including the case where it makes dozens of sequential
    large-language-model inference calls over multiple debate rounds —
    cannot block, be blocked by, delay, or otherwise share a scheduling
    resource with steps (a)-(d);

wherein the large-language-model agents of step (e) receive the outcome of
step (c)-(d) as an immutable input, have no code path by which their output
can alter, veto, delay, or be a precondition for steps (a)-(d), and are
never invoked on the same execution path, request, or scheduling context as
steps (a)-(d) — i.e. the large-language-model agents are architecturally
excluded from, rather than merely outranked within, the decision and
actuation timing budget.

### Restructuring Note (dated 2026-08-07)

This claim was rewritten in response to direct faculty feedback that
large-language-model inference is unsuitable for real-time decision-making
or action due to latency. On investigation this was correct, and pointed at
an actual defect rather than only a design smell: the previous
implementation of `dispatch_order` called the LLM council's grand-debate
routine — an up-to-80-call, tens-of-seconds-to-minutes synchronous
operation — with no `await`, inside an `async def` FastAPI request handler.
Because nothing in that call chain ever yielded control, the call did not
merely make one client wait; it blocked the single-threaded asyncio event
loop that serves *every* concurrent request on the server for the duration
of the debate. The fix removes the LLM council from the dispatch method
entirely (steps (a)-(d) above are now the *only* code path that can command
hardware) and reintroduces the council solely as an opt-in, post-hoc
explanation generator running on a dedicated background worker
(`run_in_executor`-backed, off the event loop), polled for via a status
field rather than streamed inline. The distinction drawn in this claim
between "outranked" and "architecturally excluded" is the direct, literal
embodiment of that fix, not a rhetorical strengthening of the same design.

## Independent Claim 2 — Deterministic Pre-Screen Reducing the Cost of an Asynchronous Explanation Council

*(Revised alongside Claim 1: the pre-screen no longer decides whether a
synchronous debate gates dispatch — under the current architecture nothing
gates dispatch except the CBF gate itself, per Claim 1(c)-(d). The
pre-screen's cost-reduction purpose is preserved by applying it to the
asynchronous explanation step of Claim 1(e), which is the only place a
multi-agent debate still runs.)*

A computer-implemented method for reducing the computational cost of
multi-agent dispatch-explanation reasoning, comprising:

(a) prior to invoking any large-language-model agent for the asynchronous
    explanation step of Claim 1(e), computing a deterministic conflict
    probability between the already-dispatched UAV's route and the routes
    of other active UAVs in the fleet, and a deterministic
    geofence-violation flag against a stored map of restricted airspace
    zones;

(b) comparing the conflict probability to a stored threshold;

(c) invoking the full multi-agent large-language-model explanation council
    of Claim 1(e) only if the conflict probability exceeds the threshold or
    a geofence flag is present, and otherwise generating the explanation
    with a reduced agent set;

whereby large-language-model inference cost is incurred, on the
already-asynchronous explanation path, only in proportion to actual
operational risk rather than on every explanation request — and, per
Claim 1, in no case on the dispatch decision or action path itself.

## Independent Claim 3 — 3D Altitude-Banded Corridor Geofence

A computer-implemented method for representing restricted airspace for UAV
dispatch, comprising:

(a) defining a plurality of altitude bands, each having a floor and
    ceiling elevation above ground level;

(b) associating a two-dimensional exclusion or restriction zone with one
    or more, but not necessarily all, of the altitude bands;

(c) assigning a proposed UAV route to a specific altitude band based on
    the priority class of the associated delivery order;

(d) evaluating airspace-safety constraints against the assigned
    three-dimensional volume (the two-dimensional zone extruded through
    the assigned band), rather than against a flat two-dimensional
    projection of the route;

whereby UAVs assigned to different altitude bands over the same ground
footprint are not flagged as conflicting, providing a form of vertical
traffic separation not present in two-dimensional geofence representations.

*Reference implementation:* `aerofleet/city/airspace.py` (altitude-band
constraint model) and the desktop app's Airspace Map, which renders this
as an actual 3D scene — depots, drones, and geofence zones extruded to
their real altitude/ceiling over live satellite imagery, toggleable
against the flat 2D view — rather than only being a backend constraint.

*Strengthened 2026-08-09:* step (c)'s band assignment is now also a
function of ground position, not priority class alone —
`AirspaceModel.altitude_ceiling_m_at()` returns a reduced 60 m ceiling
inside a Yellow lateral band (versus the normal 100 m operational
ceiling), and `assign_altitude_band()` demotes a route to the highest
band that still fits under whichever ceiling applies at that location.
The two-dimensional zones of step (b) are now `aerofleet/city
/restricted_sites.py`'s curated set of real, named, publicly-known DGCA
Red/Yellow sites for Pune and Mumbai (airports, military installations,
BARC Trombay, etc. — 3 zones for Pune, 7 for Mumbai) rather than one
generic per-city circle, giving step (d)'s "3D volume" a materially more
realistic ground footprint to extrude through.

## Independent Claim 4 — Immersive Spatial Rendering of CBF Safety Margins

A computer-implemented method for presenting the safety state of an
autonomous UAV dispatch system to a human supervisor, comprising:

(a) evaluating, for each of a plurality of in-flight UAVs, a plurality of
    independently-defined Control-Barrier-Function constraints as recited
    in Claim 1(c), producing for each constraint a signed numeric margin
    value h_i(x), wherein a positive value indicates the constraint is
    satisfied and a negative value indicates the magnitude of violation;

(b) mapping a subset of the constraint margins to a spatial geometric
    representation positioned relative to the corresponding UAV's real
    three-dimensional position within a rendered scene, wherein at least
    one constraint margin (a minimum-separation margin) is rendered as a
    volumetric boundary surface whose extent is derived from the margin
    value, and at least one constraint margin (an altitude-ceiling margin)
    is rendered as a bounding plane at a height derived from the margin
    value;

(c) mapping a further subset of the constraint margins, for which no
    direct spatial analogue exists, to a non-volumetric heads-up display
    element positioned adjacent to the corresponding UAV within the same
    rendered scene;

(d) rendering the scene of steps (b)-(c) via a stereoscopic head-mounted
    display in a virtual- or augmented-reality session, such that a human
    supervisor's perceived proximity between their own viewpoint and a
    constraint's boundary surface corresponds to the UAV's actual
    proximity to a safety-constraint violation;

(e) repeating steps (a)-(d) at a polling interval independent of, and
    without altering, the evaluation of Claim 1(c) that gates dispatch
    execution — the rendering is a read-only supervisory display, not an
    input to the safety-authority determination;

(f) alternatively to steps (a)-(e)'s live polling, retrieving a
    previously-frozen constraint-evaluation record associated with a
    specific rejected dispatch decision — comprising the rejected
    trajectory's spatial coordinates, the identity and signed margin value
    of each violated constraint, and a natural-language root-cause
    narrative produced by a multi-agent large-language-model
    investigation of that same rejected decision — and rendering that
    frozen record via steps (b)-(d) alongside the natural-language
    narrative presented as adjacent text within the same session, such
    that a human supervisor can visually compare the spatial rendering of
    the recorded constraint violation against the language model's
    textual claim about what occurred, thereby providing a
    human-verification mechanism for auditing a large-language-model
    output against the deterministic safety record it purports to
    describe, rather than presenting live telemetry alone.

*Reference implementation:* `aerofleet/api/routes/safety.py`'s
`GET /live-margins` endpoint (steps (a)-(e); re-evaluates the same
`aerofleet.safety.cbf_gate` used by Claim 1(c), read-only, against live
fleet telemetry); `aerofleet/api/routes/incidents.py`'s
`GET /{incident_id}/vr-scene` endpoint (step (f); reshapes the
`IncidentReport.frozen_context` and `trigger_detail` populated by the
Fleet Incident Forensics Council — see Claim 11 — into the frozen
coordinates/violations/narrative the replay renders); and
`tauri-app/src/pages/VRSafetyView.tsx` (the WebXR scene, with a Live/
Incident-Replay mode toggle — Live renders separation margin as a
sphere, altitude-ceiling margin as a plane, battery-reserve margin as a
gauge, remaining constraints as HUD panels via `@react-three/xr`; Replay
renders the frozen rejection geometry with violated constraints
highlighted and the council's `root_cause_summary`/`recommended_action`
shown in an adjacent panel).

## Independent Claim 5 — Deployment-Flexible LLM Connection Architecture with an Independent Safety Boundary

A computer-implemented method for operating a multi-agent large-language-
model dispatch council across heterogeneous inference deployments,
comprising:

(a) defining a common interface for submitting a prompt and domain
    context to a large-language-model backend and receiving a structured
    critique, independent of which of a plurality of connection modes is
    active;

(b) providing at least three connection modes implementing the interface
    of step (a): a first mode routing inference requests to a language
    model process executing on the same physical machine as the dispatch
    council; a second mode routing inference requests to a language model
    process executing on a separate machine reachable over a private
    network, the network address configurable at runtime; and a third
    mode routing inference requests to a third-party hosted inference
    API, including translating an internal model identifier to a
    provider-specific model identifier;

(c) selecting, at runtime and without restarting the dispatch council
    process, which connection mode of step (b) is active for subsequent
    dispatch requests, responsive to a configuration change originating
    from a user-facing settings interface;

(d) for the first connection mode, automatically detecting whether a
    required local inference runtime is installed on the host machine,
    and if absent, retrieving and executing an installer for that runtime
    from a designated official source after verifying the retrieved
    installer's cryptographic checksum against a value obtained from an
    independent release-metadata source, without executing any retrieved
    content prior to successful verification;

(e) irrespective of which connection mode of step (b) is active for a
    given dispatch request, subjecting the resulting candidate dispatch
    plan to the Control-Barrier-Function gate of Claim 1(c) before
    execution, wherein the gate's determination is computed identically
    regardless of connection mode and is not a function of, or influenced
    by, which connection mode produced the candidate plan.

*Reference implementation:* `aerofleet/agents/runtime_settings.py`
(runtime-mutable connection-mode singleton), `aerofleet/agents/
llm_backend.py` (mode-dispatching factory), `aerofleet/agents/
openrouter_agent.py` (third-mode implementation with model-id
translation), `aerofleet/api/routes/settings.py` (the user-facing
configuration interface of step (c)), and `tauri-app/src-tauri/src/
ollama_installer.rs` (step (d) — GitHub-Releases-checksum-verified
installer automation, Windows/macOS only; Linux is deliberately excluded
from automation as a documented implementation choice, not a limitation
of the claim).

## Dependent Claims (illustrative)

6. The method of Claim 1, wherein step (f)'s Control-Barrier-Function gate
   further computes a minimally-invasive corrective action via a
   quadratic-program projection (Active Set Invariance Filter) rather than
   a binary accept/reject determination, when a constraint is near-violated.

7. The method of Claim 1, further comprising recording each agent vote,
   the pre-screen result, and the Control-Barrier-Function certificate as
   nodes in a directed decision-provenance graph, exportable for
   regulatory audit.

8. The method of Claim 1, wherein a fault detected during UAV flight is
   classified by type and severity, resolved against a fixed priority
   ordering when multiple faults are concurrently active, and the UAV is
   automatically diverted to the nearest of a plurality of pre-mapped safe
   landing zones selected by geographic proximity, without requiring
   real-time human intervention.

9. The method of Claim 4, wherein the stereoscopic head-mounted display of
   step (d) is replaced with a mobile or wearable device's camera-
   passthrough augmented-reality display, such that the rendered scene is
   composited over a live camera feed of the physical environment rather
   than a fully virtual environment. *(Documented as future breadth — not
   reduced to practice in this filing; see docs/PATENT_NOVELTY.md's AR/VR
   scoping decision.)*

---

## Independent Claim 10 — Decentralized Peer-Broadcast Safety Backstop with Provable Verdict Equivalence to a Centralized Gate

*(Added 2026-08-09. Design and empirical basis: docs/D2D_MESH_RESEARCH_DESIGN.md,
which also documents this claim's connection to India's MoRTH/AIS-230
Vehicle-to-Vehicle mandate as the architectural — not spectral —
inspiration: the claim below targets DGCA's existing Remote ID broadcast
mandate for UAVs, not the 5.9 GHz C-V2X band DoT has licensed for road
vehicles, which DGCA has not authorized for drone use.)*

A computer-implemented method for maintaining a formally-verified UAV
collision-avoidance guarantee under degraded connectivity to a centralized
dispatch server, comprising:

(a) each of a plurality of UAVs periodically broadcasting, to other UAVs
    within direct communication range, a message comprising the
    broadcasting UAV's position, velocity, and heading;

(b) a link-state machine, executing on each UAV, classifying the health of
    that UAV's connection to the centralized dispatch server into a
    plurality of states based on a count of consecutive missed
    server-heartbeat intervals, wherein the classification additionally
    depends on whether a broadcast message under step (a) has been
    received from any other UAV within a threshold recency;

(c) upon the link-state machine of step (b) classifying the connection as
    degraded beyond a threshold, constructing, at the UAV performing the
    classification, a trajectory-point representation derived exclusively
    from broadcast messages received under step (a) directly by that UAV,
    without querying or relying upon any centrally-maintained fleet-state
    store;

(d) evaluating the trajectory-point representation of step (c) against the
    same plurality of independently-defined, deterministic safety
    constraints, executed by the same unmodified safety-evaluation
    routine, as is used to evaluate a centrally-maintained trajectory-point
    representation of the same UAV under nominal connectivity — such that
    a safety determination produced under step (c)-(d) and a safety
    determination that would have been produced centrally for the
    identical underlying geometry are outputs of the identical evaluation
    routine, differing only in which data source populated its input, not
    in which logic evaluated that input;

(e) upon the link-state machine of step (b) classifying the connection as
    healthy, or as degraded but not beyond the threshold of step (c),
    treating the centrally-computed safety determination as authoritative
    and the determination of step (c)-(d), if computed at all, as
    advisory only.

The distinguishing feature over prior decentralized UAV detect-and-avoid
art is **evaluation-routine identity**: step (d) does not describe a
separate, simplified onboard safety algorithm approximating the
centralized one — it is the same routine (`aerofleet.safety.cbf_gate
.ControlBarrierFunctionGate.evaluate_trajectory`, unmodified) applied to a
differently-sourced input, which is what makes the centralized and
decentralized safety guarantees provably, not just empirically,
equivalent whenever step (a)'s broadcast data is not stale. Where it *is*
stale (packet loss, broadcast-interval gaps), the two determinations can
diverge; `scenario_engine/d2d_degradation_study.py` quantifies that
divergence rate directly, rather than asserting equivalence without a
measured bound on it — the honest, falsifiable claim is "provably identical
logic, empirically bounded divergence under realistic loss," not "always
identical." Two figures are reported, not blended into one: a natural-rate
verdict-agreement of 99.68% from the original 5,000-trial run at 20% packet
loss / 1s broadcast interval (`python -m scenario_engine.d2d_degradation_study
--trials 5000 --seed 42`, Phase AD), and — added in Phase AL specifically to
answer a reviewer-grade objection that the original run's true-conflict count
(8 out of 5,000 trials) was too small to put a defensible confidence interval
on the D2D catch-rate metric — an importance-sampled run
(`--stress-fraction 0.5`) that deliberately oversamples near-miss/violation
geometries: 454 true conflicts, 79.5% catch rate, 95% Wilson CI [0.76, 0.83].
The natural-rate and stress-sampled numbers are reported as two separate,
labeled figures because they're drawn from different distributions — see
`scenario_engine/d2d_degradation_study.py`'s module docstring and
`run_study()`'s `metric_3` vs `metric_3b` for exactly how the two are kept
distinct, and both `--trials`/`--seed`/`--stress-fraction` are reproducible
inputs, not one-off numbers — regenerate either at any time.

*Reference implementation:* `aerofleet/safety/d2d_mesh.py`
(`D2DBasicSafetyMessage`, `D2DLinkStateMachine`, `D2DTransceiver` — steps
(a)-(c)), `aerofleet/safety/cbf_gate.py` (step (d), unmodified from Claim
1(c)), `aerofleet/hardware/telemetry_service.py` (step (b)'s link-state
tracking for LIVE drones, driven by `MAVLinkVehicle.last_message_at`),
`tools/mock_mavlink_vehicle.py` (step (a)'s broadcast, currently
implemented as local UDP multicast standing in for a real mesh radio — see
docs/D2D_MESH_RESEARCH_DESIGN.md Section 3.5 for why this is
simulation-first rather than claiming real-hardware validation this
project doesn't have).

## Independent Claim 11 — Auto-Triggered, Structured, Multi-Agent Post-Hoc Incident Forensics with Human-Gated Corrective-Action Promotion

*(Added 2026-08-10. Design and citations: `aerofleet/agents/incident_taxonomy.py`'s
module docstring, reproduced in full in PROJECT_SUMMARY.md's Phase AF entry.
This is the direct answer to "what does the LLM council actually decide" —
not whether to write an explanation paragraph on request, but what went
wrong, in which subsystem, with what confidence, and what to do about it,
triggered the moment the deterministic system produces an anomaly, never
when a human happens to ask.)*

A computer-implemented method for investigating an anomaly produced by an
autonomous UAV fleet-dispatch system, comprising:

(a) automatically initiating an investigation, without any human request,
    upon a deterministic safety-gate rejection, fault event, or emergency
    landing being recorded by the system, the investigation directed at a
    single such anomaly rather than aggregate fleet statistics;

(b) constructing a frozen evidentiary record comprising the exact
    machine-generated certificate, threshold values, and telemetry that
    were in effect at the moment of the anomaly, and providing that same
    frozen record, unmodified, to every step below — such that no
    step re-derives or approximates the state of the anomaly;

(c) submitting the frozen record of step (b) to a plurality of
    specialized large-language-model agents, each agent associated with a
    distinct operational domain, each agent independently producing a
    structured determination comprising a domain-contribution verdict
    selected from an ordered set including at least "contributed," "did
    not contribute," and "insufficient evidence," together with a
    numeric confidence value and a citation to specific values within the
    frozen record of step (b);

(d) submitting the structured determinations of step (c) to a
    synthesizing large-language-model agent, distinct from the agents of
    step (c), which produces a single root-cause narrative, an optional
    recommended corrective action, and, when and only when the evidence
    supports it, a proposed adjustment to a specific numeric safety
    threshold;

(e) upon a human operator's explicit action, and not otherwise,
    converting the proposed threshold adjustment of step (d) into a
    pending review record within the same human-approval queue used for
    threshold adjustments originating by other means, such that a
    threshold adjustment recommended by step (d) and one recommended by
    any other process are subject to identical approval requirements
    before either takes effect;

wherein steps (a)-(d) execute entirely after, and asynchronously from, the
anomaly's already-final resolution, on a separate execution context from
whatever request-handling or control-loop execution context produced the
anomaly, such that no delay in steps (a)-(d) can affect the anomaly's
resolution or any subsequent dispatch decision.

The distinguishing combination over prior art: single-LLM, taxonomy-guided
incident classification over UAV accident narratives is precedented ("UAV
Accident Forensics via HFACS-LLM Reasoning," *Drones* 9(10):704, 2025 —
macro-F1 0.58-0.76 across 18 categories and 7 models against
human-expert-labeled ground truth); multi-agent, domain-specialist
root-cause analysis is precedented in the SRE/microservices domain
("Flow-of-Action," RCACopilot-style architectures). Nothing found in
researching this claim combines both for UAV fleet dispatch specifically,
nor couples the output to a pre-existing, independently-human-gated policy
mechanism the way step (e) does here.

*Reference implementation:* `aerofleet/agents/incident_taxonomy.py` (the
taxonomy of step (c)-(d)), `aerofleet/agents/incident_forensics_worker.py`
(steps (a)-(d), background-worker executed per the same idiom as Claim
1(e)-(f)'s explanation worker), `aerofleet/data/models/models.py`'s
`IncidentReport` (step (b)'s frozen record), `aerofleet/api/routes
/incidents.py`'s `promote-to-policy-proposal` endpoint (step (e), reusing
the exact `PolicyProposal` approval queue of `aerofleet/api/routes
/policy.py` rather than introducing a second one). Currently live-triggered
only from step (a)'s safety-gate-rejection case
(`aerofleet/api/routes/orders.py`'s `dispatch_order`); the fault-event and
emergency-landing trigger cases are implemented in the taxonomy and worker
but not yet wired to a live signal, since the underlying fault-detection
modules (`aerofleet/fault_tolerance/multi_fault_handler.py`,
`aerofleet/safety/emergency_landing.py`) are themselves not yet connected
to the live dispatch/telemetry path — stated directly, not implied, since
a claim should describe what's built, not what's merely designed.

## Strongest Claim & Filing Recommendation

**Claim 1 is the strongest and most defensible claim.** Its core assertion —
that the LLM layer is structurally incapable of being the final safety
authority, by construction rather than by policy — is a concrete systems
claim that prior art (pure-LLM dispatch demos, and pure-deterministic UTM
systems that don't use LLMs at all) does not combine. **Claim 11 is the
second-strongest** — it's the claim with the most direct, real-world
precedent to distinguish from precisely (a 2025 single-LLM UAV-forensics
paper in the same target journal, plus a distinct multi-agent-RCA
literature from a different domain), which cuts both ways: easier to
explain why it's novel in a viva, but also the one most likely to draw a
"isn't this just X plus Y" question — the honest answer is yes, and the
claim is the combination plus the human-gated promotion mechanism of step
(e), not either half alone. **Claim 10 is the third-strongest, and
arguably the most novel of the set** — decentralized UAV detect-and-avoid
is well-trodden prior art on its own, but claiming *evaluation-routine
identity* between the centralized and decentralized paths (not just "a
similar backup algorithm exists") is a narrower, harder-to-design-around
claim, and it's the one backed by a direct, falsifiable measurement
(`scenario_reports/d2d_degradation_study_20260809_171005.json`) rather
than an architectural assertion alone. **Claim 5** reinforces Claim 1 at a
different layer: it doesn't just assert the safety gate is independent
once, it asserts that independence survives an axis of variation (which
inference backend produced the proposal) that most comparable systems
don't even expose as a runtime choice. Flagged honestly as the **weakest
claim of the set on novelty grounds**: pluggable/runtime-swappable LLM
backends are now table stakes in most agent frameworks (LangChain and
similar already expose this as a config choice), so the actual novel
kernel here is narrow — that the *safety boundary specifically* is proven
invariant across that swap, not the swap mechanism itself, which is
unlikely to be patentable alone. **Claim 4** is the most visually
compelling for a demo/viva. Step (f) (Incident Replay) is the part worth
defending on its own merits: it's not "drones plotted in VR" — the thing
several consumer drone apps already do, and the thing a live-telemetry-only
version of this claim would reduce to — it's using VR's spatial affordance
specifically to let a human check an LLM's natural-language claim against
a frozen deterministic record, which is a narrower and more defensible
combination than "safety data in a headset." Steps (a)-(e) (Live mode)
remain the weaker half of the claim on their own: "formal-safety-gate-as-
3D-geometry" is distinct from ordinary telemetry visualization, but that
alone should still be argued carefully against any prior AR/VR
drone-monitoring art a clearance search turns up. Treat (a)-(e) as a
strong demo feature and a claim that needs that search before relying on
it, and treat (f) as the more defensible half — though still unproven
until the same search is done for AI-output-verification-in-VR/AR prior
art specifically (a smaller, newer literature than drone AR/VR generally,
but not zero — surgical and industrial-inspection VR review tools use a
similar pattern outside the UAV/LLM context).

Recommended next steps:
1. Have this reviewed by a patent professional or your institution's TTO
   before any filing — claim language above is illustrative, not
   attorney-drafted.
2. If filing a provisional application, Claim 1 alone is likely sufficient
   to establish a priority date; Claims 2-3, 4, 5, 10, 11, and the
   dependent claims can be folded in on the non-provisional filing.
3. Document the specific prior-art comparison (Zipline/Wing/Matternet
   patents and public UTM literature for Claims 1-3; consumer drone-AR
   apps and enterprise XR-monitoring platforms for Claim 4 steps (a)-(e),
   plus surgical/industrial VR-review and AI-explainability-visualization
   literature for step (f) specifically; multi-cloud
   LLM orchestration frameworks for Claim 5; decentralized/cooperative UAV
   detect-and-avoid literature, and India's AIS-230 V2V standard as the
   design inspiration to distinguish from rather than infringe, for Claim
   10; the HFACS-LLM UAV-forensics paper and SRE/microservices multi-agent
   RCA literature named directly in its own text, for Claim 11) formally
   before filing — this document's prior-art section is a starting point,
   not a clearance search.
