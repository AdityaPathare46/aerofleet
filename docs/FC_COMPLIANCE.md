# Flight-Controller Compliance Check

An operator connects a drone's flight controller to the laptop. AeroFleet
finds it, reads it over MAVLink, and produces a report with 59 checks in
seven categories. Each check shows the value that was read, the
requirement, how to fix it, and the source of the threshold. Physical
and paperwork items go on a manual checklist. A guarded, props-off motor
test confirms motor order and spin direction.

Desktop app: **Hardware → Drone compliance**. API: `/api/v1/hardware/fc`.
Code: `aerofleet/hardware/fc_discovery.py`, `fc_inspector.py`,
`compliance_rules.py`, `motor_layouts.py`, `fc_inspection_worker.py`,
`aerofleet/api/routes/fc_compliance.py`.

> Everything except the motor test is **read-only**. AeroFleet never
> writes parameters during a check. The only thing it sends is
> `MAV_CMD_SET_MESSAGE_INTERVAL` stream-rate requests, the same thing
> every ground station sends. They are not saved and reset on reboot.

---

## 1. Connecting: two paths, auto-detected

Only one program can open a USB serial (COM) port at a time. If Mission
Planner is connected to the drone, it holds that port. AeroFleet
therefore tries two paths, in this order:

### a) Mission Planner's forwarded MAVLink (UDP)

AeroFleet listens for about 2 s on **UDP 14550 and 14551** (on
`127.0.0.1`) for a vehicle HEARTBEAT. GCS and companion heartbeats are
ignored.

**One-time Mission Planner setting (MAVLink Mirror):**

1. Connect Mission Planner to the drone as usual.
2. Press **Ctrl-F** and click **MAVLink**, or open **SETUP → Advanced → MAVLink Mirror**.
3. Choose **UDP Client** and tick **Write**.
4. Enter host **127.0.0.1**, port **14550**, then Connect. Use 14551 if
   another program (e.g. QGroundControl) already listens on 14550.
5. In AeroFleet click **Auto-detect**, or just **Run check**.

Tick **Write**, or Mission Planner forwards the vehicle's telemetry to
AeroFleet but drops AeroFleet's requests. The report then shows every
parameter-based check as UNKNOWN, with a note explaining why. The motor
test also needs Write.

The mirror stays on only while Mission Planner is running. Mission
Planner's own docs describe the forwarding tool:
<https://ardupilot.org/planner/docs/common-mp-tools.html>.

### b) Direct USB

AeroFleet scans USB only when no forwarded stream is heard. It lists
serial ports with pyserial (`pip install -r requirements.txt` installs
it) and matches:

| USB ID | Recognised as | Confidence |
|---|---|---|
| `1209:5740` | ArduPilot (ChibiOS) | high |
| `1209:5741` | ArduPilot bootloader (reported, not used: wait for the firmware to boot) | high |
| `26AC:*` | 3DR / PX4 FMU | high |
| `2DAE:*` | CubePilot | high |
| `3162:*` | Holybro | high |
| `0483:5740` | ST virtual COM port (generic STM32) | low |
| product/manufacturer string contains ArduPilot, PX4, Pixhawk or Cube | — | medium |

Each match is opened and closed once to check whether it is free. If that
fails with a permission or busy error (Windows: "Access is denied";
Linux/macOS: "Resource busy"), AeroFleet reports:

> COM5 is in use (Mission Planner?) — enable MAVLink forwarding …

It reports that instead of a generic error, because forwarding is the
fix: you don't have to close Mission Planner.

### c) Manual connection string

**Connection override** in the UI (API `{"auto": false, "connection": …}`)
accepts any pymavlink string, e.g. `udpin:127.0.0.1:14550`,
`COM5,115200`, `/dev/ttyACM0,115200` or `tcp:127.0.0.1:5760` (SITL).

### Configuration

| Env var | Default | Meaning |
|---|---|---|
| `AEROFLEET_FC_UDP_PORTS` | `14550,14551` | UDP ports to listen on for a forward |
| `AEROFLEET_FC_UDP_HOST` | `127.0.0.1` | Listen interface; `0.0.0.0` accepts a forward from another PC on the LAN |

These endpoints open the flight controller, so they only run on the
hardware-owner process (`AEROFLEET_HARDWARE_OWNER`, see
`docs/MULTI_WORKER_ARCHITECTURE.md`). An inspection and a motor test
never hold the port at the same time. If a *live* AeroFleet link
(Hardware → Vehicles) is already bound to the UDP port, discovery reports
the port as busy.

---

