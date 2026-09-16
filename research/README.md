# AeroFleet Research — Q1 Publication Readiness

What's actually been done, what's left, and the exact steps to close each gap. This folder is the
evidence trail for every claim in the eventual paper — if a number or argument shows up in the
manuscript, it should trace back to a file in here.

## Status at a glance

| # | Gap | Status |
|---|---|---|
| 1 | Real mass-forensics LLM numbers | **On you** — running on the college PC |
| 2 | Real-world/hardware validation | Architecture confirmed SITL-ready; SITL not yet connected |
| 3 | Statistical rigor (ablation study) | **Done** — real result in `results/` |
| 4 | Formal CBF safety treatment | **Done** — honest math in `cbf_formal_safety.md` |
| 5 | User study (VR/explainability) | Protocol designed; not run (needs real participants) |
| 6 | Related-work section | Draft with real citations in `related_work.md`; needs verification + prose |
| 7 | Target venue | **Done** — *Drones* (MDPI), confirmed Q1, same venue as your precedent paper |
| 8 | Reproducibility package | Mostly already existed; consolidated in `reproducibility.md` |
| 9 | The manuscript itself | Not started |
| 10 | Advisor/faculty review | **On you** — process step, not something I can do |

---

## 1. Real mass-forensics LLM numbers — *your action*

The 1,000-case study, real Ollama backend. Already reduced from 5,000 (see earlier commits) for a
realistic timeline. Command: `python -m scenario_engine.mass_forensics_evaluation`.

**Model roster simplified since the original ~11-22 GPU-hour / RTX-5090 estimate.** The earlier
4-model, ~80GB roster (`llama4:scout`, `mistral-small3.2`, `phi4-reasoning:plus`, `gemma4:12b`)
needed a dedicated GPU server, and on constrained hardware (free-tier cloud GPUs, laptops) caused
real VRAM-thrashing — a model evicted and reloaded between almost every agent call — that
dominated per-case latency far more than raw compute did. Every agent now shares one model,
`phi4-mini-reasoning` (3.8B, ~3.2GB, verified real/pullable), chosen specifically to run on
ordinary hardware — any 8GB+ RAM laptop, CPU-only, no GPU required. This also removes the
methodology deviation the earlier cloud-GPU path needed (`llama4:scout` didn't fit a 16GB card,
so 4 agents ran a substitute model there): every machine now runs the identical real roster, so
there's no secondary/robustness-vs-primary split to report — one number, from wherever it runs.

Given the roster's new footprint, this may not need a cloud GPU at all anymore — running the full
study directly on a laptop CPU is now a real option, not just Kaggle/Colab
(`research/kaggle_mass_forensics_run.ipynb` / `research/colab_mass_forensics_run.ipynb`, both
updated for the single-model roster, still useful if you want to parallelize across multiple
machines via `--only-batches`).

## 2. Real-world/hardware validation — architecture ready, connection not made yet

Two layers exist, one built this session, one now confirmed feasible but not yet done:

- **Unity physics validation** (`unity/AeroFleetValidation/`) — built, not yet run (waiting on your
  Unity Editor install).
- **SITL (Software-In-The-Loop)** — the stronger claim for the paper, and genuinely achievable:
  `aerofleet/hardware/mavlink_link.py`'s own docstring already documents
  `"udp:127.0.0.1:14550" — SITL or a UDP telemetry bridge` as a supported connection format, and
  the mock vehicle tool's docstring explicitly contrasts itself against "a full ArduPilot SITL
  build" — this was always the intended real target, never connected.

**Steps**:
1. Install `dronekit-sitl` (`pip install dronekit-sitl`) — confirmed via research as the practical
   route on Apple Silicon (the Vagrant/VirtualBox approach doesn't work well on ARM Macs). Real,
   prebuilt vehicle binaries, no VM.
2. Run it (`dronekit-sitl copter` or equivalent — check its own `--help`), confirm it's listening on
   UDP 14550, the same port `MAVLinkVehicle`'s docstring already expects.
3. Point AeroFleet at it: create a `Drone` with `link_mode="LIVE"` and connect via
   `MAVLinkVehicle("udp:127.0.0.1:14550", drone_id=...)` — this is the existing code path built for
   a real physical drone, unmodified.
4. Run a real dispatch through the full stack, confirm arm/takeoff/goto commands reach SITL and
   real telemetry flows back through `telemetry_service.py`'s poller.
5. This becomes the paper's "software-in-the-loop validation against ArduPilot" section — a real,
   standard, citable methodology, not a euphemism for "simulation only."

## 3. Statistical rigor — done

`research/ablation_zone_penalty.py` — a real ablation study, actually run (not estimated), against
the real Pune city graph and real DGCA zone data:

- **Real finding #1** (from the first run, kept as an honest result, not hidden): Yellow-zone touch
  rate is ~93-95% across every method, because 5 of Pune's 6 real depots are themselves inside the
  airport's 12km Yellow radius — a genuine geography fact, not a bug, and worth a sentence in the
  paper's discussion (delivery at this city's scale operates almost entirely within a
  permission-required zone, which is itself a finding about the regulatory environment).
