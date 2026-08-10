> **SUPERSEDED.** This document describes the original *Space Mission
> Architect* orbital-mechanics invention, which this project pivoted away
> from. The current invention (city-scale drone fleet dispatch) is
> documented in [`PATENT_NOVELTY.md`](PATENT_NOVELTY.md) — that is the
> file to use for any filing or report. Kept here for historical
> reference only.

# Space Mission Architect — Patent Claim Documentation
# For provisional patent application (USPTO)
# Generated from: architecture analysis against 20 peer-reviewed papers
# Date: [INSERT DATE]

## TITLE
Method and System for Formally-Verified Autonomous Space Mission Planning
Using Physics-Anchored Multi-Agent AI with Real-Time Space Traffic Management

## FIELD OF INVENTION
Autonomous aerospace systems, artificial intelligence, astrodynamics,
space mission planning, formal safety verification, multi-agent systems.

## BACKGROUND
Existing space mission planning tools (STK, GMAT, CARA) operate as isolated
single-domain solvers requiring weeks of manual coordination by specialist teams.
No existing system provides: (a) multi-agent AI debate over physics-verified
telemetry, (b) formal mathematical safety certification via Control Barrier
Functions, (c) integrated real-time space traffic management, and (d) structured
legal compliance output in a single automated pipeline.

## SUMMARY OF NOVEL CONTRIBUTIONS
1. First tool-first multi-agent POMDP council with CBF safety certification
2. First STM-integrated pre-council screening with real-time Pc injection
3. First pheromone-decay weighted LLM council convergence algorithm
4. First orbit-phase-aligned async LLM supervisor for council threshold adjustment
5. First software implementation of Koskina 2026 OST Article V(2) AI governance
6. First Transformer warm-start + J2 STM correction hybrid trajectory engine

---

## INDEPENDENT CLAIM 1
### Tool-First POMDP Council with CBF Safety Certification

A computer-implemented method for autonomous space mission planning, comprising:

(a) maintaining a mission state space S comprising orbital Keplerian elements,
spacecraft resource state, safety constraint flags, and mission phase;

(b) executing, prior to any large language model inference call, one or more
deterministic physics tool functions to generate a telemetry payload T_i for
each of N specialist agents, wherein the telemetry payload comprises numerically
computed values including at minimum: trajectory delta-V, fuel mass fraction,
power margin, and collision probability;

(c) routing the telemetry payload T_i as a structured observation O_i to each
specialist agent i, wherein each agent i is assigned a distinct large language
model M_i selected based on the agent's mathematical domain requirements;

(d) receiving from each agent i a structured critique comprising a verdict
selected from {GREEN, YELLOW, RED} and one or more mathematical justification
steps computed from the telemetry payload;

(e) synthesising the agent critiques using a weighted consensus function wherein
agent weights are adjusted according to a pheromone decay rule applied to agents
that repeat constraint flags without new telemetry evidence;

(f) applying a Control Barrier Function gate comprising solving an Active Set
Invariance Filter quadratic program: u_act = argmin||u_des - u||^2 subject to
BC_i(x, u) >= 0 for all i in {1..M}, wherein M >= 12 safety constraints
are evaluated simultaneously across the complete proposed trajectory;

(g) blocking output of any trajectory for which any constraint function h_i(x)
< 0, and triggering an additional planning round with the constraint violation
injected as new telemetry.

### Prior Art Distinction
- Over STK/GMAT: adds multi-agent debate, LLM reasoning, CBF gate
- Over ASTREA (Paper 10): applies CBF to mission planning, not thermal control
- Over AstroReason-Bench (Paper 16): adds CBF gate, legal compliance, STM
- Over LLMSat (Paper 7): adds formal safety gate, multi-agent, real operations

---

## INDEPENDENT CLAIM 2
### STM-Integrated Pre-Council Screening

A method as in Claim 1, further comprising, prior to step (b):

(a) fetching a catalogue of orbital objects from a space tracking data source;

(b) propagating the proposed mission trajectory under J2 perturbation using
Cowell's numerical integration method;

(c) computing, for each catalogued object within a corridor threshold of the
trajectory, a collision probability Pc using the Chen 2016 formula:
Pc = (rA^2 / 2*sigma_x*sigma_y) * exp(-0.5*(lx^2/sigma_x^2 + ly^2/sigma_y^2))
* (1 - exp(-rA^2 / 2*sigma_x*sigma_y));

(d) packaging the computed Pc values, miss distances, and required collision
avoidance manoeuvre delta-V estimates as a structured STM telemetry block;

