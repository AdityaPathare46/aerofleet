# Research References — VR Incident Replay & Related Design Choices

Collected while finalizing the VR Safety View's Incident Replay mode (see `docs/PATENT_NOVELTY.md`
Claim 4 and `README.md`'s VR Safety View section). Organized by the specific design claim each
group of papers supports, so each can slot into a related-work section directly. Every entry below
was found via a live search at time of writing (2026-08) — verify access/exact venue details
yourself before citing, since preprint servers and conference proceedings pages change.

---

## 1. VR/AR for verifying AI decisions against ground truth (core justification)

This is the load-bearing citation group: it's what makes "operator checks the council's narrative
against the frozen CBF geometry in VR" a real, published pattern rather than a one-off idea.

- **de Heuvel et al., "Immersive Explainability: Visualizing Robot Navigation Decisions through
  XAI Semantic Scene Projections in Virtual Reality"** (2025).
  [arXiv:2504.00682](https://arxiv.org/abs/2504.00682)
  Closest direct analog to Incident Replay: a VR interface that grounds an RL policy's XAI
  attribution scores in the actual 3D scene so a human can judge whether the robot's stated reasons
  for a navigation decision match the real environment. Their 24-participant study measured
  objective understanding and trust — worth citing both for the pattern and for a methodology to
  borrow if you run a user study on Incident Replay.

- **Xu, Yu, Jonker, et al., "XAIR: A Framework of Explainable AI in Augmented Reality"**, CHI 2023.
  [DOI: 10.1145/3544548.3581500](https://dx.doi.org/10.1145/3544548.3581500) ·
  [arXiv:2303.16292](https://arxiv.org/pdf/2303.16292)
  A general *when/what/how* framework for AI explanations in AR/VR, built from a 500+ person survey
  and expert workshops. Useful for framing *why* Incident Replay's specific choices (what to show,
  when to show it, spatial vs. HUD) are principled rather than arbitrary.

- **"An Exploratory Study on AI-driven Visualisation Techniques on Decision Making in Extended
  Reality"**, OzCHI 2025. [DOI: 10.1145/3726986.3727036](https://doi.org/10.1145/3726986.3727036)
  Directly studies how XR visualization of AI output changes human decision-making — relevant for
  arguing the *decision-quality* benefit, not just comprehension.

- **"Designing for Confidence: The Impact of Visualizing Artificial Intelligence Decisions"**.
  [PMC9263374](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9263374/)
  Not VR-specific, but a solid citation for the general claim that visualizing an AI's decision
  process changes user trust calibration — the premise Incident Replay is built on.

## 2. Depth perception / why stereo VR specifically (Live mode's justification)

- **El Jamiy & Marsh, "Survey on depth perception in head mounted displays: distance estimation in
  virtual reality, augmented reality, and mixed reality"**, IET Image Processing, 2019.
  [DOI: 10.1049/iet-ipr.2018.5920](https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/iet-ipr.2018.5920)
  The standard survey citation for "stereo + motion parallax gives better distance/proximity
  judgment than a flat 2D projection" — the exact claim the README makes about Live mode. Also
  honestly documents the failure modes (depth underestimation indoors, overestimation outdoors,
  screen-distance effects) — cite these as the caveats, don't only cite the headline claim.

- **Vienne, Masfrand, et al., "Depth Perception in Virtual Reality Systems: Effect of Screen
  Distance, Environment Richness and Display Factors"**.
  [ResearchGate](https://www.researchgate.net/publication/339084742) ·
  [Semantic Scholar](https://www.semanticscholar.org/paper/659a4cd7d1266ab20a4c94d4057fe4e993175af2)
  More recent, more nuanced than a pure "VR is better" claim — good for an honest limitations
  paragraph alongside the main justification.

- **"Assessing Depth Perception in VR and Video See-Through AR: A Comparison on Distance Judgment,
  Performance, and Preference"**. [ResearchGate](https://www.researchgate.net/publication/378712589)
  Useful if you ever want to argue VR vs. AR specifically for this use case, not just VR vs. flat 2D.

## 3. AR/VR for UAV/drone safety monitoring and control (positions AeroFleet in its actual field)

- **"SafeSpect: Safety-First Augmented Reality Heads-up Display for Drone Inspections"** (2025).
  [arXiv:2504.16533](https://arxiv.org/html/2504.16533v1)
  Directly comparable system in the same domain (drones) with the same framing (AR/VR *for safety*,
  not just visualization) — the closest prior-art comparison for the patent doc's Claim 4 clearance
  search.

- **"FlightAR: AR Flight Assistance Interface with Multiple Video Streams and Object Detection
  Aimed at Immersive Drone Control"** (2024). [arXiv:2410.16943](https://arxiv.org/html/2410.16943v1)
  Real-time AR for live drone piloting — good contrast case: shows what the *live-telemetry-only*
  version of your Live mode looks like elsewhere, reinforcing that Incident Replay's post-hoc
  verification angle is the differentiator, not "drones in a headset" generally.

- **"Advanced Human Machine Interfaces for Drone"**, ICAS 2024.
  [PDF](https://www.icas.org/icas_archive/icas2024/data/papers/icas2024_1059_paper.pdf)
  AR for airport-tower/UTM-style drone oversight — useful for the broader UTM/airspace-integration
  framing in the introduction.

## 4. Accident/incident reconstruction in VR/AR (frames Incident Replay as a known genre, not novel from scratch)

- **"The role of augmented reality in air accident investigation and practitioner training"**.
  [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0951832020306505)
  Establishes that AR/VR reconstruction of a real incident for human review is an established
  aviation-safety practice — cite this to frame Incident Replay as applying a known, credible
  investigative pattern to a new (AI-decision) context, rather than inventing the concept.

- **"The Challenges of Integrating AI in Aviation Incident-Accident Investigations: A Human-Centric
  Approach"**. [ResearchGate](https://www.researchgate.net/publication/388391633)
  Directly relevant to positioning the Fleet Incident Forensics Council + Incident Replay pairing:
  discusses exactly the tension (AI assistance vs. human-centric investigation authority) this
  project's whole architecture is built around.

## 5. The deterministic safety layer underneath the LLM council (Claim 1, CBF gate)

- **Ames, Coogan, Egerstedt, et al., "The safety filter: A unified view of safety-critical control
  in autonomous systems"**, Annual Review of Control, Robotics, and Autonomous Systems, vol. 7
  (2023). This is *the* standard modern survey citation for Control Barrier Functions as a safety
  filter — cite this for the CBF gate's theoretical grounding rather than any drone-specific paper.

- **"HMARL-CBF: Hierarchical Multi-Agent Reinforcement Learning with Control Barrier Functions for
  Safety-Critical Autonomous Systems"** (2025). [arXiv:2507.14850](https://arxiv.org/pdf/2507.14850)
  Closer to AeroFleet's actual multi-agent + CBF combination than a generic single-agent CBF paper —
  useful comparison/contrast in a system-design section.

## 6. Multi-agent LLM debate/council architectures (Fleet Dispatch Council, Incident Forensics Council)

- **"Multi-Agent Debate Strategies: Survey, Taxonomy, and Challenges"** (2026).
  [arXiv:2607.26212](https://arxiv.org/html/2607.26212v1)
  The current general survey of the multi-agent-LLM-debate literature your council architecture sits
  inside — good for the related-work section's opening paragraph.

- **"Multi-Agent Debate for LLM Judges with Adaptive Stability Detection"** (NeurIPS 2025).
  [OpenReview](https://openreview.net/forum?id=Vusd1Hw2D9)
  Relevant if you want to discuss *when* a council should stop debating/converge — a design
  question AeroFleet's council already answers architecturally (fixed rounds + CBF gate as the real
  authority) but worth contrasting against.

---

## How to use this for a paper

A natural structure, given what's actually built and tested in this repo:

1. **Introduction** — the general problem: LLM outputs in safety-critical multi-agent systems need
   human verification, and verification tooling usually stays flat/textual. Cite group 1.
2. **Related work** — split into (a) XAI/AI-decision visualization in XR (group 1), (b) VR/AR for
   UAV operations specifically (group 3), (c) VR/AR for incident/accident reconstruction (group 4),
   (d) the safety-filter and multi-agent-debate literature your own architecture is built from
   (groups 5–6).
3. **System description** — the CBF gate (Claim 1), the Fleet Incident Forensics Council (Claim 11),
   and the two-mode VR Safety View (Claim 4) — this repo's own docs (`PATENT_NOVELTY.md`,
   `README.md`) already have accurate, non-fabricated technical descriptions to draw from directly.
4. **Evaluation** — this is the one section that needs new work, not just references: a real user
   study (even a small N, e.g. classmates) comparing "read the council's text report" vs. "walk the
   Incident Replay scene" on a task like "spot when the report's claim doesn't match the geometry" —
   the de Heuvel et al. paper (group 1) is a usable template for that study's design.
5. **Honest limitations** — reuse `docs/PATENT_NOVELTY.md`'s own limitations language (Live mode's
   depth-perception caveats from group 2, the prior-art gaps it already flags) rather than
   overclaiming novelty.

None of the above evaluation data exists yet — Section 4 needs an actual study run, not just
citations. Happy to help design and build that once you know how many participants/how much time
you have for it.
