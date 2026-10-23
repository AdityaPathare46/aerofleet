# Within-drone test: the crash flight against the same drone's earlier flights

Crashes selected: 101; logs that could not be read or had under 10 s before the cut-off: 55. Features on each flight up to 10 s before the crash (or before the end of an earlier flight). Declared in advance in `within_drone.py`.

Scaled rank: 0 = the crash flight is the lowest of that drone's flights, 1 = the highest; 0.5 = no change.

| Feature | Drones | Mean scaled rank | One-sided p | Crash flight above the drone's median | Result |
|---|---|---|---|---|---|
| vib_p95 | 61 | 0.48 | 0.6654 | 51% | not supported |
| tune_rms | 46 | 0.50 | 0.4658 | 50% | not supported |
| clip_rate | 7 | 0.00 | 1.0000 | 0% | exploratory |
| sat_frac | 48 | 0.23 | 1.0000 | 23% | exploratory |

## By uploader label

| Feature | Label | Drones | Mean scaled rank | p |
|---|---|---|---|---|
| vib_p95 | drone | 46 | 0.52 | 0.3464 |
| vib_p95 | pilot | 15 | 0.36 | 0.9457 |
| tune_rms | drone | 36 | 0.56 | 0.1632 |
| tune_rms | pilot | 10 | 0.31 | 0.9556 |

## Sensitivity: earlier flights from the crash day left out

| Feature | Drones | Mean scaled rank | p |
|---|---|---|---|
| vib_p95 | 27 | 0.52 | 0.3656 |
| tune_rms | 15 | 0.66 | 0.0365 |

## Limits

- Uploader ratings; 'earlier' flights are the drone's own logs that were not rated as crashes (most are unrated).
- A drone can be modified between flights (new propellers, a re-tune), which this test cannot see.
- The crash flight is cut 10 s before the estimated crash moment; earlier flights 10 s before disarming.
