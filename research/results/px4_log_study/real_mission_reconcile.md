# Planned-versus-flown check on real PX4 missions

Declared in `real_mission_reconcile.py`. Missions: 7 logs that record the mission they flew. Check run with its defaults (30 m sideways, 15 m height, at least 3 s).

**Missions with any reported deviation:** 3 of 7 (43%, 95% CI 16-75%). An upper bound on false alarms: some may be real deviations.

| Log | Mission items | Seconds compared | Reported episodes (kind, max m, s) |
|---|---|---|---|
| 5d1030f3 | 3 | 969 | off_route 259 m 240 s; off_route 461 m 127 s |
| bf216347 | 3 | 969 | off_route 259 m 240 s; off_route 461 m 127 s |
| cf71aabb | 13 | 269 | none |
| ee49fb99 | 9 | 366 | off_route 186 m 156 s; off_route 158 m 103 s |
| 9bda36cb | 21 | 1451 | none |
| ba9e87be | 8 | 37 | none |
| d33f6391 | 20 | 1400 | none |

## Reading the result (after the run)

- 5d1030f3 and bf216347 report identical numbers: the same flight uploaded twice. Distinct missions: 6.
- Both flights with reported deviations had left mission mode at those times: 5d1030f3 switched to RTL and HOLD
  (803-992 s) and resumed afterwards; ee49fb99 was taken over in POSCTL and then MANUAL from 529 s. These are real
  departures from the plan, which the review also lists as mode changes, not false alarms.
- While the vehicles flew in MISSION mode, the check reported no deviation in any of the 6 missions.
- Six missions are far too few for a rate (0 of 6 has a 95% upper bound of 39%). Only 34 of about 750 downloaded logs
  record their mission items, and most were dropped (fixed wing, fewer than three waypoint/takeoff/land items).
  The false-alarm rate on real plans remains to be measured on a partner fleet's own mission files.