(e) injecting the STM telemetry block into the observations O_i of the Safety
Officer, Regulatory Advisor, and Mission Operations Coordinator agents prior
to their evaluation;

(f) conditionally activating a Collision Avoidance Planner agent when any
computed Pc exceeds a threshold of 1e-4 in accordance with NASA CARA guidelines.

---

## INDEPENDENT CLAIM 3
### Pheromone-Decay Weighted Council Convergence

A method for multi-round large language model agent consensus comprising:

(a) assigning an initial confidence weight w_i = 1.0 to each agent i in a
council of N agents;

(b) after each council round r, identifying agents that raised the same
constraint flag in round r as in round r-1 without new supporting telemetry
evidence;

(c) reducing the weight of each such agent according to a decay function:
w_i^(r+1) = max(w_floor, w_i^r * decay_factor)
wherein decay_factor is in the range (0.8, 0.95) and w_floor is in the
range (0.2, 0.5);

(d) in subsequent rounds, re-running only agents whose domains correspond
to unresolved constraint flags, not the full council;

(e) terminating iteration when a weighted RED score falls below an
effective threshold adjusted by an asynchronous supervisor module.

---

## INDEPENDENT CLAIM 4
### Orbit-Phase-Aligned Async LLM Supervisor

A method comprising:

(a) maintaining a secondary large language model supervisor operating
asynchronously outside the primary agent debate loop;

(b) receiving round summary data from the primary council via a non-blocking
message queue;

(c) aligning supervisor reasoning window boundaries with mission phase
transitions selected from the set {pre_launch, launch, early_orbit, cruise,
orbit_insertion, operations, deorbit};

(d) generating, for each completed mission phase, a recommendation comprising
an approval threshold adjustment value in the range [-0.2, +0.2];

(e) applying the threshold adjustment to the Architect synthesis policy for
the subsequent mission phase.

---

## INDEPENDENT CLAIM 5
### Koskina 2026 OST Article V(2) AI Governance Output

A method for automated space mission legal compliance assessment comprising:

(a) evaluating a mission plan against five structured compliance domains:
OST Article VI (state responsibility), OST Article IX (planetary protection),
ITU frequency coordination, IADC debris mitigation guidelines, and OST
Article V(2) quasi-astronaut AI status;

(b) for any mission wherein an autonomous AI agent operates beyond real-time
state control, defined as communication one-way delay exceeding 1 second,
automatically flagging OST Article V(2) quasi-astronaut concern status in
accordance with the Koskina (2026) functional AI governance framework;

(c) generating a structured machine-readable compliance report comprising
all five domains with status values selected from {COMPLIANT, AT_RISK,
NON_COMPLIANT} and a proposed human override mechanism specification;

(d) incorporating the compliance report as a mandatory output field of the
mission planning system.

---

## INDEPENDENT CLAIM 6
### Transformer Warm-Start + J2 STM Correction Trajectory Engine

A method for spacecraft trajectory optimisation comprising:

(a) maintaining a pre-trained causal Transformer model trained on a dataset
of at least 100,000 optimal trajectories generated by sequential convex
programming;

(b) at trajectory planning time, generating a warm-start trajectory by
autoregressively inferring control inputs from the Transformer given
initial orbital state, desired final state, and time of flight;

(c) propagating the warm-start trajectory under J2 perturbation using
Cowell's numerical integration to compute terminal position error;

(d) when terminal error exceeds a threshold of 0.001 km, applying State
Transition Matrix iterative correction: delta_v_correction = STM^(-1) *
terminal_position_error, iterated until error < 0.001 km;

(e) feeding the corrected warm-start to a sequential convex programming
solver in place of random initialisation.

---

## DRAWINGS REQUIRED FOR PATENT APPLICATION
1. Figure 1: POMDP council loop block diagram (S, O, M, T, pi)
2. Figure 2: STM pre-screening workflow
3. Figure 3: CBF/ASIF QP gate flowchart
4. Figure 4: Pheromone decay weight evolution over rounds
5. Figure 5: Transformer warm-start + J2 correction pipeline
6. Figure 6: End-to-end system architecture
7. Figure 7: Benchmark results — SpacePlanBench-100 BSS table

## FILING STRATEGY
1. File provisional patent application (PPA) immediately — $320 USD (micro entity)
2. PPA gives 12 months patent-pending status
3. Post arXiv preprint after PPA filing (arXiv does not affect patent rights)
4. Submit to Acta Astronautica within 3 months of PPA
5. Convert to full utility patent within 12 months
6. Consider PCT application for ESA member states, Japan, China
