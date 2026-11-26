# SITL check: AeroFleet on real ArduCopter flight logs with known faults

Declared before the scenarios are flown (this file, `run_scenarios.py` and `evaluate.py` are committed and pushed
first). Engineering verification of the product, not a hypothesis about drones.

## Why

AeroFleet has been checked on public logs, where nobody knows exactly what happened. Here the faults are put in on
purpose, so every expected result is known in advance. ArduPilot SITL runs the **real ArduCopter flight code**
(ArduPilot master, commit 3d6ebed of 19 Nov 2026, built for SITL on this Mac) with a simulated quadcopter and writes
the same DataFlash `.bin` log a Pixhawk writes. What it cannot give: real sensor noise, vibration from a real frame, or
weather beyond the simulated wind.

Before declaring, one normal mission was flown to check the setup (engineering check): the log was read by AeroFleet
(1,926 positions, 1,436 settings, battery, GPS, vibration, modes). Its review was not looked at.

## Flights

Each run starts from ArduPilot's SITL default settings (wiped), home on a field east of Pune, and flies a
spraying-style mission: back-and-forth passes 8 m apart at 4 m over an 80 m by 40 m field, then return to launch and
land. Three runs per scenario; the field moves 150 m between runs and the passes alternate east-west and north-south.
Logs go to `AeroFleet_px4_data/sitl/` with the mission file beside each.

| Scenario | Change | When |
|---|---|---|
| S0 normal | none | |
| S1 failsafe off | `FS_THR_ENABLE` 0 and `BATT_FS_LOW_ACT` 0 | before arming |
| S2 GPS lost | `SIM_GPS1_ENABLE` 0, back to 1 after 20 s | 40 s into the mission |
| S3 battery low | simulated battery 350 mAh (`SIM_BATT_CAP_AH` 0.35, `BATT_CAPACITY` 350, `BATT_LOW_MAH` 90, `BATT_FS_LOW_ACT` 2 = return) | before arming |
| S4 geofence switched off in flight | `FENCE_ENABLE` 1 at start, set to 0 | 40 s into the mission |
| S5 wind | 8 m/s steady wind from the west | before arming |
| S6 motor failure | motor 1 output to zero (`SIM_ENGINE_FAIL` 1, `SIM_ENGINE_MUL` 0) | 40 s into the mission |
| S7 compass failure | `SIM_MAG1_FAIL` 1 | 40 s into the mission |

## How each log is checked (evaluate.py)

Exactly as the product does it: the log is read by `read_flight_log`, compared with its mission by `reconcile` (default
tolerances: 30 m sideways, 15 m height, at least 3 s), its events listed by `timeline`, its settings compared by
`drift_report` with the **approved baseline = the settings in the log of S0 run 1**, settings changed in flight by
`in_flight_changes`, and the morning verdict by `readiness.assess` (registration recorded and verified, so only the
log and settings decide).

## Expected results (declared)

| Scenario | Expected | Counts as met when |
|---|---|---|
| S0 | Clean flight | no warning-level event, no plan deviation, settings OK, verdict Ready |
| S1 | Drone blocked | settings verdict BLOCK with both `FS_THR_ENABLE` and `BATT_FS_LOW_ACT` named; verdict Do not fly |
| S2 | GPS loss shown | a "Poor GPS" warning in the timeline |
| S3 | Low battery shown | a "Battery below 20%" event in the timeline |
| S4 | In-flight change shown | `FENCE_ENABLE` 1 → 0 listed as a safety-critical setting changed in flight; verdict Check first |
| S5 | No false alarm in wind | no plan deviation at the default tolerances (largest sideways and height deviation reported) |
| S6 | Descriptive | the log is reviewed and no cause is named (by design); what the timeline shows is reported |
| S7 | Descriptive, known gap | AeroFleet reads the estimator's own sensor checks only from PX4 logs, so nothing about the compass is expected; what appears is reported |

**Outcome per scenario S0-S5:** met if the expectation holds in all 3 runs; partly met in 1-2; not met in 0.
Every run's numbers are reported in `research/results/sitl_check/` whatever they show. A run that fails to fly
(SITL error) is reported as such and rerun once.

    python research/sitl_check/run_scenarios.py
    python research/sitl_check/evaluate.py
