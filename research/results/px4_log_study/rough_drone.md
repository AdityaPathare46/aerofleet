# Rough-drone test: crashed drones against matched drones that did not crash

Matched sets: 66; flights that could not be read or were too short: 71. A drone's value is the median over its 3 flights (crashed drones: flights before the crash). Controls match the case on flight-controller hardware, PX4 version and vehicle type. Declared in advance in `rough_drone_test.py`.

Scaled rank: 1 = the crashed drone is rougher than all its matched controls, 0 = smoother than all; 0.5 = no difference.

| Feature | Matched sets used | Mean scaled rank | One-sided p | Result |
|---|---|---|---|---|
| vib_p95 | 60 | 0.67 | 0.0023 | supported |
| tune_rms | 47 | 0.57 | 0.1453 | not supported |

## By uploader label

| Feature | Label | Sets | Mean scaled rank | p |
|---|---|---|---|---|
| vib_p95 | drone | 46 | 0.67 | 0.0049 |
| vib_p95 | pilot | 14 | 0.64 | 0.1575 |
| tune_rms | drone | 35 | 0.60 | 0.1108 |
| tune_rms | pilot | 12 | 0.50 | 0.5654 |

## Limits

- Controls have no crash-rated log, which does not prove they never crashed (most logs are unrated).
- Matching is on hardware, firmware and vehicle type only; frames, propellers, payloads and use differ.
- Uploader-rated crashes come from people who rate their logs, which may not represent all operators.
