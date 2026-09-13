"""Headless Unity physics validation of Feature 1's optimized routes
(aerofleet/city/route_weights.py + trajectory_builder.py). Shells out to
the real Unity CLI (`unity run`, confirmed via `unity run --help` on the
authoring machine) rather than a live MCP connection — a live connection
needs a human-attended Editor window with the Pipeline package running,
which isn't automatable or testable in a script/CI the way batch mode is.

This is NOT part of the live dispatch path. aerofleet/api/routes/orders.py's
dispatch_order stays fully synchronous/deterministic/LLM-free per
docs/PATENT_NOVELTY.md's Claim 1 — this is a separate, offline validation
tool an operator or a CI job runs against an already-computed route.
Blocking synchronously on the Unity subprocess is fine here, unlike
anything in the live request path.

HONEST STATUS: written against the real Unity CLI's confirmed
subcommands/flags and unity/AeroFleetValidation/'s real JSON contract
(see that project's own README.md), but this module and that C# project
have not yet been run together against an actual installed Unity Editor —
tested by inspection and by mirroring confirmed CLI behavior, not yet by
execution. Run find_unity_cli() and a real route through
run_unity_validation() once an Editor is installed to confirm.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_PROJECT_PATH = REPO_ROOT / "unity" / "AeroFleetValidation"
DEFAULT_TIMEOUT_S = 180

# Must match RouteValidator.cs's own defaults exactly — reasonable,
# documented placeholders for a small-category delivery quadcopter, not a
# specific cited product's spec sheet (same honesty standard as
# fleet/models.py's Drone.weight_kg). Deliberately duplicated on both
# sides of the Python/C# boundary rather than one importing the other.
DEFAULT_MAX_THRUST_N = 60.0
DEFAULT_DRAG_COEFFICIENT = 0.9


@dataclass
class WaypointResult:
    index: int
    reached: bool
    deviation_m: float


@dataclass
class UnityValidationResult:
    success: bool
    waypoints: List[WaypointResult] = field(default_factory=list)
    events: List[str] = field(default_factory=list)
    error: Optional[str] = None
    # Set only when Unity itself couldn't be run at all (missing CLI,
    # missing project, timeout, crash before writing a result) — distinct
    # from a real, completed validation that legitimately found the route
    # unflyable (that's success=False with real waypoints/events data).
    invocation_error: Optional[str] = None


def find_unity_cli() -> Optional[str]:
    """Locate the real Unity CLI binary — PATH first, then the known
    install location this project's authoring machine has it at
    (~/.unity/bin/unity), rather than assuming either unconditionally."""
    on_path = shutil.which("unity")
    if on_path:
        return on_path
    home_install = Path.home() / ".unity" / "bin" / "unity"
    if home_install.exists():
        return str(home_install)
    return None


def build_route_json(
    lat_lons: List[Tuple[float, float]],
    altitudes_m: List[float],
    wind_speeds_mps: List[float],
    drone_mass_kg: float,
    max_thrust_n: float = DEFAULT_MAX_THRUST_N,
    drag_coefficient: float = DEFAULT_DRAG_COEFFICIENT,
) -> Dict[str, Any]:
    """The real route.json shape RouteValidator.cs reads (see
    unity/AeroFleetValidation/README.md's JSON contract), built from
    parallel per-waypoint lists — all three must be the same length.

    Deliberately takes lat/lon explicitly rather than trajectory_builder.
    build_trajectory_points_from_path()'s own List[Dict] output directly:
    that function's dicts carry the 11 CBF-checkable fields
    (battery_margin_wh, in_red_zone, etc.), not lat/lon — real, honest gap
    between the two schemas, not something to paper over. A caller wiring
    this up for real needs to keep the node path's lat/lon alongside
    trajectory_points, not assume this function can derive them."""
    if not (len(lat_lons) == len(altitudes_m) == len(wind_speeds_mps)):
        raise ValueError("lat_lons, altitudes_m, and wind_speeds_mps must all be the same length")
    waypoints = [
        {"lat": lat, "lon": lon, "altitude_m": alt, "wind_speed_mps": wind}
        for (lat, lon), alt, wind in zip(lat_lons, altitudes_m, wind_speeds_mps)
    ]
    return {
        "waypoints": waypoints,
        "drone_mass_kg": drone_mass_kg,
        "max_thrust_n": max_thrust_n,
        "drag_coefficient": drag_coefficient,
    }


def run_unity_validation(
    route: Dict[str, Any],
    work_dir: Path,
    project_path: Path = DEFAULT_PROJECT_PATH,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> UnityValidationResult:
    """Shells out to the real Unity CLI in batch mode and blocks
    synchronously — this is an offline/CI validation tool, never part of
    the live dispatch path, so a blocking subprocess wait is fine here
    unlike anything in aerofleet/api/routes/orders.py.

    work_dir: a directory this function writes route.json/result.json/
    unity.log into. Creating and cleaning it up is the caller's
    responsibility — this module doesn't assume a scratch-dir convention
    that doesn't exist elsewhere in this codebase."""
    unity_bin = find_unity_cli()
    if unity_bin is None:
        return UnityValidationResult(
            success=False,
            invocation_error="Unity CLI not found (checked PATH and ~/.unity/bin/unity) — install it first.",
        )
    if not project_path.exists():
        return UnityValidationResult(success=False, invocation_error=f"Unity project not found at {project_path}")

    work_dir.mkdir(parents=True, exist_ok=True)
    route_path = work_dir / "route.json"
    output_path = work_dir / "result.json"
    log_path = work_dir / "unity.log"

    with open(route_path, "w", encoding="utf-8") as f:
        json.dump(route, f, indent=2)

    cmd = [
        unity_bin, "run", str(project_path),
        "--timeout", str(timeout_s),
        "--",
        "-batchmode", "-nographics", "-quit",
        "-executeMethod", "RouteValidator.Run",
        "-route", str(route_path),
        "-output", str(output_path),
        "-logFile", str(log_path),
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s + 10)
    except subprocess.TimeoutExpired:
        return UnityValidationResult(
            success=False,
            invocation_error=f"Unity process did not exit within {timeout_s}s (see {log_path} if it was written).",
        )
    except OSError as exc:
        return UnityValidationResult(success=False, invocation_error=f"Failed to launch Unity CLI: {exc}")

    if not output_path.exists():
        detail = proc.stderr.strip() or proc.stdout.strip() or "no output captured"
        return UnityValidationResult(
            success=False,
            invocation_error=f"Unity exited (code {proc.returncode}) without writing {output_path}: {detail}",
        )

    with open(output_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    return UnityValidationResult(
        success=bool(raw.get("success", False)),
        waypoints=[
            WaypointResult(index=w["index"], reached=w["reached"], deviation_m=w["deviation_m"])
            for w in raw.get("waypoints", [])
        ],
        events=list(raw.get("events", [])),
        error=raw.get("error"),
    )
