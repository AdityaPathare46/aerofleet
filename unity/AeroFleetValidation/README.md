# AeroFleetValidation — Unity Physics Validation

Headless physics validation of AeroFleet's optimized trajectory output
(`aerofleet/city/route_weights.py` + `trajectory_builder.py`). The CBF gate
checks each waypoint's state independently and deterministically; this
project checks whether a real point-mass rigid body can actually *fly* the
path between those waypoints — a genuinely different, complementary check,
not a duplicate of the CBF math. See `aerofleet/validation/unity_bridge.py`
for the Python side that drives this.

## Status — read before assuming this works

**Written, not yet run.** This was authored against the real, confirmed
Unity CLI batch-mode invocation (`unity run --help`) and standard,
documented Unity APIs, but no Unity Editor was installed on the authoring
machine at the time — so `Assets/Editor/RouteValidator.cs` has not been
compiled or executed by a real Editor yet. Treat it as a real first draft
to test, not verified working code. `ProjectSettings/ProjectVersion.txt`'s
`m_EditorVersionWithRevision` is a placeholder (no real changeset hash
available without an Editor to generate one) — Unity will likely prompt
about this on first open; that's expected, not a sign of corruption.

## First-time setup

1. Install the target Editor version if you haven't already:
   ```bash
   unity install 6000.0.83f1
   ```
2. Open this project in Unity Editor once, normally (not batch mode) —
   this lets Unity regenerate `Library/` (its cache, not checked into git)
   and resolve/confirm the version in `ProjectVersion.txt`. Fix any
   compile errors `RouteValidator.cs` surfaces at this point; this is the
   real first compile.

## Running a validation (after setup)

```bash
unity run unity/AeroFleetValidation -- -batchmode -nographics -quit \
    -executeMethod RouteValidator.Run \
    -route /path/to/route.json \
    -output /path/to/result.json \
    -logFile /path/to/unity.log
```

Or, once the Python bridge is wired up, just call
`aerofleet/validation/unity_bridge.py`'s `run_unity_validation()`, which
builds this exact command for you.

## The JSON contract

**Input** (`route.json`, written by `unity_bridge.py` from a real
`trajectory_builder.py` waypoint list):
```json
{
  "waypoints": [
    {"lat": 18.55, "lon": 73.90, "altitude_m": 30.0, "wind_speed_mps": 3.0},
    {"lat": 18.56, "lon": 73.91, "altitude_m": 30.0, "wind_speed_mps": 3.0}
  ],
  "drone_mass_kg": 12.5,
  "max_thrust_n": 60.0,
  "drag_coefficient": 0.9
}
```

**Output** (`result.json`, written by `RouteValidator.cs`):
```json
{
  "success": true,
  "waypoints": [
    {"index": 0, "reached": true, "deviation_m": 0.0},
    {"index": 1, "reached": true, "deviation_m": 0.8}
  ],
  "events": [],
  "error": null
}
```
`success` is `true` only if every waypoint was reached within the 2m
tolerance inside the 120s-per-leg safety cap. `events` lists any leg that
didn't make it, with the actual deviation — this is the real signal this
whole project exists to produce: a route that passed the CBF gate's
per-point math but isn't actually flyable in between.
