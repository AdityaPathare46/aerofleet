# Injected deviations in real PX4 flights (planned-versus-flown check)

Flights: 40 real PX4 multirotor logs (rated good or great), each at least 120 s airborne. Plan built from the flight itself (a waypoint every 10 s). Deviation injected for 30 s with 3 s ramps. Check run with its defaults: 30 m sideways, 15 m height, at least 3 s. Declared in `injection_reconcile.py`.

**False alarms on the unmodified flights:** 16 of 40 (40%, 95% CI 26-55%).

| Injected | Size | Detected | Rate | 95% CI |
|---|---|---|---|---|
| sideways | 5 m | 1 of 40 | 2% | 0-13% |
| sideways | 10 m | 1 of 40 | 2% | 0-13% |
| sideways | 20 m | 1 of 40 | 2% | 0-13% |
| sideways | 25 m | 2 of 40 | 5% | 1-17% |
| sideways | 35 m | 20 of 40 | 50% | 35-65% |
| sideways | 50 m | 23 of 40 | 57% | 42-71% |
| sideways | 75 m | 33 of 40 | 82% | 68-91% |
| sideways | 100 m | 35 of 40 | 88% | 74-95% |
| upwards | 5 m | 3 of 40 | 8% | 3-20% |
| upwards | 10 m | 4 of 40 | 10% | 4-23% |
| upwards | 14 m | 11 of 40 | 28% | 16-43% |
| upwards | 20 m | 39 of 40 | 98% | 87-100% |
| upwards | 30 m | 39 of 40 | 98% | 87-100% |
| upwards | 50 m | 39 of 40 | 98% | 87-100% |

A false alarm here means the check reported a deviation on a flight that followed a plan made from itself; a miss below the tolerance is the intended behaviour, not an error.
