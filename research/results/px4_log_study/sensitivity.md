# Robustness checks (post hoc)

These checks were run after the declared tests, in response to an internal critical review. They are exploratory: none was declared in advance.

## S0 Composition of the archive samples

| | Crash-rated (real hardware) | Rated good/great (real hardware) |
|---|---|---|
| Logs | 520 | 21112 |
| Median duration (s) | 54 | 388 |
| Years (top 4) | 2018 91, 2025 89, 2019 87, 2017 57 | 2018 10571, 2017 5748, 2019 2910, 2020 949 |
| PX4 version (top 4) | v1.8. 70, v1.9. 66, v1.15 65, v1.11 65 | v1.7. 6299, v1.8. 5785, v1.6. 4265, v1.9. 2151 |
| Vehicle type (top 3) | Quadrotor 320, Fixed Wing 71, Hexarotor 38 | Quadrotor 19890, Fixed Wing 620, Hexarotor 291 |

## S1-S3, S5 Between-drone vibration test, variations

| Variation | Matched sets | Mean scaled rank | One-sided p | Crashed drone roughest of its set | Expected if no difference |
|---|---|---|---|---|---|
| As declared (all controls, all sources) | 60 | 0.67 | 0.0023 | 55% | 41% |
| S1 controls with the same airframe as the case | 39 | 0.69 | 0.0079 | 64% | 47% |
| S2 no case flights from the crash day | 25 | 0.76 | 0.0027 | 64% | 41% |
| S3 PX4 accelerometer vibration metric only | 12 | 0.62 | 0.1914 | 42% | 33% |
| S3 older-firmware estimator vibration only | 48 | 0.68 | 0.0047 | 58% | 42% |

## S4 Holm correction over the seven p-valued confirmatory tests

| Test | p | Holm-adjusted p |
|---|---|---|
| Settings: protections disabled, crash vs normal (Fisher) | 0.6260 | 1.0000 |
| Held-out: clipping, aircraft- vs pilot-blamed | 0.0450 | 0.2700 |
| Held-out: manual mode at the crash, pilot- vs aircraft-blamed | 0.1650 | 0.7265 |
| Within-drone vibration | 0.6654 | 1.0000 |
| Within-drone rate tracking | 0.4658 | 1.0000 |
| Between-drone vibration | 0.0023 | 0.0161 |
| Between-drone rate tracking | 0.1453 | 0.7265 |

## S6 Duration of the exposure flights

Median duration: case flights 289 s (n = 185), control flights 173 s (n = 312).

## S7 Within-drone vibration test with a different crash-moment threshold

| Tilt threshold | Drones | Mean scaled rank | One-sided p |
|---|---|---|---|
| 45 deg | 56 | 0.46 | 0.7865 |
| 60 deg (declared) | 61 | 0.48 | 0.6654 |
| 75 deg | 64 | 0.50 | 0.5375 |

## S8 Duration-adjusted between-drone vibration test

- imu: 118 flights, Spearman rho(duration, vibration) = 0.05, slope -0.16
- estimator_vibe: 361 flights, Spearman rho(duration, vibration) = -0.04, slope -0.08

On vibration adjusted for flight duration: 57 matched sets, mean scaled rank 0.69, one-sided p = 0.0005.