## 2. What the inspection reads

1. Vehicle HEARTBEAT: autopilot, frame type, armed state.
2. Stream-rate requests for SYS_STATUS, BATTERY_STATUS, GPS_RAW_INT,
   EKF_STATUS_REPORT, VIBRATION, RC_CHANNELS, SERVO_OUTPUT_RAW,
   ESC_TELEMETRY_1_TO_4/5_TO_8, POWER_STATUS, RADIO_STATUS.
3. AUTOPILOT_VERSION via `MAV_CMD_REQUEST_MESSAGE`, falling back to
   `MAV_CMD_REQUEST_AUTOPILOT_CAPABILITIES`.
4. The full parameter list (`PARAM_REQUEST_LIST`). Any dropped index is
   re-requested with `PARAM_REQUEST_READ`, up to 3 rounds.
5. Telemetry sampled for 6 s by default (2–15 s via `sample_seconds`).
6. `MAV_CMD_RUN_PREARM_CHECKS`, collecting the autopilot's own
   `PreArm: …` STATUSTEXTs.

The result is stored as an immutable snapshot. The report is always
recomputed from the snapshot, the checklist and the motor-test records,
so ticking a checklist item can never overwrite a measured value.

---

## 3. What is checked

Statuses:

- **PASS**: measured and meets the requirement.
- **WARN**: measured and works, but outside guidance.
- **FAIL**: measured and does not meet the requirement.
- **UNKNOWN**: the data was not received. It is never guessed and never counts as a pass.
- **MANUAL**: cannot be sensed over MAVLink, so a person must check it.

**Verdict:**

- **FAIL** if any check is FAIL.
- Otherwise **INCOMPLETE** while a *required* check is UNKNOWN or any MANUAL item is unresolved.
- Otherwise **WARN** if any check is WARN.
- Otherwise **PASS**.

Optional checks (ESC telemetry, telemetry radio, external compass,
current sensor, hover throttle) can be UNKNOWN without blocking the
verdict, because many valid builds lack that hardware or data.

Thresholds come from ArduPilot where ArduPilot documents one. Each
check's `source` field holds the URL. Thresholds AeroFleet chose itself
are labelled as AeroFleet guidelines in the check's `reference` field.

### Flight controller & firmware
| Check | Requirement | Source |
|---|---|---|
| `fc.autopilot` | HEARTBEAT autopilot = ArduPilot | MAVLink HEARTBEAT |
| `fc.vehicle_type` | multicopter MAV_TYPE | MAVLink HEARTBEAT |
| `fc.firmware` | AUTOPILOT_VERSION received, official release build (WARN for dev/beta/rc) | MAVLink FIRMWARE_VERSION_TYPE |
| `fc.sensor_gyro/accel/mag/baro` | SYS_STATUS present + enabled + healthy | MAVLink SYS_STATUS |
| `fc.accel_calibrated` | INS_ACCOFFS/ACCSCAL not at defaults, no "3D Accel calibration needed" | ArduPilot pre-arm checks |
| `fc.compass_calibrated` | COMPASS_OFS non-zero and ≤ COMPASS_OFFS_MAX | ArduPilot pre-arm checks |
| `fc.ekf` | attitude valid; FAIL if ≥2 of velocity/position/compass variance ≥ FS_EKF_THRESH (the EKF failsafe condition), WARN for one | ArduPilot EKF failsafe |
| `fc.vibration` | < 30 m/s² (WARN 30–60, FAIL > 60); FAIL if clipping counters grow during the sample | ArduPilot "Measuring Vibration" |
| `fc.arming_check` | ARMING_CHECK = 1 (or ARMING_SKIPCHK = 0 on newer firmware) | ArduPilot pre-arm checks |
| `fc.logging` | LOG_BITMASK ≠ 0, LOG_BACKEND_TYPE ≠ 0, logging healthy | ArduPilot logs |
| `fc.prearm` | no PreArm messages; pre-arm health bit set | ArduPilot pre-arm checks |

Vibration is measured on the ground, disarmed. In-flight vibration is
higher, so the evidence tells you to confirm it with a hover log.

