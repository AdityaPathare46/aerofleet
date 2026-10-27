# Post-crash flight audit (within-drone samples)

Declared in `research/px4_log_study/postcrash_audit.py` (docstring). Exploratory (dagger).

Anchors pass: **True**.

Same-day earlier flights: 210; {'precedes': 107, 'follows': 85, 'undeterminable': 18}; crashes with >= 1 following flight: 29.

F = without flights flown after the crash; FU = also without flights with no GPS time.

## A. Within-drone rank test

| Version | Feature | Drones | Mean rank | One-sided p |
|---|---|---|---|---|
| Published | vib_p95 | 61 | 0.481 | 0.6654 |
| Published | tune_rms | 46 | 0.504 | 0.4658 |
| F | vib_p95 | 44 | 0.488 | 0.5953 |
| F | tune_rms | 30 | 0.551 | 0.2140 |
| FU | vib_p95 | 41 | 0.528 | 0.3025 |
| FU | tune_rms | 26 | 0.552 | 0.2279 |

## B. Within-drone Group-CV model

| Version | Drones | Earlier flights | AUC | Cluster 95% CI |
|---|---|---|---|---|
| Published | 67 | 305 | 0.559 | [0.511, 0.618] |
| F | 57 | 227 | 0.582 | [0.525, 0.660] |
| FU | 56 | 216 | 0.572 | [0.516, 0.658] |

## C. Caliper 0.25 lift

| Version | Airframes | Features | Matched | Unmatched | Lift | Paired 95% CI |
|---|---|---|---|---|---|---|
| Published | 36 | F11 | 0.636 | 0.526 | +0.110 | [+0.028, +0.205] |
| Published | 36 | F8 | 0.573 | 0.496 | +0.077 | [+0.013, +0.204] |
| F | 24 | F11 | 0.616 | 0.529 | +0.086 | [-0.064, +0.184] |
| F | 24 | F8 | 0.615 | 0.552 | +0.063 | [-0.087, +0.159] |
| FU | 24 | F11 | 0.606 | 0.527 | +0.079 | [-0.048, +0.199] |
| FU | 24 | F8 | 0.612 | 0.548 | +0.063 | [-0.074, +0.171] |

## D. Factorial same-aircraft cells (grouped CV, constant subset)

| Version | Cell | Crashes | Earlier flights | AUC | Cluster 95% CI |
|---|---|---|---|---|---|
| Published | m0_full | 60 | 301 | 0.562 | [0.488, 0.624] |
| Published | m0_first30 | 60 | 301 | 0.455 | [0.375, 0.506] |
| Published | m10_full | 60 | 301 | 0.534 | [0.468, 0.598] |
| Published | m10_first30 | 60 | 301 | 0.455 | [0.375, 0.506] |
| F | m0_full | 60 | 223 | 0.528 | [0.438, 0.602] |
| F | m0_first30 | 60 | 223 | 0.498 | [0.410, 0.574] |
| F | m10_full | 60 | 223 | 0.507 | [0.436, 0.582] |
| F | m10_first30 | 60 | 223 | 0.498 | [0.410, 0.574] |
| FU | m0_full | 60 | 213 | 0.537 | [0.446, 0.603] |
| FU | m0_first30 | 60 | 213 | 0.488 | [0.394, 0.552] |
| FU | m10_full | 60 | 213 | 0.513 | [0.429, 0.587] |
| FU | m10_first30 | 60 | 213 | 0.488 | [0.394, 0.552] |

## Declared decisions (F version)

- A_within_drone_warning: **False**
- B_signal_detected: **True**
- C_masking_supported: **False**
- D_same_aircraft_above_chance: **False**
