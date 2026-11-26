# SITL retest (v2): after fixing what v1 did not show

Declared before any v2 flight is flown (this file, `run_v2.py`, `evaluate_v2.py` and the product changes are committed
and pushed first). The v1 results stay as recorded (`research/results/sitl_check/`, commit `3f0327e`).

## What changed in AeroFleet after v1 (written after seeing v1, so v1's logs are development data)

1. **Failsafes switched off are flagged whatever the baseline says.** Today's fleet gives *Check first* when a failsafe
   is off in the drone's settings: for ArduPilot, the compliance rules for the low- and critical-battery failsafes,
   the RC-loss (throttle) failsafe, the EKF failsafe and the geofence; for PX4, `NAV_RCL_ACT` = 0, `COM_LOW_BAT_ACT`
   = 0 and `GF_ACTION` = 0. (v1 showed ArduPilot ships with its battery failsafe off, so a baseline can have it off.)
2. **The ArduPilot `.bin` reader reads what the autopilot recorded about its own health**, from structured records
   only: `ERR` (its own error reports, subsystem and code named as in ArduPilot's `AP_Logger.h`), `MAG` (each compass's
   health flag), `XKF4` (EKF3 core 0 test ratios above 1, as already read from PX4), `ATT` (tilt above 60°, the study's
   crash-tilt rule) and `RCOU` (a motor held within 2% of the autopilot's own ceiling `MOT_SPIN_MAX` for at least 1 s).
   The motor rule was first written as "outputs at opposite limits"; on the v1 motor-failure log it did not fire, the
   outputs were checked, and it was changed to the ceiling rule before this declaration.

Checked before declaring, on v1 logs only: no new warning on v1's normal, wind, failsafe and fence flights, nor on the
two public ArduPilot sample logs from FlightMD; the new readings appear on v1's motor and compass logs.

## Flights (all new)

`run_v2.py`: the same scenarios as v1 on three fields never flown before (field numbers 3, 4 and 5), home 10 m south of
each field, 3 runs per scenario. Every run starts from a **configured** vehicle (ArduPilot SITL defaults plus
`BATT_FS_LOW_ACT` 2, `BATT_FS_CRT_ACT` 1, `BATT_LOW_VOLT` 10.5, `BATT_CRT_VOLT` 10.0, `FENCE_ENABLE` 1), so a normal
flight has no failsafe switched off. Baseline = the settings in the log of v2 S0 run 1. In S4 the fence is already on
(configured) and is switched off 40 s into the mission.

## Expected results (declared; met = in all 3 runs)

| Scenario | Counts as met when |
|---|---|
| S0 normal | no warning-level event, no plan deviation, no failsafe off, settings OK, verdict Ready |
| S1 failsafes off | `FS_THR_ENABLE` and `BATT_FS_LOW_ACT` both named as changed safety-critical settings **and** both flagged as failsafes off; verdict Do not fly |
| S2 GPS lost | a "Poor GPS" warning (as v1) |
| S3 battery low | a "Battery below 20%" event (as v1) |
| S4 fence off in flight | `FENCE_ENABLE` 1 → 0 listed as a safety-critical change in flight (as v1) |
| S5 wind | no warning-level event, no plan deviation, no failsafe off |
| S6 motor failure | at least one of: tilt above 60°, a motor held at its maximum output, the autopilot's thrust-loss or crash-check report |
| S7 compass failure | at least one of: compass 1 reported unhealthy, the autopilot's compass report, the estimator rejecting compass data |

S0 and S5 are the false-alarm controls for the new readings. Results are committed whatever they show.

    python research/sitl_check/run_v2.py
    python research/sitl_check/evaluate_v2.py
