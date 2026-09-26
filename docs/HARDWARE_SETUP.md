# Hardware Setup — Connecting Real Drones

AeroFleet can command real ArduPilot/PX4 flight controllers over MAVLink
(`aerofleet/hardware/`), not just simulated drones. This document is the
safety context and the exact steps to connect one.

Before connecting a drone for flight, run the pre-flight **flight-controller
compliance check** (Hardware → Drone compliance). It works alongside Mission
Planner via its MAVLink Mirror, or directly over USB — see
[FC_COMPLIANCE.md](FC_COMPLIANCE.md).

## Read this first

**This software makes AeroFleet capable of commanding real aircraft. It
does not, on its own, make flying safe.** Standard UAV safety practice —
a human safety pilot with RC override authority, the flight controller's
own independently-configured failsafes (RC-loss, GCS-loss, low-battery,
geofence), and flying within your DGCA-authorized category and visual
line of sight — remains mandatory. AeroFleet's CBF safety gate and
hardware layer are a fleet-coordination layer *on top of* that baseline,
not a replacement for it.

Every command AeroFleet sends to real hardware — arm, takeoff, goto,
mission upload, RTL — goes through the CBF gate first when it originates
from the normal dispatch path (`POST /api/v1/orders/{id}/dispatch`, see
`aerofleet/api/routes/orders.py`). The manual override endpoints in
`aerofleet/api/routes/hardware.py` (arm/disarm/emergency-stop-all) are
direct operator controls and intentionally bypass the dispatch pipeline —
that's the point of a kill switch — but they still require an
authenticated user and, in the desktop app, an explicit two-click
confirmation for the fleet-wide stop.

## Try it safely first: the mock vehicle

Before pointing this at anything that can fly, verify the whole pipeline
against `tools/mock_mavlink_vehicle.py` — a small fake ArduPilot vehicle
that speaks real MAVLink over UDP and responds to arm/mode/mission/RTL
commands with proper ACKs. It has no flight dynamics; it just proves the
wire protocol and AeroFleet's command layer work end to end.

```bash
python tools/mock_mavlink_vehicle.py --port 14550
```

Then connect to it exactly like a real vehicle (see below), using
`connection_string=udpin:127.0.0.1:14550`.

## Connecting a real vehicle

Use the Hardware panel in the desktop app, or call the API directly:

```bash
curl -X POST http://localhost:8000/api/v1/hardware/vehicles/DEPOT-1-D1/connect \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"connection_string": "udp:127.0.0.1:14550", "city": "pune"}'
```

`connection_string` uses the same format Mission Planner / QGroundControl
use:

| Setup | connection_string |
|---|---|
| ArduPilot SITL, or a companion computer forwarding UDP | `udp:127.0.0.1:14550` |
| GCS is the UDP listener (matches the mock vehicle above) | `udpin:127.0.0.1:14550` |
| TCP SITL | `tcp:127.0.0.1:5760` |
| Flight controller wired directly over USB | `/dev/ttyACM0,57600` (macOS: `/dev/cu.usbmodemXXXX,57600`) |
| Telemetry radio (SiK, RFD900, etc.) | `/dev/ttyUSB0,57600` |

For a USB/serial connection from inside the Docker container, see the
commented `devices:` block on the `api` service in `docker-compose.yml` —
container-to-USB passthrough needs the host device path mapped in
explicitly and isn't enabled by default.

## Flight-controller-side configuration

- **ArduPilot**: if connecting over a telemetry port rather than USB,
  set `SERIALx_PROTOCOL=2` (MAVLink2) on that serial port and confirm
  `SYSID_THISMAV` is unique per vehicle if you're running more than one.
- **PX4**: MAVLink is on by default on the telemetry port
  (`MAV_0_CONFIG`); confirm the baud rate matches your radio/USB link.
- Both: AeroFleet auto-detects ArduPilot vs. PX4 from the vehicle's own
  `HEARTBEAT.autopilot` field and reads its live mode table via
  `mode_mapping()` — no per-autopilot configuration needed on the
  AeroFleet side.

## What AeroFleet does and doesn't do here

- Does: telemetry polling (position, battery, armed state, GPS fix) at
  2 Hz, arm/disarm, takeoff, guided-mode goto, full mission upload via
  the MAVLink mission protocol, return-to-launch, a best-effort onboard
  circular geofence push (ArduPilot `FENCE_*` parameters), and the
  fleet-wide emergency-stop-all kill switch.
- Doesn't: replace your flight controller's own failsafes, provide a
  polygon (non-circular) onboard geofence (documented limitation — the
  circular fence is what's implemented; a full MAVLink fence-item upload
  is a natural follow-on), or guarantee link recovery — if the
  connection drops, the vehicle's own configured failsafe behavior
  (whatever you set `FS_*` / `COM_DL_LOSS_*` to) is what actually
  protects it, not AeroFleet.
