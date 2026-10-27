# Round 14 audit

Declared in `research/px4_log_study/r14_audit.py` (docstring). Exploratory (dagger).

## Part A: caliper lift (0.25) with and without clip_rate, tilt_p95, volt_sag

Airframes 36; matched flights 113; unmatched 199. Anchors pass: True.

| Features | Matched (5 seeds) | Unmatched (5 seeds) | Lift | Paired 95% CI | Matched (seed 42) | Unmatched (seed 42) | Lift | Paired 95% CI |
|---|---|---|---|---|---|---|---|---|
| F11 | 0.636 | 0.526 | +0.110 | [+0.028, +0.205] | 0.609 | 0.511 | +0.098 | [+0.019, +0.176] |
| F8 | 0.573 | 0.496 | +0.077 | [+0.013, +0.204] | 0.561 | 0.500 | +0.062 | [-0.008, +0.132] |

Masking reading supported (F8 lift_5 >= 0.05 and CI excludes 0): **True**

## Part B: GPS-time ordering of crash-day exposure flights

Analysed sets: 60 (declared test: mean rank 0.667, p 0.0023, n 60).
Same-day sets: 39; same-day exposure flights: 98; {'precedes': 38, 'follows': 47, 'undeterminable': 10}.
without_following: mean rank 0.698, p 0.0021, n 43.
without_following_or_undeterminable: mean rank 0.718, p 0.0014, n 39.