### Battery & power
| Check | Requirement | Source |
|---|---|---|
| `batt.monitor` | BATT_MONITOR ≠ 0 (WARN for voltage-only) | ArduPilot power module setup |
| `batt.voltage` | 3.3–4.2 V/cell for the reported or inferred cell count | ArduPilot tuning setup (MOT_BAT_VOLT_MAX/MIN per-cell guidance) |
| `batt.cell_min` | every cell ≥ 3.5 V at rest | AeroFleet guideline |
| `batt.cell_balance` | max − min ≤ 0.10 V | AeroFleet guideline |
| `batt.capacity` | BATT_CAPACITY > 0, WARN if still the 3300 default | AP_BattMonitor defaults |
| `batt.fs_low_action` / `batt.fs_critical_action` | BATT_FS_LOW_ACT / BATT_FS_CRT_ACT ≠ 0 (**the ArduCopter default is 0 = none**); WARN for 5 = Terminate | ArduPilot battery failsafe |
| `batt.fs_thresholds` | low and critical set (voltage or mAh), low > critical, low ≥ 3.3 V/cell | ArduPilot battery failsafe |
| `batt.board_vcc` | FAIL outside 4.3–5.8 V (ArduPilot pre-arm window); WARN outside 4.8–5.4 V (AeroFleet margin) | ArduPilot pre-arm checks |

Per-cell voltages are only available when the battery monitor measures
cells (smart/DroneCAN batteries, cell monitors). A standard analog power
module reports only the pack voltage. ArduPilot then puts the pack total
in `voltages[0]`, which AeroFleet detects, so `batt.cell_min` and
`batt.cell_balance` become UNKNOWN. They never PASS on a pack-only
reading. The cell count is inferred as ⌈V / 4.25⌉, and the evidence says
it was inferred.

### Motors & ESCs
| Check | Requirement | Source |
|---|---|---|
| `mot.frame` | FRAME_CLASS ≠ 0 with a valid FRAME_TYPE | ArduPilot pre-arm checks |
| `mot.output_mapping` | SERVOn_FUNCTION maps Motor1…MotorN exactly once each; names duplicates and missing motors | ArduPilot ESC/motor connection |
| `mot.pwm_range` | MOT_PWM_MIN < MOT_PWM_MAX with ≥ 500 µs span, or 1000/2000 for DShot | ArduPilot motor range / DShot |
| `mot.spin_arm_min` | MOT_SPIN_ARM < MOT_SPIN_MIN < MOT_SPIN_MAX | ArduPilot pre-arm checks |
| `mot.esc_telemetry` *(optional)* | every motor's ESC reports; disarmed temperature ≤ 60 °C (AeroFleet heuristic) | ArduPilot ESC telemetry |
| `mot.motor_test` | the motor-test wizard, see §4 | ArduPilot motor diagrams |

### Airframe & design
| Check | Requirement | Source |
|---|---|---|
| `air.hover_throttle` *(optional)* | MOT_THST_HOVER in ArduPilot's typical 0.2–0.6; WARN above 0.6 (underpowered); UNKNOWN while still at the 0.35 default (not yet learned) | ArduPilot "Setting Hover Throttle" |
| `air.dgca_category` | weight category (Nano/Micro/Small/Medium/Large) from the fleet registry `weight_kg` plus payload, or the weight entered for the inspection; WARN within 10 % of a boundary | reuses `compliance_report._airworthiness_domain` |
| MANUAL: `air.props`, `air.frame_integrity`, `air.arm_locks`, `air.cg`, `air.payload_mount` | props, cracks, arm locks, CG, payload retention | — |

### Wiring & sensors
| Check | Requirement | Source |
|---|---|---|
| `wir.gps_type` | GPS_TYPE (GPS1_TYPE) ≠ 0 | ArduPilot GPS |
| `wir.gps_fix` | 3D fix, HDOP ≤ GPS_HDOP_GOOD/100; WARN with fewer than 6 satellites (AeroFleet heuristic). **Bench mode turns no-fix and high HDOP into WARN.** | ArduPilot pre-arm checks |
| `wir.compass_external` *(optional)* | primary compass external | ArduPilot compass setup |
| `wir.rc_receiver` | RC_CHANNELS ≥ 4 channels, receiver healthy | ArduPilot radio failsafe |
| `wir.telemetry_radio` *(optional)* | RADIO_STATUS seen → PASS with RSSI/noise; not seen → MANUAL (normal over USB) | MAVLink RADIO_STATUS |
| `wir.current_sensor` *(optional)* | current measured, 0–10 A while disarmed (AeroFleet heuristic); WARN for exactly 0 A or negative | ArduPilot power module setup |
| MANUAL: `wir.gps_mast`, `wir.connectors`, `wir.antennas` | — | — |

