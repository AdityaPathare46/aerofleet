# Injected deviations in real PX4 flights (planned-versus-flown check, matching in flying order)

Flights: 40 real PX4 multirotor logs (rated good or great), each at least 120 s airborne. Plan built from the flight itself (a waypoint every 10 s). Deviation injected for 30 s with 3 s ramps. Check run with its defaults: 30 m sideways, 15 m height, at least 3 s. Declared in `injection_reconcile.py`.

**False alarms on the unmodified flights:** 9 of 40 (22%, 95% CI 12-38%).

| Injected | Size | Detected | Rate | 95% CI |
|---|---|---|---|---|
| sideways | 5 m | 1 of 40 | 2% | 0-13% |
| sideways | 10 m | 1 of 40 | 2% | 0-13% |
| sideways | 20 m | 4 of 40 | 10% | 4-23% |
| sideways | 25 m | 7 of 40 | 18% | 9-32% |
| sideways | 35 m | 36 of 40 | 90% | 77-96% |
| sideways | 50 m | 38 of 40 | 95% | 83-99% |
| sideways | 75 m | 39 of 40 | 98% | 87-100% |
| sideways | 100 m | 39 of 40 | 98% | 87-100% |
| upwards | 5 m | 0 of 40 | 0% | 0-9% |
| upwards | 10 m | 0 of 40 | 0% | 0-9% |
| upwards | 14 m | 8 of 40 | 20% | 10-35% |
| upwards | 20 m | 37 of 40 | 92% | 80-97% |
| upwards | 30 m | 39 of 40 | 98% | 87-100% |
| upwards | 50 m | 39 of 40 | 98% | 87-100% |

A false alarm here means the check reported a deviation on a flight that followed a plan made from itself; a miss below the tolerance is the intended behaviour, not an error.
