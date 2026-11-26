# SITL check: results

Declared in `research/sitl_check/PROTOCOL.md`. Every run in `results.json`.

| Scenario | Outcome | What AeroFleet showed (run 1) |
|---|---|---|
| S0_normal | met (3 of 3 runs) | verdict READY, settings OK; no warnings |
| S1_failsafe_off | not met (0 of 3 runs) | verdict DO_NOT_FLY, settings BLOCK; no warnings |
| S2_gps_lost | met (3 of 3 runs) | verdict CHECK_FIRST, settings OK; Poor GPS for 20 s (fewer than 6 satellites, no 3D fix, or HDOP above 2.5); SIM_GPS1_ENABLE 1 -> 0 (INFO); SIM_GPS1_ENABLE 0 -> 1 (INFO) |
| S3_battery_low | met (3 of 3 runs) | verdict DO_NOT_FLY, settings BLOCK; Battery below 10% (9%, 9.2 V) |
| S4_fence_off_in_flight | met (3 of 3 runs) | verdict DO_NOT_FLY, settings BLOCK; Setting FENCE_ENABLE changed 1 → 0 in flight (safety-critical); FENCE_ENABLE 1 -> 0 (CRITICAL) |
| S5_wind | met (3 of 3 runs) | verdict READY, settings OK; no warnings |
| S6_motor_failure | descriptive | verdict CHECK_FIRST, settings OK; Battery below 10% (9%, 12.3 V); SIM_ENGINE_FAIL 0 -> 1 (INFO) |
| S7_compass_failure | descriptive | verdict READY, settings OK; SIM_MAG1_FAIL 0 -> 1 (INFO) |

## Notes, written after seeing the results

- **S1 not met, as declared.** The declaration expected both `FS_THR_ENABLE` and `BATT_FS_LOW_ACT` to be named. In
  ArduPilot's SITL defaults `BATT_FS_LOW_ACT` is already 0 (the battery failsafe is off out of the box: baseline 0,
  S1 0), so setting it to 0 changed nothing and there was nothing to detect. `FS_THR_ENABLE` (1 → 0) was named in all
  3 runs and the verdict was **Do not fly** in all 3. The expectation was wrong, not the check; the result stays
  "not met". Worth telling operators: ArduPilot ships with the low-battery failsafe off.
- **S2.** "Poor GPS for 20 s" in all 3 runs, matching the 20 s outage; the autopilot's EKF failsafe switched to LAND,
  which the timeline also shows as a mode change. Verdict Check first.
- **S3 and S4** show Do not fly partly because the scenario itself changed settings against the baseline (battery
  limits; fence type and height), which the drift check rightly reports. The declared expectation (the battery events;
  `FENCE_ENABLE` 1 → 0 changed in flight, safety-critical) was met in all runs.
- **S3** also shows "Battery voltage fell 90% (12.6 → 1.3 V)": the simulated battery was run flat after landing. Real
  packs do not read 1.3 V; it is a simulation artefact, shown as the log recorded it.
- **S5.** In 8 m/s wind the largest sideways deviation was 0.9-1.5 m; no false alarm.
- **S6 (descriptive).** Nothing in AeroFleet's review points to the motor failure. The crashed vehicle stayed armed
  until the run timed out, so the battery ran down and the review shows only low-battery events. AeroFleet has no
  crash detection and names no cause, as designed; a motor failure is not something it claims to find.
- **S7 (descriptive, known gap confirmed).** The autopilot switched to its second compass; AeroFleet showed nothing,
  because it reads the estimator's own sensor checks only from PX4 logs. ArduPilot logs do record them (EKF
  innovation test ratios), so reading them is a clear next step.
- Simulator parameter changes (`SIM_...`) appear in the in-flight list as INFO, which is correct: they are not
  vehicle settings.
