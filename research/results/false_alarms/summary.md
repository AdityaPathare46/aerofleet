# FA1: how often does Today's fleet flag a healthy drone from its last log?

Declared in `research/false_alarms/measure.py`. Full numbers in `results.json`.

| Flights | Flagged (Check first) | 95% interval |
|---|---|---|
| All 1121 ordinary flights | 456 (40.7%) | 37.8-43.6% |
| 299 rated good or great | 86 (28.8%) | 23.9-34.1% |

Pass mark: at most 20% of good-or-great flights. **Not met.**

| Warning (all flights) | Share | Flights |
|---|---|---|
| Estimator rejected compass data | 16.2% | 182 |
| Battery below | 16.2% | 182 |
| Estimator rejected velocity data | 11.8% | 132 |
| Autopilot in failsafe | 11.2% | 125 |
| Estimator reported an internal fault | 8.6% | 97 |
| Estimator rejected position data | 8.3% | 93 |
| Estimator rejected height data | 4.1% | 46 |
| Poor GPS | 2.0% | 22 |
| Setting RTL_DESCEND_ALT changed 119.819 → 119.595 in flight | 0.2% | 2 |
| Setting RTL_DESCEND_ALT changed 99.917 → 119.819 in flight | 0.2% | 2 |
| Setting RTL_RETURN_ALT changed 119.819 → 119.595 in flight | 0.2% | 2 |
| Setting RTL_RETURN_ALT changed 99.917 → 119.819 in flight | 0.2% | 2 |
| Setting RTL_DESCEND_ALT changed 100.084 → 105.043 in flight | 0.1% | 1 |
| Setting RTL_DESCEND_ALT changed 104.822 → 104.837 in flight | 0.1% | 1 |
| Setting RTL_DESCEND_ALT changed 105.043 → 104.822 in flight | 0.1% | 1 |
| Setting RTL_RETURN_ALT changed 100.084 → 105.043 in flight | 0.1% | 1 |
| Setting RTL_RETURN_ALT changed 104.822 → 104.837 in flight | 0.1% | 1 |
| Setting RTL_RETURN_ALT changed 105.043 → 104.822 in flight | 0.1% | 1 |
| Setting GF_MAX_HOR_DIST changed 150 → 180 in flight | 0.1% | 1 |
| Setting RTL_RETURN_ALT changed 30 → 100 in flight | 0.1% | 1 |
| Setting COM_RC_LOSS_T changed 0.5 → 2 in flight | 0.1% | 1 |
| Setting COM_DL_LOSS_T changed 190 → 60 in flight | 0.1% | 1 |
| Setting RTL_RETURN_ALT changed 90 → 100 in flight | 0.1% | 1 |
| Setting COM_DL_LOSS_T changed 210 → 200 in flight | 0.1% | 1 |
| Setting RTL_RETURN_ALT changed 130 → 80 in flight | 0.1% | 1 |
| Setting RTL_RETURN_ALT changed 80 → 130 in flight | 0.1% | 1 |
| Setting NAV_DLL_ACT changed 7 → 8 in flight | 0.1% | 1 |
| Setting RTL_RETURN_ALT changed 120 → 100 in flight | 0.1% | 1 |
| Setting NAV_RCL_ACT changed 2 → 0 in flight | 0.1% | 1 |

## Notes, written after seeing the result

- **Not met.** 28.8% [23.9, 34.1] of the 299 good-or-great flights would get "Check first" from their own log, and
  40.7% of all 1,121 ordinary flights; 218 of 401 vehicles have at least one flagged flight. The two halves agree
  (D 42.3%, H 39.2%). As built, the board would flag healthy drones far too often.
- The commonest reasons: the PX4 estimator briefly rejecting compass or velocity data, landing below 10% battery,
  and the autopilot's failsafe flag. These are real events in the logs, but most say little about whether the drone is
  fit to fly **today**.
- The table lists each in-flight setting change separately (the summary groups by text); together they are under 2%.
- Next (declared separately): change the rules using the development half D only, then test on the held-out half H.
