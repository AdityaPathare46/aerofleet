# Testing Strategy — How We Actually Know This Works

Three genuinely different questions get asked as one ("does the app work / are the agents good /
how do we test something with VR in it"), and they need three different answers. Conflating them
is how you end up with an impressive-sounding test count that doesn't actually prove anything.

## 1. Does the deterministic decision layer make correct calls? — automated, ~3,000+ cases, no LLM

`tests/property/test_dispatch_invariants.py`. This is the "1000 cases, checked automatically"
suite. It does **not** reuse `scenario_engine/{schemas,evaluator,runner}.py` — that machinery
evaluates the council's `run_grand_debate()` output against hand-labeled numeric expected values
(`eta_minutes`, `cost_usd`, `cbf_all_pass`...), which was correct when the council still made
decisions. It doesn't anymore: `council.py`'s own docstring is explicit that `run_grand_debate()`
only ever runs as a **post-hoc explanation** of a decision the deterministic CBF gate already made
(`aerofleet/api/routes/orders.py`). Scaling the legacy suite up to 1000 cases would have been 1000
tests of a decision-making role the council no longer has — a real finding, not a stylistic choice,
surfaced while building this.

What this suite checks instead: real **properties** that must hold regardless of implementation —
not "recompute the expected value with the same code and compare" (circular), but invariants like:

- A destination inside a real, named DGCA red zone (`aerofleet/city/restricted_sites.py`) must
  always be rejected, specifically for the geofence reason.
- An unobstructed, light dispatch must still get approved (proves the gate isn't just rejecting
  everything to trivially satisfy the property above).
- Payload above the real configured ceiling must always be rejected, independent of destination.
- The identical input dispatched twice must produce the identical verdict (no hidden randomness).
- The CBF gate must stay fast (a real performance regression guard, not just a correctness one).

Every destination is a real, distinct point — generated as small offsets from real depots, then
classified RED/YELLOW/GREEN by the same `AirspaceModel.zone_at()` the app itself uses, against
real restricted-site data. Last real run: **3,072 generated cases** (761 genuinely RED, 402
green-light, 120 overweight) — not a chosen round number, whatever the real city data produces.
No LLM involved, no GPU needed, runs in well under a minute:

```bash
pytest tests/property/test_dispatch_invariants.py -q -m property
```

**A real finding from the first full run, worth knowing regardless of testing:**
`aerofleet/api/routes/orders.py`'s `create_order` snaps whatever destination is requested to the
nearest routable graph node *before* anything downstream — the CBF gate included — ever evaluates
which zone it's in. The first run of this suite, before the generator accounted for that, showed
21 apparent "red-zone destination was approved" failures; each one was the real system correctly
evaluating a *different* point than the one requested — in one traced example, a destination
genuinely inside a real DGCA red zone snapped to a routable node **116 meters away**, in a YELLOW
zone, and the geofence check ran against that snapped point instead. The generator now labels
cases by the same snapped point the real pipeline checks, so the suite's ground truth is accurate
— but whether *snap-then-check* is the right product behavior for a delivery genuinely requested
into a red zone is a separate, real question this surfaced, not something to decide unilaterally
here. Two honest options: keep it (the drone only ever actually flies to the snapped, safe point,
so arguably nothing unsafe happens) or add an explicit check against the raw requested point too,
rejecting upfront when *that* point is restricted even if the nearest road node isn't. Worth a
deliberate decision, not a snap judgment either way.

## 2. Are the LLM agents themselves reasoning well? — the part that actually needs real models

This is the only part of "are the AI models working nicely" that a deterministic test can't answer,
because it's the only part where an LLM's judgment is actually in the loop for something a human
reads. `scenario_engine/incident_forensics_evaluation.py` already exists for exactly this (built
in an earlier phase, easy to miss) — a **labeled evaluation harness** for the Fleet Incident
Forensics Council, methodology borrowed directly from a real precedent paper ("UAV Accident
Forensics via HFACS-LLM Reasoning", *Drones* 9(10):704, 2025): a set of incidents with known
ground-truth contributing factors, scored per-category with precision/recall/F1, macro-averaged —
not one aggregate number, which would hide a model that's great at one factor and useless at
another.

```bash
python -m scenario_engine.incident_forensics_evaluation
```

**Read the module docstring before citing a number from this.** Run with `USE_MOCK_AGENTS=true`
(no GPU needed), it's a pipeline sanity check only — the mock backend's domain assessment is a
regex over CBF margin values, so it scores perfectly *by construction* on the factors that map
to a margin, and always returns UNCERTAIN on the two that don't (`routing_navigation`,
`cross_check_anomaly`), which the harness correctly excludes from scoring rather than faking a
verdict for. **The only number worth writing down anywhere is from re-running this against a real
Ollama backend** — unset `USE_MOCK_AGENTS`, make sure the 4 roster models are pulled (see
`docs/COLLEGE_PC_TEST_RUNBOOK.md`), then run the same command. That's where a language model's
actual judgment is being scored, the same way the precedent paper's number was.

12 labeled incidents today in the base script — a real, honest starting set, not artificially
padded to look like more. Real LLM inference makes each one 8 sequential model calls (one per
domain factor plus one regulatory call, across 4 different models), so there's no honest way to
make this "1000+ cases" *in an evening* without either faking the labels or a GPU that doesn't
exist. There is, however, an honest way to make it 1000+ cases over several evenings — see below.

### Scaling this to 5,000 cases — `scenario_engine/mass_forensics_evaluation.py`

For a genuinely large, citable sample (built for a publication-quality accuracy claim, not just a
sanity check), `scenario_engine/mass_forensics_dataset.py` extends the exact same ground-truth
derivation (`_labeled()`/`_cert()`, imported, not copied) to 5,000 systematically generated
incidents — full combinatorial coverage (arity 1 through 4) across the 5 real, CBF-margin-grounded
factors, each single-factor case sweeping a real magnitude range from borderline to extreme rather
than repeating one hardcoded value, plus two control categories (no violation at all, and a
near-zero-*positive*-margin stress test for false-positive robustness). The other 4 real CBF
constraints (`altitude_ceiling`, `payload_weight_limit`, `noise_limit`, `collision_probability`)
have no forensics-factor mapping in the existing taxonomy and are deliberately left out — a
payload/noise/altitude rejection is a trivial pre-flight rejection, not incident-forensics
material worth an LLM investigation.

At 8 calls/incident, 5,000 incidents is ~40,000 real Ollama calls — tens of GPU-hours even on a
high-end card, genuinely not an evening's work. `scenario_engine/mass_forensics_evaluation.py` is
built around that reality: batched (default 250/batch) and fully resumable — every individual
result is flushed to `results.jsonl` immediately, so killing the process at any point loses at
most one in-flight incident, and re-running picks up exactly where it left off, across as many
days as it takes. Each batch gets its own self-contained HTML report (no CDN, opens offline); a
top-level `index.html` shows pooled precision/recall/F1 across every batch completed so far,
recomputed from raw confusion counts each time — never averaged per-batch F1s, matching how the
12-case script already scores. `IncidentForensicsWorker` itself is never modified — no concurrency
added, calls happen exactly the way the 12-case script already calls them, just orchestrated at
scale.

```bash
# No-GPU pipeline check (this only proves the mechanics work — mock mode's
# regex-based "reasoning" is not a capability measurement, see above):
USE_MOCK_AGENTS=true python -m scenario_engine.mass_forensics_evaluation --dry-run

# The real, citable run (needs Ollama + the roster pulled):
python -m scenario_engine.mass_forensics_evaluation
# ...next day, and the day after, just re-run the same command to continue:
python -m scenario_engine.mass_forensics_evaluation
```

A study's `results.jsonl` is refused from mixing mock-mode and real-mode rows into one pool (a
hard error unless `--allow-mixed-mode-report` is explicitly passed) — a "citable" bar means never
accidentally citing a mock-mode number, structurally, not just via a banner.