- **Real finding #2** (the actual ablation result): on 111 reachable real origin-destination pairs,
  the zone-penalty term in the trajectory optimizer avoided a **Red** zone in **6 cases (5.4%)**
  that plain distance-shortest or energy-only routing would have crossed, with **zero regressions**
  (never made a route worse), at a mean cost of **4.2km** extra distance when it changed the route.
  Modest effect size, honestly reported — worth re-running at higher N (500-1,000 pairs) once you
  have spare compute, to tighten the confidence interval.

**Steps to strengthen further**: increase `N_ADVERSARIAL`/`N_GENERAL` in the script for a tighter
estimate; add Mumbai as a second city for a cross-city robustness check (the script already only
targets Pune).

## 4. Formal CBF safety treatment — done

`research/cbf_formal_safety.md` — the honest version, not the inflated one. Key finding from
actually reading the code rather than assuming: `run_asif_qp()` is **not yet** a textbook CBF-QP
(it has no system dynamics term, so the classical Nagumo/Ames et al. forward-invariance theorem
doesn't yet formally apply) — the document states precisely what *can* be claimed today and the
exact two code changes (a dynamics model, a waypoint-spacing bound) that would unlock the full
theorem.

**Steps if you want the full theorem**: implement the two changes in §4 of that document before
writing the paper's formal claims — or write the honest, weaker-but-correct claim in §5, which is
entirely legitimate and won't get flagged by a CBF-literate reviewer the way an inflated claim
would.

## 5. User study — protocol designed, not run

`research/user_study_protocol.md` — a real, executable within-subjects protocol mirroring the
de Heuvel et al. precedent study's methodology (same outcome types: objective understanding +
subjective trust), N=15-30, with a real analysis plan decided in advance.

**Steps**: check your institution's IRB/ethics requirement first (likely needed even for a small
study — don't skip this). Build the 2D control-condition view (small frontend work, reuses existing
`VRSceneDto` data). Recruit. Run the exact procedure in the doc. Analyze per the pre-registered plan.

## 6. Related work — draft with real citations, needs verification

`research/related_work.md` — organized by the four pillars this paper spans, with real papers found
via live search across CBF-for-UAV-safety, neuro-symbolic/deterministic-gate architectures,
UAV dispatch/scheduling, and LLM-explainability (the last already well-covered by
`docs/VR_RESEARCH_REFERENCES.md`). One paper is in the **same target journal** as this work.

**Steps**: verify every citation's exact details independently (this doc is explicit about which
ones need that pass). Write real connecting prose. Build the comparison table against 4-5 closest
systems — this doc lists exactly which ones.

## 7. Target venue — done

**Primary: *Drones* (MDPI)** — confirmed Q1 (SJR 1.049, IF 4.8), and it's the exact journal your
precedent paper (the HFACS-LLM dataset) was published in, meaning reviewers there are already
primed for this methodology. **Backup: Aerospace Science and Technology** (Elsevier, Q1, IF 6.4) if
the paper ends up leaning harder into classical aerospace/control-theory rigor. Ruled out: IEEE RA-L
(actually Q2, not Q1, despite being a strong venue) and Journal of Field Robotics (Q1 but expects
heavy real-field-deployment data, a poor fit for where this project realistically is).

## 8. Reproducibility package — mostly already existed

`research/reproducibility.md` — `requirements.txt`, `requirements-dev.txt`, `Dockerfile`, and
`docker-compose.yml` were already real and solid. Consolidated the exact command for every
result (done and pending) into one table.

**Steps**: add a `.python-version` pin, a `pip freeze` lockfile once final results are generated,
and commit small summary numbers (not the full gitignored output directories) for every real run.

## 9. The manuscript — not started

Genuinely a separate, multi-week deliverable from everything above. Once #1 (real numbers) and #2
(SITL validation) land, there's enough real material to draft: intro (use the neuro-symbolic
related-work framing), methods (the architecture is already extremely well-documented in code
comments — that's real material to draw from directly), results (the tables already in this
folder), formal safety (§4's honest version), limitations (this whole project already has an
unusually good habit of stating its own limitations in code — mine those comments directly).

**Steps**: once you're ready to start drafting, say so and we can work through it section by
section, the same way we've worked through everything else here.

## 10. Advisor/faculty review — *your action*

Not something I can do. Budget real calendar time for it before any submission deadline.
