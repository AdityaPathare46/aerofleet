# Council F1 diagnostics — scenario_reports/mass_forensics_final

985 completed cases × 5 scorable factors (factors with no positive case in the pool are excluded, as in the study).

## 1. Headline (reproduced)

| factor | prevalence | precision | recall | F1 | UNCERTAIN rate |
|---|---|---|---|---|---|
| airspace_conflict | 33.5% | 0.507 | 0.312 | **0.386** | 72.8% |
| battery_energy | 25.3% | 0.437 | 0.470 | **0.453** | 45.6% |
| communications_link | 25.6% | 0.381 | 0.659 | **0.483** | 38.9% |
| ops_scheduling_capacity | 25.6% | 0.506 | 0.484 | **0.495** | 45.8% |
| weather_environmental | 33.6% | 0.533 | 0.511 | **0.522** | 42.0% |

**Macro-F1 0.4678**, macro-precision 0.4728, macro-recall 0.4872.

## 2. Naive baselines on the same labels

A classifier that ignores the evidence. *Always-yes* predicts CONTRIBUTED for every factor of every case; *prevalence-random* says CONTRIBUTED with probability equal to the factor's prevalence (expected F1 = prevalence).

| factor | council F1 | always-yes F1 | prevalence-random F1 |
|---|---|---|---|
| airspace_conflict | 0.386 | 0.502 | 0.335 |
| battery_energy | 0.453 | 0.404 | 0.253 |
| communications_link | 0.483 | 0.407 | 0.256 |
| ops_scheduling_capacity | 0.495 | 0.407 | 0.256 |
| weather_environmental | 0.522 | 0.503 | 0.336 |
| **macro** | **0.468** | 0.445 | 0.287 |

## 3. Error anatomy

**False positives: 788**

- cross-attribution: cites another factor's violated constraint as its own evidence: 479 (60.8%)
- other unsupported claim: 221 (28.0%)
- blamed a factor although nothing was violated (control case): 88 (11.2%)

**False negatives: 737**

- agent response could not be parsed (pipeline failure, not a judgement): 606 (82.2%)
- said NOT_CONTRIBUTED (a real miss): 78 (10.6%)
- abstained (UNCERTAIN): 53 (7.2%)

## 4. When the council does answer

Scoring only the factor-verdicts that are not UNCERTAIN and not a parse failure (coverage = share of verdicts kept).

| factor | coverage | precision | recall | F1 |
|---|---|---|---|---|
| airspace_conflict | 27.2% | 0.507 | 0.912 | 0.652 |
| battery_energy | 54.4% | 0.437 | 0.807 | 0.567 |
| communications_link | 61.1% | 0.381 | 0.988 | 0.550 |
| ops_scheduling_capacity | 54.2% | 0.506 | 0.884 | 0.644 |
| weather_environmental | 58.0% | 0.533 | 0.885 | 0.665 |
| **macro** | | | | **0.616** |

## 5. Control cases (nothing violated)

89 control cases. The council blamed at least one factor in **65 (73.0%)**, 89 false claims in total. (Per-category F1 is 0.0 for controls by construction — there are no positives to recall — so the false-alarm rate is the meaningful number here.)

## 6. Does stated confidence mean anything?

| council confidence on a CONTRIBUTED claim | claims | precision |
|---|---|---|
| ≥ 0.9 | 1298 | 0.510 |
| 0.7 – 0.9 | 166 | 0.090 |
| < 0.7 | 1 | 0.000 |

## 7. Council claims filtered by the deterministic claim check

A CONTRIBUTED claim is kept only if a violated CBF constraint maps to that factor (`CONSTRAINT_TO_FACTOR`, the same rule the VR claim-check board applies to each incident). The filter can only withdraw claims, never add them.

| factor | precision | recall | F1 |
|---|---|---|---|
| airspace_conflict | 1.000 | 0.312 | 0.476 |
| battery_energy | 1.000 | 0.470 | 0.639 |
| communications_link | 1.000 | 0.659 | 0.794 |
| ops_scheduling_capacity | 1.000 | 0.484 | 0.652 |
| weather_environmental | 1.000 | 0.511 | 0.676 |
| **macro** | | | **0.647** |

> Caveat: this dataset's labels are generated from the violated margins, so the filter's precision is an upper bound on this benchmark, not independent evidence. What it does show is that every one of the council's false positives is detectable without an LLM — which is why the claim check, not the council, is what an operator is shown as the verdict.

