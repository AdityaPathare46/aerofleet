# SITL retest (v2): results

Declared in `research/sitl_check/PROTOCOL_v2.md`. Every run in `results.json`.

| Scenario | Outcome | What AeroFleet showed (run 1) |
|---|---|---|
| S0_normal | met (3 of 3 runs) | verdict READY, settings OK; no warnings |
| S1_failsafe_off | met (3 of 3 runs) | verdict DO_NOT_FLY, settings BLOCK; failsafes off: BATT_FS_LOW_ACT, FS_THR_ENABLE |
| S2_gps_lost | met (3 of 3 runs) | verdict CHECK_FIRST, settings OK; Poor GPS for 20 s (fewer than 6 satellites, no 3D fix, or HDOP above 2.5); Autopilot reported: EKF check, bad variance; Autopilot reported: EKF failsafe, triggered |
| S3_battery_low | met (3 of 3 runs) | verdict DO_NOT_FLY, settings BLOCK; Autopilot reported: battery failsafe, triggered; Battery below 10% (9%, 9.2 V); A motor held at its maximum output (saturated) for 2 s; A motor held at its maximum output (saturated) for 8 s |
| S4_fence_off_in_flight | met (3 of 3 runs) | verdict DO_NOT_FLY, settings BLOCK; Setting FENCE_ENABLE changed 1 → 0 in flight (safety-critical); failsafes off: FENCE_ENABLE |
| S5_wind | met (3 of 3 runs) | verdict READY, settings OK; no warnings |
| S6_motor_failure | met (3 of 3 runs) | verdict CHECK_FIRST, settings OK; A motor held at its maximum output (saturated) for 787 s; Autopilot reported: thrust loss check, thrust loss detected; Battery below 10% (9%, 12.3 V); Autopilot reported: thrust loss check, thrust loss detected |
| S7_compass_failure | met (3 of 3 runs) | verdict CHECK_FIRST, settings OK; Autopilot reported: compass, unhealthy; Compass 1 reported unhealthy for 110 s |

## Notes, written after seeing the results

- All 8 scenarios met their declared expectation in all 3 runs, on fields never flown before and with the readers and
  rule frozen at the declaring commit (`6f55575`). The v1 results (`research/results/sitl_check/`) stand as recorded;
  this is a separate, declared retest after the fixes.
- **Normal and windy flights stayed clean** (no warning, no failsafe off, Ready), so the new readings added no false
  alarm here. That is 6 flights of one simulated airframe; real frames vibrate and their motors work harder, so the
  false-alarm rate on real fleets is still unmeasured.
- **The new signs say what happened, not why.** "A motor held at its maximum output" appeared after the motor failure
  and also when the simulated battery ran flat (S3): it marks a drone at the limit of its power, not a failed motor.
  The autopilot's own "thrust loss detected" report appeared in both too. AeroFleet still names no cause.
- **S6 timelines are long and repetitive**: the crashed vehicle stayed armed until each run timed out, so saturation
  lasted 13-29 minutes and the thrust-loss report repeated. A real crash is usually followed by a disarm.
- **S7**: compass 1 was reported unhealthy for about 110 s in each run, together with the autopilot's compass error.
- What SITL cannot show: real sensor noise, real frame vibration, and whether these readings mean the same on a real
  Pixhawk in a field.