## 3. Everything with a screen, VR included — manual QA, checklist below

Rendering correctness, spatial layout, and the VR Safety View's two modes aren't things a unit test
can grade automatically — nobody's written an oracle for "does this look right in a headset", and
building one wouldn't be a good use of time before a demo. This is a real, permanent limitation of
automated testing for this class of feature, not a gap to apologize for. Manual pass, each time
something in this area changes:

- [ ] **Ops Center** — all 4 stat tiles populate, Fleet Digital Twin card appears once a dispatch
      has happened
- [ ] **Dispatch Console** — approved verdict shows Export for Mission Planner; rejected verdict
      shows a Request Explanation path that eventually resolves
- [ ] **Airspace Map** — red/yellow/green zone boundaries are actually visible against the
      satellite basemap (this session's own zone-visibility fix — regression-check it stays fixed)
- [ ] **VR Safety View, Live mode** — separation spheres, altitude plane, and battery gauges track
      a real in-flight drone
- [ ] **VR Safety View, Incident Replay** — pick a real CBF-rejected incident, confirm the replayed
      geometry's violated-constraint highlight matches the certificate, confirm the council's
      narrative panel populates (or correctly shows nothing, if `USE_MOCK_AGENTS`/no LLM available)
- [ ] **Incident Forensics** — a rejected dispatch shows up, investigation eventually reaches
      READY or FAILED (never hangs silently)
- [ ] **Settings → Local Ollama / Setup Wizard** — model list matches the real 4-tag roster, pull
      progress actually updates
- [ ] **Window chrome** — minimize/maximize/close all present and working (native OS decorations,
      fixed this session — regression-check it stays fixed)

## What "fine-tuning" actually means here

Worth being precise about, since it's easy to conflate with what's actually happening: nothing in
this project adjusts model weights. `mistral-small3.2`, `llama4:scout`, and the rest are used
exactly as Ollama serves them — no LoRA, no weight updates, no training run. What actually exists,
and is genuinely valuable, is two different things that get called "fine-tuning" loosely:

1. **Regression testing at scale** (section 1 above) — catches the deterministic layer breaking,
   automatically, on every change.
2. **Prompt-level retry-and-correct** — `scenario_engine/runner.py`'s `inject_correction` already
   implements this for the legacy scenario suite: when a metric fails, the next attempt's prompt
   gets told specifically what was wrong and how to fix it. That's real and useful, but it's
   iterating on the *prompt*, not the model — a different lever than fine-tuning, worth using where
   it applies (it currently only wires up to the legacy `run_grand_debate` evaluator, which per
   section 1 above needs its own rework before this retry loop is testing something current).
