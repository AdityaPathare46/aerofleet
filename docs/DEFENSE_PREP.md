# AeroFleet — Defense Prep

Hard questions, honest short answers, said first before anyone has to ask them. Organized from
most fundamental (problem statement) to most superficial (presentation). Say the answer plainly —
none of these need hedging beyond what's written; the honesty *is* the defense.

---

## Tier 1 — Problem statement / ideology

**Q: Is this actually an AI project, or a software-engineering project with an LLM bolted on?**
> Fair question, and the honest answer is: the safety-critical engineering (CBF gate, dispatch,
> D2D mesh, MAVLink layer) is classical controls/CS, not AI, and there is no learning or training
> anywhere in the system — every model is used purely for inference. The AI contribution is
> narrower: a structural proof that an LLM layer can be given real reasoning responsibility
> (explanation, policy tuning, root-cause synthesis) while being architecturally incapable of
> ever making or influencing a safety decision. That's a systems-design claim about *how to safely
> deploy* LLMs next to a safety-critical system, not a claim about a new learning algorithm — and
> it's stated that way on purpose, not oversold as something it isn't.

**Q: What does the AI actually decide?**
> Nothing about whether a delivery launches. That's the CBF gate alone, deterministic,
> sub-millisecond, zero LLM calls. The LLM council writes an explanation of a decision that
> already happened, drafts a policy-tuning suggestion every 6 hours for a human to approve, and
> auto-investigates a rejection after the fact. Say this before being asked — it heads off the
> follow-up.

**Q: Why call it "neuro-symbolic"? Isn't that a stretch?**
> We've moved away from that framing for exactly that reason. What's actually here is a
> deterministic symbolic safety gate with an LLM advisory layer kept behind a hard architectural
> boundary — closer to "guardrailed LLM agent system" than the tighter coupling "neuro-symbolic"
> usually implies in the literature (differentiable logic, neural-to-symbolic program synthesis).
> We call it a hybrid deterministic-safety + async-LLM-advisory architecture now.

**Q: The project pivoted from space missions to drones, and has gone through a dozen "phases" —
isn't this just reactive patching rather than a coherent design?**
> Each phase was a direct response to a specific, named piece of feedback — that's traceable and
> honest, not hidden. The alternative — not responding to real feedback, or quietly absorbing it
> without documenting why — would be worse. What ties it together is the one constraint that
> never moved across any phase: the safety gate's authority. Everything else (D2D mesh, incident
> forensics, multi-worker support) is additive capability around that fixed point, not a
> different architecture each time.

---

## Tier 2 — Architecture

**Q: Why 11 agents? Couldn't 3 do the same job?**
> Possibly — that's a fair simplification argument. The current roster maps each agent to a real
> domain a human reviewer panel would also have (route, energy, weather, comms, cost, ops,
> compliance, cross-check). The honest tension: several agents reason over numbers `tools.py`
> already computes deterministically, so their value is narrative synthesis, not new information.
> We think that synthesis is worth it for the two async, non-blocking use cases where a human is
> going to read prose anyway — but a leaner roster is a legitimate next iteration, not a claim
> we're precious about.

**Q: Does the Incident Forensics Council actually discover anything, or just restate the CBF
certificate's violations list in prose?**
> Mostly the latter, honestly — the certificate already names which constraint failed. The
> council's real value is cross-domain judgment: a systemic-factor note, a recommended action, and
> a *proposed* policy change, none of which the certificate itself produces. It's a synthesis and
> judgment layer, not a root-cause discovery engine, and we describe it that way now rather than
> implying detective work that isn't happening.

**Q: "City-scale" — how many drones has this actually been tested with?**
> The architecture (multi-city registry, real per-city street graphs and DGCA zone data) is
> designed for city scale. The running demo fleet is intentionally small — a handful of depots,
> under 20 drones — for a local dev environment. No load test at real metro-area drone counts has
> been done. Said plainly if asked, not left implied by the name.

---

## Tier 3 — Scientific / statistical rigor

**Q: What's the real D2D conflict-catch rate?**
> We don't have a statistically confident answer yet. The natural-rate sample — the operationally
> realistic one — only produced 5 true conflicts out of 5,000 trials (60%, but a 95% CI of
> [0.23, 0.88], too wide to state a number with confidence). We built an importance-sampled
> variant that deliberately biases toward near-miss geometries to get a tight interval (79.5%,
> CI [0.76, 0.83]) — but that number describes an artificially adversarial distribution, not
> expected real-flight performance, and we say so directly rather than letting the tighter number
> stand in for the one we don't actually have.

**Q: Is the incident-forensics evaluation dataset independently verified?**
> No — the 12-entry labeled set was authored by the same team building the system being
> evaluated. No second annotator, no inter-rater agreement statistic. A real submission would need
> that; this is a first-pass evaluation harness, presented as such.

**Q: Has this actually been run against real LLMs, or only the mock backend?**
> Both, but unevenly — most development and testing used `USE_MOCK_AGENTS=true` because no GPU
> was reachable during most of the build. Every legitimate live LLM path has been spot-checked
> against real models at least once; `docs/GPU_LIVE_TESTING_GUIDE.md` is the file we use to run a
> comprehensive live pass, and its results — including any live-model accuracy drop versus the
> mock baseline — get reported honestly either way.

---

## Tier 4 — Business viability

**Q: Would a real drone operator actually pay for this?**
> The safety-gate and D2D-mesh engineering, yes — that's genuinely deployable value regardless of
> the LLM layer. The LLM layer specifically (explanations, incident narratives) has no regulatory
> standing — DGCA won't accept an LLM-generated report as an official filing, it's advisory
> reading for an internal ops team. Whether that's worth recurring GPU/API cost is a real open
> question we don't oversell an answer to.

**Q: What's the actual moat here — couldn't a competitor copy the DGCA zone data in a week?**
> Yes, honestly — the curated site data is real and useful for credibility, not a technical moat.
> The more durable claim is the architectural pattern (proven safety-boundary independence across
> LLM backend, across degraded connectivity, across worker topology) — that's the part that's
> actually hard to copy quickly and the part the patent draft focuses on.

---

## Tier 5 — Patent

**Q: How confident are you in the patent claims?**
> Unevenly. Claim 1 (the safety-boundary exclusion) and Claim 11 (auto-triggered forensics with
> human-gated promotion) are the strongest — narrow, falsifiable, and distinguishable from the
> nearest real prior art we found. Claim 5 (swappable LLM backend with an invariant safety
> boundary) is the weakest — backend-swapping itself is common in agent frameworks now; the
> narrower kernel (the *boundary* proven invariant across the swap) might survive a clearance
> search, the swap mechanism alone wouldn't. None of this has been through an actual clearance
> search or patent counsel — we say that upfront rather than waiting to be asked.

---

## The one-sentence version, if time is short

*"AeroFleet is a deterministic, tested drone-dispatch and safety system with an LLM layer that's
structurally forbidden from ever making a safety decision — the LLM explains, drafts policy
suggestions, and writes incident reports, always after the fact, always for a human to read or
approve, and we can point to the exact code boundary that enforces it."*
