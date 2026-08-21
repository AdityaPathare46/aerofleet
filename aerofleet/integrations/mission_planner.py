"""Interop with ArduPilot Mission Planner — NOT a vendored copy of it.

Mission Planner (github.com/ArduPilot/MissionPlanner, GPL-3.0) is a full
Windows-native C#/.NET ground control station. Merging its codebase into
this Python/TypeScript project wouldn't build, wouldn't run, and wouldn't
actually be "integrated" with anything — it would just be a second,
disconnected application sitting in the tree. The real integration point
is the one AeroFleet already has: aerofleet/hardware/mavlink_link.py talks
raw MAVLink over the exact same connection-string format (udp:/tcp:/serial)
that Mission Planner, QGroundControl, and pymavlink all use, and both tools
can read/write the same standard `.waypoints` file format (QGC WPL 110).

This module generates that file from an already-CBF-approved dispatch —
letting an operator load AeroFleet's decision straight into the real,
professional flight-planning tool for upload/monitoring, rather than
AeroFleet reinventing a waypoint editor. AeroFleet still owns the only
decision that matters (the CBF gate, before this file can even be
generated); Mission Planner is downstream tooling, not a decision-maker.

No GPL obligations are triggered by this file's existence: it doesn't
link against, embed, or derive from Mission Planner's source — it emits a
plain-text file in a public, tool-agnostic format that MAVLink ecosystem
software happens to share.
"""
from typing import Any, Dict, Optional

# MAVLink command/frame IDs used below — stable, standard values, not
# specific to any one GCS implementation.
_MAV_FRAME_GLOBAL = 0
_MAV_FRAME_GLOBAL_RELATIVE_ALT = 3
_MAV_CMD_NAV_WAYPOINT = 16
_MAV_CMD_NAV_RETURN_TO_LAUNCH = 20
_MAV_CMD_NAV_TAKEOFF = 22


def _wpl_row(
    index: int, current: int, frame: int, command: int,
    p1: float, p2: float, p3: float, p4: float,
    lat: float, lon: float, alt: float, autocontinue: int = 1,
) -> str:
    return "\t".join(str(v) for v in (
        index, current, frame, command, p1, p2, p3, p4, lat, lon, alt, autocontinue
    ))


def build_waypoint_file(dispatch_plan: Dict[str, Any]) -> Optional[str]:
    """Builds a QGC WPL 110 `.waypoints` file for one approved dispatch —
    home (origin depot) -> takeoff -> waypoint (destination) -> RTL.

    Returns None if the plan is missing coordinates it needs (e.g. an
    origin depot lookup failed at dispatch time) — callers should treat
    that as "nothing to export" rather than emitting a broken file.
    """
    origin_lat, origin_lon = dispatch_plan.get("origin_lat"), dispatch_plan.get("origin_lon")
    dest_lat, dest_lon = dispatch_plan.get("dest_lat"), dispatch_plan.get("dest_lon")
    altitude_m = dispatch_plan.get("altitude_m")
    if None in (origin_lat, origin_lon, dest_lat, dest_lon, altitude_m):
        return None

    rows = [
        _wpl_row(0, 1, _MAV_FRAME_GLOBAL, _MAV_CMD_NAV_WAYPOINT,
                 0, 0, 0, 0, origin_lat, origin_lon, 0),
        _wpl_row(1, 0, _MAV_FRAME_GLOBAL_RELATIVE_ALT, _MAV_CMD_NAV_TAKEOFF,
                 0, 0, 0, 0, origin_lat, origin_lon, altitude_m),
        _wpl_row(2, 0, _MAV_FRAME_GLOBAL_RELATIVE_ALT, _MAV_CMD_NAV_WAYPOINT,
                 0, 0, 0, 0, dest_lat, dest_lon, altitude_m),
        _wpl_row(3, 0, _MAV_FRAME_GLOBAL_RELATIVE_ALT, _MAV_CMD_NAV_RETURN_TO_LAUNCH,
                 0, 0, 0, 0, 0, 0, 0),
    ]
    return "QGC WPL 110\n" + "\n".join(rows) + "\n"
