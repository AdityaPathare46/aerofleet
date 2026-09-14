# Related Work — Draft

A structured comparison against the actual current literature, organized by the four pillars
AeroFleet's contribution spans. Every paper below was found via a live search (2026-09) — **verify
exact venue/page details yourself before citing**, the way `docs/VR_RESEARCH_REFERENCES.md` already
instructs for its own citation list, since preprint servers and journal listings change.

## 1. Neuro-symbolic / deterministic-gate architectures for safety-critical AI

This is the pillar AeroFleet's central claim (Claim 1: the LLM is "architecturally excluded, not
just outranked" from the decision path) needs positioned against most carefully — it's the paper's
actual novelty claim, so related work here has to show genuine gap, not just adjacency.

- **"A Neuro-Symbolic Framework for Ensuring Deterministic Reliability in AI-Assisted Structural
  Engineering: The SYNAPSE Architecture"** (MDPI *Buildings*, 2075-5309/16/3/534). The closest
  direct architectural parallel found: a deterministic reliability layer gating an AI component in
  a different safety-relevant domain (structural engineering, not UAVs). Cite this as convergent
  evidence the "deterministic-decides, AI-explains" pattern is a real, emerging architectural
  answer to LLM-reliability concerns — not unique to AeroFleet's domain, which is a *stronger*
  framing than claiming total novelty of the pattern itself. AeroFleet's specific contribution is
  applying it to real-time UAV dispatch with a real regulatory-compliance layer on top, not
  inventing deterministic-gate-plus-LLM as a category.
- **"AIVV: Neuro-Symbolic LLM Agent-Integrated Verification and Validation for Trustworthy
  Autonomous Systems"** (arXiv:2604.02478) and **"ATA: A Neuro-Symbolic Approach to Implement
  Autonomous and Trustworthy Agents"** (arXiv:2510.16381) — both general neuro-symbolic
  trustworthy-agent frameworks; useful for the "why not just trust the LLM" framing.
  One search result specifically named a **"Sentry"** pattern — "a deterministic, non-LLM hard gate
  that evaluates residuals against calibrated conformal bounds, with samples forwarded to LLM
  agents only when bounds are violated" — track down and read the source paper directly (not fully
  identified in the search snippet); if accurate, it's close enough to AeroFleet's CBF-gate-first
  design to warrant a direct comparison paragraph.
- **Load-bearing citation for the core thesis**: one search result stated LLMs "should not be
  trusted for autonomous decision-making in deterministic domains beyond approximately 19-31
  steps" and that safety-critical deployments need tool-based verification for multistep reasoning.
  **Find and verify the primary source for this claim before citing it** — if it holds up, it's a
  direct, quantified justification for exactly the architectural choice AeroFleet's Claim 1 makes,
  and belongs in the introduction, not just related work.

## 2. UAV fleet dispatch / scheduling (multi-agent and LLM-based)

- **"Traffic-Predictive Drone Scheduling: Day-Ahead Synchronization of Mobile Depots and Parallel
  Aerial Sorties in Urban Airspace"** (*Drones* 10(6):461, 2025, DOI: 10.3390/drones10060461) —
  published in the same target journal as AeroFleet's own precedent paper. Read this one closely;
  a direct, same-venue comparison table (their dispatch objective/method vs. AeroFleet's CBF-gated
  dispatch) is exactly the kind of "compared to what" evidence a reviewer at the same journal will
  expect to see addressed.
- **"UAV-MARL: Multi-Agent Reinforcement Learning for Time-Critical and Dynamic Medical Supply
  Delivery"** (arXiv:2603.10528) — directly comparable use case (medical priority delivery, same as
  AeroFleet's `MEDICAL` priority class) but a pure MARL approach with no deterministic safety layer
  — a genuine, citable contrast for why AeroFleet's hybrid architecture exists.
- **"MultiUAV-Plat: An LLM-Oriented Platform, Benchmark and Framework for Multi-UAV Collaborative
  Task Planning"** (arXiv:2606.31073) and the general UTTUT/P³ factor-graph multi-agent LLM
  planning line of work — useful for positioning AeroFleet's 11-agent council against other
  LLM-multi-agent UAV planning systems, with the key differentiator being that AeroFleet's council
  never plans/decides, only explains post-hoc.
- **"UAVBench: An Open Benchmark Dataset for Autonomous and Agentic AI UAV Systems via
  LLM-Generated Flight Scenarios"** (arXiv:2511.11252) — relevant to the *methodology* comparison
  for the property-based/mass-forensics evaluation approach (§3 below), not just as a dispatch
  system.

## 3. Control Barrier Functions for UAV safety

Directly relevant to `research/cbf_formal_safety.md`'s own claims — this is the literature that
would immediately notice if the CBF treatment overclaims.

- **"Safe multi-agent drone control using control barrier functions and acceleration fields"**
  (*Robotics and Autonomous Systems*) — multi-agent CBF, closest match to AeroFleet's fleet-level
  (not single-vehicle) safety framing.
- **"Collision Avoidance and Geofencing for Fixed-wing Aircraft with Control Barrier Functions"**
  (arXiv:2403.02508) — geofencing via CBF is *exactly* AeroFleet's `geofence_exclusion` constraint;
  compare their formal treatment directly against `research/cbf_formal_safety.md`'s §1 to make sure
  AeroFleet's own citation of Ames et al. (2017) is applied the same way this paper applies it.
- **"UAV Obstacle Avoidance Algorithm Based on Model Predictive Control and Control Barrier
  Functions"** (ScienceDirect, 2025) — MPC+CBF hybrid, useful contrast since AeroFleet's
  `run_asif_qp` is CBF-only, no MPC horizon.
- **"Safe Autonomous UAV Target-Tracking Under External Disturbance, Through Learned Control
  Barrier Functions"** (*Robotics* 14(8):108, 2025) — a *learned* CBF, worth noting as a possible
  future-work direction (AeroFleet's `h_i` functions are all hand-specified, not learned).

## 4. LLM explainability / XAI in VR (already covered)

`docs/VR_RESEARCH_REFERENCES.md` already has a real, carefully-built citation list for this pillar
(the de Heuvel et al. and XAIR papers especially) — reuse that list directly rather than
re-researching it; it's already at the standard this document is aiming for elsewhere.

## What's still missing before this is submission-ready

This is a source list with framing notes, not prose. The actual related-work section needs:
1. Every citation above independently verified (exact author list, venue, page numbers, publication
   date) — none of this should be cited from a search snippet alone.
2. Real prose connecting each cluster to AeroFleet's specific contribution, not just adjacency.
3. A comparison table (method / decision layer / safety mechanism / evaluation scale) against the
   ~4-5 closest systems (the *Drones* dispatch paper, the SYNAPSE architecture, one CBF-for-UAV
   paper, one MARL dispatch paper) — reviewers read tables before they read paragraphs.
