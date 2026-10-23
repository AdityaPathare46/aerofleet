# Injected deviations in real PX4 flights (planned-versus-flown check, matching in flying order)

Flights: 40 real PX4 multirotor logs (rated good or great), each at least 120 s airborne. Plan built from the flight itself (a waypoint every 5 s). Deviation injected for 30 s with 3 s ramps. Check run with its defaults: 30 m sideways, 15 m height, at least 3 s. Declared in `injection_reconcile.py`.

**False alarms on the unmodified flights:** 0 of 40 (0%, 95% CI 0-9%).

| Injected | Size | Detected | Rate | 95% CI |
|---|---|---|---|---|
| sideways | 5 m | 0 of 40 | 0% | 0-9% |
| sideways | 10 m | 0 of 40 | 0% | 0-9% |
| sideways | 20 m | 0 of 40 | 0% | 0-9% |
| sideways | 25 m | 2 of 40 | 5% | 1-17% |
| sideways | 35 m | 36 of 40 | 90% | 77-96% |
| sideways | 50 m | 38 of 40 | 95% | 83-99% |
| sideways | 75 m | 39 of 40 | 98% | 87-100% |
| sideways | 100 m | 39 of 40 | 98% | 87-100% |
| upwards | 5 m | 0 of 40 | 0% | 0-9% |
| upwards | 10 m | 0 of 40 | 0% | 0-9% |
| upwards | 14 m | 3 of 40 | 8% | 3-20% |
| upwards | 20 m | 39 of 40 | 98% | 87-100% |
| upwards | 30 m | 39 of 40 | 98% | 87-100% |
| upwards | 50 m | 39 of 40 | 98% | 87-100% |

A false alarm here means the check reported a deviation on a flight that followed a plan made from itself; a miss below the tolerance is the intended behaviour, not an error.
