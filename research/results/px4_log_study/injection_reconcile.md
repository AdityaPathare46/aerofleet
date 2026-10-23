# Planned-versus-flown check: injected deviations in 40 real PX4 flights (summary)

Declared in `research/px4_log_study/injection_reconcile.py`. A plan is built from each real flight, a known sideways or
upward deviation is injected for 30 s, and the check is run with its defaults (30 m, 15 m, at least 3 s).

| Version of the check | False alarms (untouched flights) | Sideways 35 m | Sideways 50 m | Upwards 20 m |
|---|---|---|---|---|
| Nearest leg anywhere (as first built) | 16/40 (40%) | 20/40 (50%) | 23/40 (57%) | 39/40 (98%) |
| Greedy step-by-step order (tried, rejected) | 32/40 (80%) | 39/40 (98%) | 39/40 (98%) | 35/40 (88%) |
| **Whole-flight ordered alignment (now the default)** | 9/40 (22%) | 36/40 (90%) | 38/40 (95%) | 37/40 (92%) |
| Same, plan with a waypoint every 5 s instead of 10 s | **0/40 (0%)** | 36/40 (90%) | 38/40 (95%) | 39/40 (98%) |

The remaining 22% at 10 s spacing are fast flights (17-22 m/s) cutting the corners of ~200 m plan legs by 35-49 m for
3-5 s, an artefact of building plans from the track; a real mission has waypoints at its turns. Deviations below the
tolerances (25 m sideways, 14 m up) are mostly not reported, as specified. Full tables:
`injection_reconcile_nearest_first_run.md`, `injection_reconcile_ordered.md`, `injection_reconcile_ordered_wp5s.md`.
The greedy run's table was not kept; its numbers are as printed during the session (commit message records them).
