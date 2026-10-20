# Pilot or drone? First test on PX4 crash logs

Crash logs analysed: 93 (skipped: {'never armed': 7}). Labels are the uploader's own rating on PX4 Flight Review.
The rule was written and committed before it was run (see the docstring of `pilot_vs_drone.py`).

| Uploader said ↓ / rule said → | drone | pilot | unknown |
|---|---|---|---|
| drone | 37 | 18 | 8 |
| pilot | 15 | 13 | 2 |

- Decided: 83 of 93 (89%)
- Right when it decided: 50 of 83; wrong: 33 (35% of all)
- Balanced accuracy on decided cases: 0.57 (drone recall 0.67, pilot recall 0.46)
- Baseline 'always drone': right on 63 of 93 (68%), balanced accuracy 0.50
- Pre-declared success test: **FAILED**

## How often each piece of evidence fired

| Evidence | Drone-labelled crashes | Pilot-labelled crashes |
|---|---|---|
| D_BATT | 7 of 61 | 4 of 30 |
| D_MOTOR | 13 of 62 | 5 of 30 |
| D_CLIP | 19 of 51 | 3 of 26 |
| D_GPS | 1 of 47 | 1 of 29 |
| D_FD | 1 of 63 | 0 of 30 |
| D_ERR | 10 of 63 | 4 of 30 |
| D_CPU | 0 of 56 | 0 of 30 |
| D_FAILSAFE | 7 of 63 | 2 of 30 |

## Flight mode at the crash moment

| Mode | Drone-labelled | Pilot-labelled |
|---|---|---|
| ACRO | 1 | 0 |
| ALTCTL | 6 | 3 |
| MANUAL | 5 | 7 |
| POSCTL | 16 | 5 |
| STAB | 17 | 13 |
| auto/other 12 | 2 | 0 |
| auto/other 14 | 4 | 0 |
| auto/other 17 | 2 | 0 |
| auto/other 18 | 2 | 0 |
| auto/other 20 | 1 | 0 |
| auto/other 22 | 1 | 0 |
| auto/other 3 | 3 | 1 |
| auto/other 4 | 1 | 1 |
| auto/other 5 | 2 | 0 |

## Limits

- Uploader labels are unchecked and can be wrong; 'pilot' and 'drone' causes can both be present.
- No normal flights were tested here, so how often each evidence item fires on good flights is not known yet;
  an item that fires on many good flights is not evidence of anything.
- 100 logs; the pilot group is about a third of them.