### Failsafes
| Check | Requirement | Source |
|---|---|---|
| `fs.rc_loss` | FS_THR_ENABLE ≠ 0 and 910 ≤ FS_THR_VALUE < RC3_MIN | ArduPilot radio failsafe / pre-arm |
| `fs.gcs_loss` | FS_GCS_ENABLE ≠ 0 (WARN when off: AeroFleet commands the aircraft over MAVLink) | ArduPilot GCS failsafe |
| `fs.ekf` | FS_EKF_ACTION ≠ 0, FS_EKF_THRESH in (0, 1.0] | ArduPilot EKF failsafe |
| `fs.crash_check` | FS_CRASH_CHECK = 1 | ArduPilot crash check |
| `fs.fence_enabled` | FENCE_ENABLE = 1 | ArduPilot simple geofence |
| `fs.fence_altitude` | FENCE_TYPE includes the altitude ceiling and FENCE_ALT_MAX ≤ 120 m | DGCA Drone Rules 2021 (green zone up to 400 ft AGL) |
| `fs.fence_action` | FENCE_ACTION ≠ 0 | ArduPilot simple geofence |
| `fs.rtl_altitude` | RTL altitude ≥ 5 m (AeroFleet heuristic), ≤ 120 m, below the fence ceiling (ArduPilot caps it below the fence anyway, so WARN) | ArduPilot RTL mode |

### DGCA regulatory
| Check | Requirement |
|---|---|
| `dgca.uin` | A Digital Sky UIN is recorded for the aircraft. FAIL if none. |
| MANUAL: `dgca.remote_pilot` | Remote Pilot Certificate. |
| MANUAL: `dgca.npnt` | NPNT / Digital Sky permission. |
| MANUAL: `dgca.airspace` | Green, yellow or red zone on the Digital Sky map. |
| MANUAL: `dgca.insurance` | Third-party insurance. |
| MANUAL: `dgca.type_certificate` | DGCA type certificate for the model. |

**UIN:** AeroFleet's fleet registry has no UIN field today. The UIN
entered when starting the inspection is stored with the inspection
record. A PASS means "recorded", not "valid on Digital Sky".

**NPNT is MANUAL on purpose.** ArduPilot exposes no NPNT or permission
artefact state over MAVLink, so AeroFleet cannot sense it and does not
pretend to.

### Why these are MANUAL

MAVLink carries what the autopilot measures or is configured with.
AeroFleet cannot sense:

- **Physical condition:** prop damage, cracks, arm latches, CG, a loose
  GPS mast, connector retention.
- **Paperwork:** pilot certificate, insurance, type certificate, the
  airspace zone for a given day.

An operator's tick is stored as an **attestation** (who, when, note).
The item stays MANUAL with `resolved: true` and never turns into a
measured PASS. Marking an item **failed** turns it into a FAIL.

---

## 4. Motor test: safety

The motor test is the only step that actuates hardware. It needs an
**operator** account. The server enforces these gates on every request,
whatever the UI does:

1. `props_removed_confirmed: true` must be in the request. Otherwise the
   server returns **400** and nothing is sent. The UI asks for this in a
   three-tick modal: props removed, drone disarmed and restrained,
   area clear.
2. **Disarmed only.** The server reconnects, reads a fresh heartbeat and
   refuses with **409** if the vehicle is armed.
3. **Same vehicle.** The heartbeat's system id must match the inspected one.
4. **One motor at a time.** A process-wide hardware lock is shared with
   the inspection worker. A second request while one runs gets **409**.
5. **Caps:** throttle is capped at **15 %** and duration at **3 s**.
   Larger requests are clamped, and the response shows the requested and
   applied values with `capped: true`.
6. **Test order "sequence":** `MAV_CMD_DO_MOTOR_TEST` is sent with
   param1 = letter position (A = 1), param2 = percent, param5 = 1 motor,
   param6 = `MOTOR_TEST_ORDER_SEQUENCE`. This matches Mission Planner.
   ArduCopter's handler (`ArduCopter/GCS_Mavlink.cpp`, `motor_test.cpp`)
   always treats param1 as the test-order position.

The flight controller also applies its own checks, for example refusing
unless landed, safety switch pressed, or RC calibrated. A refusal is
returned as 409 with the autopilot's STATUSTEXT.

**Expected position and direction** (letters run clockwise from the
nose), transcribed from ArduPilot's motor matrix
`libraries/AP_Motors/AP_MotorsMatrix.cpp` on the Copter-4.5 branch:

| Frame | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| Quad X | M1 front-right CCW | M4 rear-right CW | M2 rear-left CCW | M3 front-left CW | | |
| Quad + | M3 front CW | M1 right CCW | M4 rear CW | M2 left CCW | | |
| Hexa X | M5 front-right CCW | M1 right CW | M4 rear-right CCW | M6 rear-left CW | M2 left CCW | M3 front-left CW |

