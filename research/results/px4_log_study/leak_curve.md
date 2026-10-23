# The crash-window leak

Logs with at least one usable window: 287 (skipped 85). Features are computed on the flight up to *m* seconds before the crash (normal flights: before the end of the armed period). Declared in advance in `leak_curve.py`.

## Model (logistic regression, 5-fold CV x 5)

| Cut-off m (s) | A: crash vs normal — logs | A: AUC | B: pilot vs drone — logs | B: AUC |
|---|---|---|---|---|
| 0 | 148 crash / 139 normal | 0.88 ± 0.01 | 112 drone / 36 pilot | 0.49 ± 0.05 |
| 2 | 142 crash / 137 normal | 0.86 ± 0.01 | 106 drone / 36 pilot | 0.48 ± 0.05 |
| 5 | 135 crash / 133 normal | 0.88 ± 0.01 | 101 drone / 34 pilot | 0.52 ± 0.04 |
| 10 | 114 crash / 130 normal | 0.87 ± 0.01 | 87 drone / 27 pilot | 0.42 ± 0.02 |
| 20 | 100 crash / 128 normal | 0.85 ± 0.01 | 73 drone / 27 pilot | 0.48 ± 0.03 |
| 30 | 89 crash / 124 normal | 0.86 ± 0.01 | 63 drone / 26 pilot | 0.46 ± 0.03 |

**H_leak** (task A AUC at 0 s minus at 10 s >= 0.10): drop = 0.01 → **not supported**.

## Single features, task A (crash vs normal), AUC with no fitting

| Feature | m=0 | m=2 | m=5 | m=10 | m=20 | m=30 |
|---|---|---|---|---|---|---|
| tune_rms | 0.81 | 0.75 | 0.72 | 0.72 | 0.68 | 0.69 |
| tilt_p95 | 0.41 | 0.39 | 0.35 | 0.36 | 0.35 | 0.33 |
| vib_p95 | 0.74 | 0.73 | 0.71 | 0.72 | 0.74 | 0.77 |
| clip_rate | 0.59 | 0.58 | 0.57 | 0.54 | 0.54 | 0.55 |
| sat_frac | 0.67 | 0.64 | 0.64 | 0.66 | 0.65 | 0.65 |
| batt_min | 0.42 | 0.41 | 0.42 | 0.40 | 0.39 | 0.38 |
| volt_sag | 0.55 | 0.55 | 0.53 | 0.53 | 0.52 | 0.48 |
| gps_bad | 0.53 | 0.53 | 0.54 | 0.55 | 0.54 | 0.54 |
| failsafe | 0.50 | 0.49 | 0.48 | 0.47 | 0.46 | 0.47 |
| manual_frac | 0.67 | 0.66 | 0.68 | 0.68 | 0.68 | 0.69 |
| stick_p95 | 0.32 | 0.31 | 0.31 | 0.33 | 0.35 | 0.35 |

AUC 0.5 = no better than chance; below 0.5 means the feature is *lower* in crashes.

## Limits

- Labels are the uploaders'; normal flights are self-rated good/great.
- The crash moment is estimated from attitude (rotary wing) or the end of arming (fixed wing).
- Normal flights end with a landing, crashes with a crash; the cut-off removes the last m seconds of both.
- One simple model; a stronger model could do better at every cut-off, which would not remove the leak.
