# FA2: the revised warning rule on the held-out half H

Declared in `research/false_alarms/measure_fa2.py`. Full numbers in `fa2_results.json`.

| Flights (held-out half H) | Flagged | 95% interval |
|---|---|---|
| 190 rated good or great | 21 (11.1%) | 7.3-16.3% |
| All 572 | 113 (19.8%) | 16.7-23.2% |

Pass mark: at most 20% of H's good-or-great flights. **Met.**

Reasons (all H flights): Autopilot in failsafe 46; Estimator rejected compass data 43; Estimator rejected velocity data 43; Estimator rejected position data 41; Estimator reported an internal fault 19; Estimator rejected height data 18; Poor GPS 6; Setting RTL_DESCEND_ALT changed 119.819 → 119.595 in flight 2; Setting RTL_DESCEND_ALT changed 99.917 → 119.819 in flight 2; Setting RTL_RETURN_ALT changed 119.819 → 119.595 in flight 2; Setting RTL_RETURN_ALT changed 99.917 → 119.819 in flight 2; Setting RTL_DESCEND_ALT changed 100.084 → 105.043 in flight 1
Pilot notes (landed below 10% battery), shown but not a reason: 94 of 572 H flights.

## Notes, written after seeing the result

- **Met.** On drones never used to choose the rule, 11.1% [7.3, 16.3] of good-or-great flights would get "Check first"
  (FA1, same flights, old rule: H 39.2% of all flights). The development half D gave 19.3%; the held-out figure is
  lower, so the rule was not over-fitted to D in this respect.
- Still one healthy flight in five overall (19.8% of all H flights), mostly the autopilot's failsafe flag and the
  estimator rejecting sensor data for 3 s or more in the air. These are real events; whether each matters for today's
  flight is for the operator to judge, which is why the board says "Check first", never "Do not fly", for them.
- The rule costs some sensitivity, measured on D: real motor-fault flights flagged 19.4% instead of 21.5%, sensor-fault
  flights 53.8% instead of 58.4% (RflyMAD). Most injected motor faults were absorbed by the controller and leave little
  in the log either way.
- These are public, mostly hobby and research flights, not a spraying fleet: the rate on real agricultural drones is
  still unmeasured.
