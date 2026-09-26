# Real 1,000-case mass-forensics results — and how to report the F1

**Run:** `scenario_engine.mass_forensics_evaluation`, seed 20260826, 1,000 generated incidents,
real Ollama backend (not mock), every agent on `phi4-mini-reasoning` (3.8B, the single-model
roster sized for a laptop CPU — see `aerofleet/agents/factory.py`). 985 cases completed, 0 excluded.
Raw rows: `scenario_reports/mass_forensics_final/results.jsonl`. Report:
`python -m scenario_engine.mass_forensics_evaluation --study-dir scenario_reports/mass_forensics_final --target 1000 --batch-size 25 --report-only`.
Diagnostics: `python -m research.f1_diagnostics` → `research/results/f1_diagnostics.md`
(every number below comes from that file).

## Headline

| | value |
|---|---|
| Macro-F1 (5 scorable factors) | **0.468** |
| Macro-precision / recall | 0.473 / 0.487 |
| Latency per case | mean 291 s, median 243 s, p95 620 s |
| Macro-F1 by incident arity | single 0.346 · pair 0.514 · triple 0.625 · quad 0.701 |

`routing_navigation` and `cross_check_anomaly` have no positive cases in this pool and are not
scored; the per-category F1 of 0.0 for *control* cases is a scoring artefact (no positives to
recall) — the meaningful control metric is the false-alarm rate below.

## What the number is — and isn't

**It is not a safety number.** No dispatch decision depends on the council. The CBF gate decides,
deterministically, before any LLM is called (`docs/PATENT_NOVELTY.md`, Claim 1); the council only
investigates a rejection that is already final. A low council F1 therefore cannot let an unsafe
flight through — it can only produce a wrong *explanation*.

**It is a measurement of a 3.8B model's causal attribution from structured evidence.** In this
benchmark each case's ground truth is a deterministic function of its violated CBF margins, so the
task is "read the numbers and name the right subsystem". That makes every error diagnosable.

## Where the F1 is lost

**Misses (737 false negatives):**

| cause | share |
|---|---|
| agent reply could not be parsed → recorded UNCERTAIN (pipeline failure, not a judgement) | **82.2%** |
| agent said NOT_CONTRIBUTED (a real reasoning miss) | 10.6% |
| agent abstained (UNCERTAIN) | 7.2% |

**False alarms (788 false positives):**

| cause | share |
|---|---|
| cross-attribution — cites *another* factor's violated constraint as its own evidence (e.g. the comms agent citing `battery_reserve_margin = -42`) | **60.8%** |
| other unsupported claim | 28.0% |
| blamed something on a control case where nothing was violated | 11.2% |

On control cases the council blamed at least one factor in 73% of incidents. Stated confidence is
not calibrated: claims made at ≥ 0.9 confidence are right 51% of the time.

## Context numbers to report next to 0.468

| comparison | macro-F1 |
|---|---|
| prevalence-random (ignores the evidence) | 0.287 |
| always-CONTRIBUTED (ignores the evidence) | 0.445 |
| **council, as measured** | **0.468** |
| council, scored only where it produced a parseable, non-abstaining verdict (coverage 27–61% per factor) | 0.616 |
| council claims filtered by the deterministic claim check (`CONSTRAINT_TO_FACTOR`) | 0.647 |

State the always-yes comparison plainly: as measured, the council is only marginally better than
a classifier that ignores the evidence. The diagnostics show why (parsing and cross-attribution),
and that is the defensible story — not the headline number.

The last row needs its caveat: this dataset's labels are generated from the margins, so the
geometry filter's precision (1.000) is an upper bound here, not independent evidence. What it
does establish is that **every** false positive the council made is detectable without an LLM.

## How to put it (paper / review wording)

> On 985 real LLM investigations using a 3.8B model on commodity hardware, the council reached a
> macro-F1 of 0.47, only marginally above an evidence-blind always-yes baseline (0.45). Error
> analysis attributes 82% of misses to unparseable agent output rather than wrong judgements, and
> 61% of false alarms to cross-attribution, where a domain agent cites another domain's violated
> constraint as its own evidence. Because the safety decision is made by the deterministic CBF gate
> before the council runs, these errors affect explanations, never dispatch. They also motivate the
> design choice we evaluate in VR: the council's causal claims are never shown to an operator
> unverified — each is checked against the violated constraints (Table X), and every false positive
> in this study is caught by that check.

Points to make explicitly:

1. **Safety is decoupled from the LLM.** The architecture was built on the assumption that LLM
   attribution is unreliable; the study quantifies that assumption rather than contradicting the
   design.
2. **The failure modes are specific and fixable.** Both were fixed after the study
   (`aerofleet/agents/incident_forensics_worker.py`): a brace-balancing JSON extractor that
   accepts any fence or a bare object and skips an echoed schema line, verdicts pinned to the
   factor that was asked (agents had relabelled their factor, e.g. `safety_margin_negative`, which
   silently dropped the verdict), and a prompt with a valid JSON example plus an explicit
   "another factor's constraint is not your evidence" rule. Regression tests:
   `tests/unit/test_incident_forensics_worker.py`. **These fixes are not yet measured** — a re-run
   (same seed, same manifest) is needed before any improved number is claimed; 0.616 is a bound
   on the parsing fix alone, not a result.
3. **Difficulty scales the right way.** F1 rises from 0.35 (single factor) to 0.70 (four factors):
   the council over-attributes, which costs most precision when only one subsystem failed.
4. **The claim check is the mitigation, and it is what the operator sees.** The VR Safety View's
   claim-check board shows, per incident, which of the council's claims are confirmed, missed, or
   unbacked by the geometry — so an operator is never asked to trust the council's own
   confidence (which the study shows is uncalibrated).

## What not to say

- Don't report 0.616 or 0.647 as "the council's F1" — one is selective, the other is circular on
  this dataset.
- Don't compare against prior incident-analysis papers' F1 without matching task and model size.
- Don't claim the fixes improved F1 until the re-run exists.

## Next run (to close this properly)

Same manifest (`scenario_reports/mass_forensics_final/dataset_manifest.json`), same seed, fixed
worker, new study dir, e.g. `--study-dir scenario_reports/mass_forensics_v2`. Then compare v1 vs v2
per factor with the same diagnostics script. Saving each agent's raw text alongside its verdict
would make any future parse failure re-scorable without re-running the model.
