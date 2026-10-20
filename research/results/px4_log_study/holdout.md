# Held-out test: PX4 crash benchmark, step 2

Held-out crashes analysed: 112 (73 drone-blamed, 39 pilot-blamed); normal flights: 143. Skipped: {'crash: never armed': 11, 'normal: never armed': 6}.
Hypotheses and pass marks were committed before these logs were downloaded (`holdout_test.py`).

## Pre-declared hypotheses (one-sided Fisher exact, supported if p < 0.025)

| | Drone-blamed | Pilot-blamed | p | Result |
|---|---|---|---|---|
| H1 clipping | 14 of 58 | 3 of 36 | 0.045 | not supported |
| H2 MANUAL at crash | 7 of 73 | 7 of 39 | 0.165 | not supported |

## Rules on the held-out crashes

| Rule | Answered | Wrong (of all) | Balanced accuracy (answered) |
|---|---|---|---|
| v1 (as declared before the first run) | 107 of 112 | 53 (47%) | 0.47 |
| v2 (clipping, then MANUAL) | 31 of 112 | 10 (9%) | 0.68 |

## How often each sign fires

| Sign | Drone-blamed crashes | Pilot-blamed crashes | Normal flights |
|---|---|---|---|
| D_BATT | 11 of 73 (15%) | 7 of 38 (18%) | 4 of 143 (3%) |
| D_MOTOR | 16 of 71 (23%) | 11 of 38 (29%) | 2 of 143 (1%) |
| D_CLIP | 14 of 58 (24%) | 3 of 36 (8%) | 7 of 48 (15%) |
| D_GPS | 2 of 61 (3%) | 2 of 37 (5%) | 2 of 143 (1%) |
| D_FD | 0 of 73 (0%) | 0 of 39 (0%) | 0 of 143 (0%) |
| D_ERR | 14 of 73 (19%) | 4 of 39 (10%) | 29 of 143 (20%) |
| D_CPU | 0 of 64 (0%) | 0 of 38 (0%) | 0 of 143 (0%) |
| D_FAILSAFE | 13 of 73 (18%) | 3 of 39 (8%) | 19 of 143 (13%) |

Rule v1 would have called 56 of 143 normal flights a drone fault (39%).

## Limits

- Uploader labels are unchecked. Normal flights are those rated good/great by their uploader.
- For normal flights the 'crash moment' is the end of the armed period, so late-window signs cover landing.