The operator marks each motor **correct** or **incorrect**:

- Any incorrect motor fails the check.
- Once all motors are confirmed correct, the check resolves.

**ESC telemetry corroboration:** when ESC telemetry exists, AeroFleet
records the highest rpm per ESC during the spin and compares it with the
ESC(s) that SERVOn_FUNCTION says drive that motor:

- `corroborated`: the expected ESC spun.
- `mismatch`: a different ESC spun, or more than one ESC turned for a single motor.
- `no_rpm`: no ESC reported rotation.
- `unavailable`: there is no ESC telemetry.

A mismatch on a motor the operator confirmed turns the check into WARN.
Other frames: use Mission Planner's Motor Test and ArduPilot's diagrams.
<https://ardupilot.org/copter/docs/connect-escs-and-motors.html>

---

## 5. API

All endpoints are under `/api/v1/hardware/fc` and need a bearer token.

| Method & path | Who | What |
|---|---|---|
| `GET /discover?listen_s=2` | active user | UDP forward, then USB scan; `mission_planner_help` when nothing is forwarded |
| `POST /inspections` | active user | `{auto, connection?, drone_id?, city, uin?, weight_kg?, payload_kg, bench_mode, sample_seconds}` → 202 `{inspection_id}` |
| `GET /inspections/{id}` | active user | status, progress %, stage, report, checklist, motor tests, motor layout, snapshot |
| `GET /inspections?drone_id=` | active user | history |
| `GET /inspections/{id}/export` | active user | the same as JSON attachment |
| `POST /inspections/{id}/checklist` | operator | `{items: [{check_id, result: confirmed/failed/unchecked, note}]}` (manual items only) |
| `POST /inspections/{id}/motor-test` | operator | `{motor: "A", throttle_pct, duration_s, props_removed_confirmed: true}` |
| `POST /inspections/{id}/motor-test/{motor}/confirm` | operator | `{result: correct/incorrect, note}` |
| `GET /motor-layouts`, `GET /rules` | active user | static diagram data and the rule table |

Inspections are stored in the `fc_inspections` table and are never
deleted by the API, so they form the audit trail. Each record holds:

- the snapshot
- the context: UIN, weight and its source, bench mode
- who requested the inspection
- the checklist attestations
- the motor-test log

---

## 6. Simulator and tests

`tools/mock_mavlink_vehicle.py` is a MAVLink2 ArduCopter 4.5 stand-in:

- ~450 real parameter names
- the telemetry streams above
- PreArm messages
- the motor test (ESC rpm rises on the tested output)

It sends to `127.0.0.1:<port>`, exactly like Mission Planner's mirror.

```bash
python tools/mock_mavlink_vehicle.py --port 14550 --no-d2d --profile faulty
# healthy | faulty | bench;  --lossy-params  --start-armed
```

The faulty profile's problems:

- BATT_FS_LOW_ACT = BATT_FS_CRT_ACT = 0 (the real defaults)
- FENCE_ALT_MAX 150 m
- one cell 0.25 V low
- 45–52 m/s² vibration with growing clipping
- no compass
- SERVO3 duplicating Motor1
- hover throttle 0.64
- GCS failsafe off

The bench profile has no GPS fix.

Tests (none of them mock pymavlink):

- `tests/unit/test_fc_compliance_rules.py`: every rule against synthetic snapshots
- `tests/unit/test_fc_discovery.py`: serial scan with fake port lists, busy-port wording, UDP port conflicts
- `tests/integration/test_fc_compliance_api.py`: discovery → inspection → report → checklist → motor test over real UDP against the mock, including all motor-test gates

## 7. What still needs a real board

Everything above has run against the mock only. Still to confirm on
hardware:

- The USB scan on real ports: exact Windows "Access is denied" wording
  from pyserial while Mission Planner holds the port, and macOS/Linux
  exclusive-lock behaviour.
- Mission Planner's mirror with **Write**: that parameter requests and
  `MAV_CMD_DO_MOTOR_TEST` pass through, and that the mirror forwards
  STATUSTEXT and COMMAND_ACK meant for AeroFleet.
- `MAV_CMD_RUN_PREARM_CHECKS` ACK and STATUSTEXT timing on 4.5.x firmware.
- Real ESC telemetry indexing (BLHeli32/AM32/bidirectional DShot) for
  the corroboration.
- Parameter download time for ~1,000 params over a slow radio link. The
  default timeout is 30 s.
